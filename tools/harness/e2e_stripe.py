"""HARNESS ONLY: deliver a Stripe webhook event for an order or subscription, through the
real webhook handler (only the signature check is bypassed)."""

import os
import sys
import time
import uuid
from unittest import mock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from apps.commerce import gateway, webhooks  # noqa: E402
from apps.commerce.models import Order, Subscription  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402


def deliver(event):
    with mock.patch("apps.commerce.gateway.construct_event", return_value=event):
        print(webhooks.handle(b"{}", "sig"))


kind, ident = sys.argv[1], sys.argv[2]
if kind == "order":
    with tenant_context(staff=True):
        o = Order.objects.select_related("currency").get(pk=ident)
        amount = gateway.to_stripe_amount(o.total_minor, o.currency_id, o.currency.exponent)
    deliver({"id": f"evt_{uuid.uuid4().hex}", "type": "checkout.session.completed", "data": {"object": {
        "payment_status": "paid", "payment_intent": f"pi_e2e_{uuid.uuid4().hex[:10]}", "amount_total": amount,
        "currency": o.currency_id.lower(), "metadata": {"kind": "order", "id": str(o.id)}}}})
else:
    sub_stripe = f"sub_e2e_{uuid.uuid4().hex[:10]}"
    deliver({"id": f"evt_{uuid.uuid4().hex}", "type": "checkout.session.completed", "data": {"object": {
        "subscription": sub_stripe, "customer": f"cus_e2e_{uuid.uuid4().hex[:8]}",
        "metadata": {"kind": "subscription", "id": ident}}}})
    deliver({"id": f"evt_{uuid.uuid4().hex}", "type": "customer.subscription.updated", "data": {"object": {
        "id": sub_stripe, "status": "trialing", "current_period_end": int(time.time()) + 7 * 86400,
        "cancel_at_period_end": False, "items": {"data": [{"quantity": 1}]},
        "metadata": {"kind": "subscription", "id": ident}}}})
