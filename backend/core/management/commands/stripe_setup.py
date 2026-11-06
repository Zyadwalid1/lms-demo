"""python manage.py stripe_setup: connect the LMS plans to your Stripe account.

    1. checks STRIPE_SECRET_KEY works (test mode only unless --allow-live)
    2. creates a Stripe product + price for every plan / add-on price that has none yet,
       or whose price id is a demo placeholder or a different amount (Stripe prices
       cannot be edited, so a new one is created and takes over the lookup key)
    3. saves the real price ids on the LMS plan prices
    4. checks STRIPE_WEBHOOK_SECRET is set

Safe to run again: products and prices are found by fixed ids / lookup keys.
Never prints keys. Use --dry-run to see what it would do.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.commerce import gateway
from apps.commerce.models import AddonPrice, PlanPrice
from core.tenancy import tenant_context


class Command(BaseCommand):
    help = "Check the Stripe keys and create the Stripe prices for plans and add-ons."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-live", action="store_true", help="permit a live-mode key")

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  PASS  {msg}"))

    def warn(self, msg):
        self.stdout.write(self.style.WARNING(f"  NOTE  {msg}"))

    def handle(self, *args, dry_run, allow_live, **opts):
        key = settings.STRIPE_SECRET_KEY
        self.stdout.write("Stripe setup")
        if not key:
            raise CommandError(
                "STRIPE_SECRET_KEY is empty in backend/.env (Developers > API keys > Secret key)."
            )
        if key.startswith("pk_"):
            raise CommandError(
                "STRIPE_SECRET_KEY holds the publishable key (pk_...). Use the secret key (sk_...)."
            )
        live = "_live_" in key
        if live and not allow_live:
            raise CommandError("This is a LIVE key. The demo must use a test key (sk_test_...).")
        client = gateway._client()
        try:
            client.v1.balance.retrieve()
        except Exception as exc:  # noqa: BLE001 - report any Stripe error plainly
            raise CommandError(f"Stripe rejected the key: {type(exc).__name__}") from exc
        self.ok(f"secret key works ({'LIVE' if live else 'test'} mode)")

        with tenant_context(staff=True):
            rows = [
                (p, f"lms_plan_{p.plan.code}", p.plan.name, p.plan.interval, p.plan.is_active)
                for p in PlanPrice.objects.select_related("plan", "currency")
            ] + [
                (p, f"lms_addon_{p.addon.code}", p.addon.name, p.interval, p.addon.is_active)
                for p in AddonPrice.objects.select_related("addon", "currency")
            ]
            created = reused = 0
            for price, product_id, name, interval, active in rows:
                code = price.currency.code
                amount = gateway.to_stripe_amount(price.amount_minor, code, price.currency.exponent)
                lookup = f"{product_id}_{code.lower()}"
                found = client.v1.prices.list(params={"lookup_keys": [lookup], "limit": 1}).data
                match = found[0] if found and found[0].unit_amount == amount and found[0].recurring \
                    and found[0].recurring.interval == interval else None  # fmt: skip
                if match:
                    reused += 1
                    stripe_id = match.id
                elif dry_run:
                    self.warn(f"would create {lookup}: {amount} {code}/{interval}")
                    continue
                else:
                    try:
                        client.v1.products.retrieve(product_id)
                    except Exception:  # noqa: BLE001 - not found: create it
                        client.v1.products.create(params={"id": product_id, "name": name, "active": active})
                    stripe_id = client.v1.prices.create(params={
                        "product": product_id, "currency": code.lower(), "unit_amount": amount,
                        "recurring": {"interval": interval}, "lookup_key": lookup, "transfer_lookup_key": True,
                        "tax_behavior": "inclusive", "metadata": {"lms_lookup": lookup},
                    }).id  # fmt: skip
                    created += 1
                if price.stripe_price_id != stripe_id and not dry_run:
                    type(price).objects.filter(pk=price.pk).update(stripe_price_id=stripe_id)
            self.ok(f"{len(rows)} plan/add-on prices linked ({created} created, {reused} already in Stripe)")

        secret = settings.STRIPE_WEBHOOK_SECRET
        if secret.startswith("whsec_"):
            self.ok("webhook signing secret is set")
        else:
            self.warn(
                "STRIPE_WEBHOOK_SECRET is missing: run `stripe listen` (see the setup notes) and paste its whsec_"
            )
        self.stdout.write("Done.")
