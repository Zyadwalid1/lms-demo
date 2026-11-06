"""HARNESS ONLY (not part of the app): run Django with Stripe replaced by a local fake, so
the end-to-end tests can go through checkout without real keys. The fake 'hosted page'
sends the browser straight back to the success URL; payments are then confirmed by
tools/e2e_stripe.py delivering a webhook event, exactly as Stripe would."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

from apps.commerce import gateway  # noqa: E402


def create_checkout_session(*, mode, line_items, metadata, customer_email, success_url, cancel_url, idempotency_key, trial_days=0, customer=""):
    return {"id": f"cs_e2e_{metadata['id']}", "url": success_url}


gateway.create_checkout_session = create_checkout_session
gateway.refund = lambda *, payment_intent, amount, idempotency_key: f"re_e2e_{idempotency_key[:12]}"
gateway.billing_portal = lambda *, customer, return_url: return_url
gateway.cancel_at_period_end = lambda subscription_id: None
