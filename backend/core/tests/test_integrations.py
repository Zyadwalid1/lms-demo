"""Integrations: Microsoft Graph email, certificate PDFs, subscriptions and the billing
portal, and sign-in through allauth headless."""

import json
from unittest import mock

import httpx
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.commerce import webhooks
from apps.commerce.models import Plan, PlanPrice, Subscription
from apps.identity.models import User
from apps.org import services as org_services
from apps.org.models import Organization, OrgMember
from core.mail import GraphEmailBackend
from core.tenancy import tenant_context
from core.tests import factories as f
from core.tests.base import SchemaTransactionTestCase

GRAPH = {
    "GRAPH_TENANT_ID": "t",
    "GRAPH_CLIENT_ID": "c",
    "GRAPH_CLIENT_SECRET": "s",
    "GRAPH_SENDER": "no-reply@kbc.test",
}


@override_settings(**GRAPH, MAIL_ALLOWED_DOMAINS={"kbc.test"})
class GraphMailTest(SchemaTransactionTestCase):
    def test_token_cached_allowlist_and_one_retry_on_401(self):
        cache.clear()
        calls = []

        def handler(request: httpx.Request):
            calls.append(request)
            if "oauth2" in str(request.url):
                return httpx.Response(200, json={"access_token": f"tok{len(calls)}", "expires_in": 3600})
            sends = [c for c in calls if "sendMail" in str(c.url)]
            if len(sends) == 2:  # the second message: token expired early once
                return httpx.Response(401)
            return httpx.Response(202)

        GraphEmailBackend.transport = httpx.MockTransport(handler)
        try:
            backend = GraphEmailBackend()
            msgs = [
                mail.EmailMessage("Hi", "Body", to=["staff@kbc.test", "customer@gmail.com"]),
                mail.EmailMessage("Again", "Body 2", to=["staff@kbc.test"]),
                mail.EmailMessage("Nobody", "x", to=["someone@gmail.com"]),  # entirely outside the allow-list
            ]
            self.assertEqual(backend.send_messages(msgs), 2)
        finally:
            GraphEmailBackend.transport = None
        token_calls = [c for c in calls if "oauth2" in str(c.url)]
        self.assertEqual(len(token_calls), 2)  # once, then once more after the 401
        first_send = next(c for c in calls if "sendMail" in str(c.url))
        self.assertIn("/users/no-reply@kbc.test/sendMail", str(first_send.url))
        body = json.loads(first_send.content)
        self.assertEqual(
            [r["emailAddress"]["address"] for r in body["message"]["toRecipients"]], ["staff@kbc.test"]
        )
        self.assertEqual(first_send.headers["Authorization"], "Bearer tok1")


class CertificatePdfTest(SchemaTransactionTestCase):
    def test_pdf_is_private_and_verifiable(self):
        staff, teacher, sara, omar = f.users()
        f.money(staff)
        course = f.course(staff=staff, owner=teacher, slug="git", title="Git Basics", free=True)
        from apps.learning import services as learning

        with tenant_context(user_id=sara.id):
            e = learning.enrol(user=sara, course=course, source="free")
            cert = learning.complete_course(e)
        self.client.force_login(sara)
        r = self.client.get(f"/api/v1/learning/certificates/{cert.id}/pdf")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn(cert.verification_code, r["Content-Disposition"])
        self.client.force_login(omar)
        self.assertEqual(self.client.get(f"/api/v1/learning/certificates/{cert.id}/pdf").status_code, 404)


