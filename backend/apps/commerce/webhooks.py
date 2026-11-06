"""Stripe webhooks: the only way an order becomes paid or a subscription active.

    1. verify the signature on the RAW body (gateway.construct_event)
    2. store the event once (unique event id): a redelivery is acknowledged and ignored
    3. process it in its own transaction; on failure the error is saved and Stripe
       retries later (it redelivers for up to 3 days)

Runs as a platform job (staff RLS context): the request has no logged-in user.
"""

import logging
from datetime import UTC, datetime

from django.db import transaction
from django.utils import timezone

from apps.platform import services as platform
from core.tenancy import tenant_context

from . import gateway, services
from .models import AddonSubscription, Invoice, StripeEvent, Subscription

log = logging.getLogger(__name__)


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value else None


def handle(payload: bytes, signature: str) -> str:
    event = gateway.construct_event(payload, signature)
    with tenant_context(staff=True):
        row, created = StripeEvent.objects.get_or_create(
            event_id=event["id"], defaults={"type": event["type"], "payload": event}
        )
        if not created and row.processed_at:
            return "duplicate"
    try:
        with tenant_context(staff=True):
            dispatch(event)
            StripeEvent.objects.filter(pk=row.pk).update(processed_at=timezone.now(), error="")
    except Exception as exc:
        log.exception("stripe event %s failed", event["id"])
        with tenant_context(staff=True):
            StripeEvent.objects.filter(pk=row.pk).update(error=str(exc)[:2000])
        raise
    return "processed"


def dispatch(event: dict) -> None:
    obj = event["data"]["object"]
    kind = event["type"]
    meta = obj.get("metadata") or {}
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        _session_completed(obj, meta)
    elif kind == "checkout.session.expired" and meta.get("kind") == "order":
        services.expire_order(order_id=meta["id"])
    elif kind.startswith("customer.subscription."):
        _subscription_changed(obj, meta)
    elif kind == "invoice.paid":
        _invoice_paid(obj)
    # every other event type is stored and ignored


def _session_completed(session: dict, meta: dict) -> None:
    if meta.get("kind") == "order":
        if session.get("payment_status") != "paid":
            return  # e.g. bank transfer still pending: async_payment_succeeded follows
        services.fulfil_order(
            order_id=meta["id"],
            payment_intent=session.get("payment_intent") or "",
            amount_minor=session.get("amount_total"),
            currency=session.get("currency") or "",
        )
    elif meta.get("kind") in ("subscription", "addon"):
        model = Subscription if meta["kind"] == "subscription" else AddonSubscription
        model.objects.filter(pk=meta["id"], stripe_subscription_id__isnull=True).update(
            stripe_subscription_id=session.get("subscription"), updated_at=timezone.now()
        )
        services.remember_customer(
            kind=meta["kind"], row_id=meta["id"], customer=session.get("customer") or ""
        )


def _period_end(sub: dict):
    # Newer Stripe API versions keep the period on each subscription item
    end = sub.get("current_period_end")
    if end is None:
        items = (sub.get("items") or {}).get("data") or []
        end = max((i.get("current_period_end") or 0) for i in items) if items else None
    return _ts(end)


@transaction.atomic
def _subscription_changed(sub: dict, meta: dict) -> None:
    model = AddonSubscription if meta.get("kind") == "addon" else Subscription
    row = model.objects.select_for_update().filter(stripe_subscription_id=sub["id"]).first()
    if row is None and meta.get("id"):
        row = model.objects.select_for_update().filter(pk=meta["id"]).first()
    if row is None:
        log.warning("subscription %s not ours", sub["id"])
        return
    row.stripe_subscription_id = sub["id"]
    row.status = sub.get("status", row.status)
    row.current_period_end = _period_end(sub) or row.current_period_end
    fields = ["stripe_subscription_id", "status", "current_period_end", "updated_at"]
    if model is Subscription:
        row.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
        row.canceled_at = _ts(sub.get("canceled_at"))
        items = (sub.get("items") or {}).get("data") or []
        if items and items[0].get("quantity"):
            row.seats = items[0]["quantity"]
        fields += ["cancel_at_period_end", "canceled_at", "seats"]
    row.save(update_fields=fields)
    active = row.status in ("trialing", "active", "past_due")
    ends = row.current_period_end if active else timezone.now()
    if model is Subscription:
        services.sync_subscription_access(row.id, ends)
        feature = "business" if row.plan.audience == "team" else "personal_plan"
        source, seats = "subscription", row.seats
    else:
        feature, source, seats = row.addon.code, "addon", None
    platform.sync_entitlement(
        feature=feature, source=source, source_ref=row.id, active=active, ends_at=ends,
        org_id=row.org_id, user_id=None if row.org_id else row.user_id, seats_count=seats,
    )  # fmt: skip


def _invoice_paid(inv: dict) -> None:
    sub_id = inv.get("subscription") or (
        ((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )
    sub = Subscription.objects.filter(stripe_subscription_id=sub_id).first() if sub_id else None
    if sub is None:
        return
    Invoice.objects.update_or_create(
        stripe_invoice_id=inv["id"],
        defaults={
            "user_id": sub.user_id,
            "org_id": sub.org_id,
            "subscription": sub,
            "number": inv.get("number") or "",
            "currency_id": (inv.get("currency") or sub.currency_id).upper(),
            "amount_minor": inv.get("amount_paid") or 0,
            "status": inv.get("status") or "paid",
            "hosted_url": inv.get("hosted_invoice_url") or "",
            "pdf_url": inv.get("invoice_pdf") or "",
            "issued_at": _ts(inv.get("created")) or timezone.now(),
        },
    )