class BillingTest(SchemaTransactionTestCase):
    def test_company_subscription_customer_reuse_and_portal(self):
        staff, _, sara, _ = f.users()
        f.money(staff)
        hr = User.objects.create_user("hana@acme.example.com", "x")
        acme = org_services.create_organization(name="Acme", slug="acme", owner=hr)
        H = {"HTTP_X_ORG_ID": str(acme.id)}
        with tenant_context(org_id=acme.id, user_id=hr.id):
            OrgMember.objects.create(org=acme, user=sara, joined_at=timezone.now())
        with tenant_context(user_id=staff.id, staff=True):
            team = Plan.objects.create(
                code="team", name="Team", audience="team", interval="year", min_seats=5
            )
            PlanPrice.objects.create(
                plan=team, currency_id="GBP", amount_minor=36000, stripe_price_id="price_team"
            )
        body = {"plan_id": str(team.id), "currency": "GBP", "seats": 10}
        session = mock.patch("apps.commerce.gateway.create_checkout_session",
                             side_effect=lambda **kw: {"id": f"cs_{kw['metadata']['id']}", "url": "https://stripe.test/c"})  # fmt: skip

        self.client.force_login(sara)  # a learner cannot buy for the company
        with session:
            self.assertEqual(self.client.post("/api/v1/commerce/subscriptions", data=body,
                                              content_type="application/json", **H).status_code, 403)  # fmt: skip
        self.client.force_login(hr)
        with session as checkout:
            r = self.client.post(
                "/api/v1/commerce/subscriptions", data=body, content_type="application/json", **H
            )
            self.assertEqual(r.json()["checkout_url"], "https://stripe.test/c")
            self.assertEqual(
                checkout.call_args.kwargs["line_items"], [{"price": "price_team", "quantity": 10}]
            )
        sub_id = r.json()["subscription_id"]
        with mock.patch("apps.commerce.gateway.construct_event", return_value={
            "id": "evt_1", "type": "checkout.session.completed",
            "data": {"object": {"subscription": "sub_1", "customer": "cus_acme",
                                "metadata": {"kind": "subscription", "id": sub_id}}}}):  # fmt: skip
            webhooks.handle(b"{}", "sig")
        with tenant_context(user_id=staff.id, staff=True):
            self.assertEqual(Organization.objects.get(pk=acme.id).stripe_customer_id, "cus_acme")
            self.assertEqual(Subscription.objects.get(pk=sub_id).stripe_subscription_id, "sub_1")
        with mock.patch(
            "apps.commerce.gateway.billing_portal", return_value="https://billing.stripe.test/p"
        ) as portal:
            r = self.client.post("/api/v1/commerce/billing-portal", **H)
        self.assertEqual(r.json()["url"], "https://billing.stripe.test/p")
        self.assertEqual(portal.call_args.kwargs["customer"], "cus_acme")
        with mock.patch("apps.commerce.gateway.cancel_at_period_end") as cancel:
            self.client.post(f"/api/v1/commerce/subscriptions/{sub_id}/cancel", **H)
        cancel.assert_called_once_with("sub_1")


class SignInTest(SchemaTransactionTestCase):
    def test_headless_login_requires_a_verified_email(self):
        u = User.objects.create_user("sara@learnhub.example.com", "Correct-Horse-9", full_name="Sara")
        self.client.get("/api/v1/identity/csrf")
        login = {"email": "sara@learnhub.example.com", "password": "Correct-Horse-9"}
        bad = self.client.post("/_allauth/browser/v1/auth/login", data={**login, "password": "nope"},
                               content_type="application/json")  # fmt: skip
        self.assertEqual(bad.status_code, 400)
        r = self.client.post("/_allauth/browser/v1/auth/login", data=login, content_type="application/json")
        self.assertEqual(r.status_code, 401)  # pending email verification
        self.assertTrue(
            any("verify" in m.subject.lower() or "confirm" in m.subject.lower() for m in mail.outbox)
        )
        EmailAddress.objects.update_or_create(
            user=u, email=u.email, defaults={"verified": True, "primary": True}
        )
        r = self.client.post("/_allauth/browser/v1/auth/login", data=login, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/identity/me").json()["email"], u.email)
        config = self.client.get("/_allauth/browser/v1/config").json()
        providers = config["data"].get("socialaccount", {}).get("providers", [])
        self.assertEqual(providers, [])  # none configured here: no dead buttons


@override_settings(AZURE_STORAGE={"ACCOUNT": "acct", "CONTAINER": "lms-resources", "TENANT_ID": "t",
                                  "CLIENT_ID": "c", "CLIENT_SECRET": "s"})  # fmt: skip
class AzureStorageTest(SchemaTransactionTestCase):
    def test_signed_links_use_a_cached_delegation_key(self):
        from urllib.parse import parse_qs, urlparse

        from core import storage

        cache.clear()
        calls = []
        udk = ("<UserDelegationKey><SignedOid>o</SignedOid><SignedTid>t</SignedTid>"
               "<SignedStart>2026-11-06T00:00:00Z</SignedStart><SignedExpiry>2026-11-08T00:00:00Z</SignedExpiry>"
               "<SignedService>b</SignedService><SignedVersion>2022-11-02</SignedVersion>"
               "<Value>a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=</Value></UserDelegationKey>")  # fmt: skip

        def handler(request: httpx.Request):
            calls.append(str(request.url))
            if "oauth2" in str(request.url):
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
            self.assertEqual(request.headers["Authorization"], "Bearer tok")
            return httpx.Response(200, text=udk)

        storage.transport = httpx.MockTransport(handler)
        try:
            down = storage.download_url("courses/x/notes v2.pdf", "notes.pdf")
            up = storage.upload_url("courses/x/notes v2.pdf")
        finally:
            storage.transport = None
        self.assertEqual(len(calls), 2)  # one token, one delegation key, then cached
        self.assertTrue(
            down.startswith("https://acct.blob.core.windows.net/lms-resources/courses/x/notes%20v2.pdf?")
        )
        q = {k: v[0] for k, v in parse_qs(urlparse(down).query).items()}
        self.assertEqual((q["sp"], q["sr"], q["spr"], q["skoid"]), ("r", "b", "https", "o"))
        self.assertIn('filename="notes.pdf"', q["rscd"])
        self.assertEqual(parse_qs(urlparse(up).query)["sp"], ["cw"])


@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x")
class StripeSetupTest(SchemaTransactionTestCase):
    def test_creates_real_prices_once_and_never_uses_live_keys(self):
        from io import StringIO
        from types import SimpleNamespace as NS

        from django.core.management import CommandError, call_command

        staff, *_ = f.users()
        f.money(staff)
        with tenant_context(user_id=staff.id, staff=True):
            plan = Plan.objects.create(
                code="team", name="Team", audience="team", interval="year", min_seats=5
            )
            pp = PlanPrice.objects.create(plan=plan, currency_id="GBP", amount_minor=36000,
                                          stripe_price_id="price_demo_team_gbp")  # fmt: skip
        stripe_prices = {}

        def list_prices(params):
            p = stripe_prices.get(params["lookup_keys"][0])
            return NS(data=[p] if p else [])

        def create_price(params):
            p = NS(id=f"price_{len(stripe_prices) + 1}", unit_amount=params["unit_amount"],
                   recurring=NS(interval=params["recurring"]["interval"]))  # fmt: skip
            stripe_prices[params["lookup_key"]] = p
            return p

        client = mock.MagicMock()
        client.v1.prices.list.side_effect = list_prices
        client.v1.prices.create.side_effect = create_price
        client.v1.products.retrieve.side_effect = Exception("missing")
        with mock.patch("apps.commerce.gateway._client", return_value=client):
            call_command("stripe_setup", stdout=StringIO())
            call_command("stripe_setup", stdout=StringIO())  # second run reuses
            with override_settings(STRIPE_SECRET_KEY="sk_live_x"), self.assertRaises(CommandError):
                call_command("stripe_setup", stdout=StringIO())
        self.assertEqual(client.v1.prices.create.call_count, 1)
        created = client.v1.prices.create.call_args.kwargs["params"]
        self.assertEqual((created["unit_amount"], created["currency"], created["lookup_key"]),
                         (36000, "gbp", "lms_plan_team_gbp"))  # fmt: skip
        with tenant_context(user_id=staff.id, staff=True):
            self.assertEqual(PlanPrice.objects.get(pk=pp.pk).stripe_price_id, "price_1")


@override_settings(**GRAPH, MAIL_ALLOWED_DOMAINS={"kbc.test"})
class CheckCommandsTest(SchemaTransactionTestCase):
    def run_mail(self, status):
        from io import StringIO

        from django.core.management import call_command

        def handler(request: httpx.Request):
            if "oauth2" in str(request.url):
                return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
            return httpx.Response(status)

        out = StringIO()
        GraphEmailBackend.transport = httpx.MockTransport(handler)
        try:
            call_command("check_mail", "me@kbc.test", stdout=out)
        finally:
            GraphEmailBackend.transport = None
        return out.getvalue()

    def test_check_mail_reports_each_step(self):
        from django.core.management import CommandError, call_command

        self.assertIn("PASS  sent to me@kbc.test", self.run_mail(202))
        self.assertIn("is not a mailbox", self.run_mail(404))
        with self.assertRaises(CommandError):  # the safety switch also guards the check
            call_command("check_mail", "someone@gmail.com")

    def test_check_bunny_needs_settings(self):
        from django.core.management import CommandError, call_command

        with override_settings(BUNNY_STREAM={**settings.BUNNY_STREAM, "LIBRARY_ID": ""}):
            with self.assertRaises(CommandError):
                call_command("check_bunny")
