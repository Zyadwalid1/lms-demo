"""Commerce background jobs (Celery)."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from core.tenancy import tenant_context

from . import pricing
from .models import Order


@shared_task(name="commerce.refresh_fx", autoretry_for=(Exception,), retry_backoff=600, max_retries=6)
def refresh_fx_task() -> dict:
    """Daily: ECB rates, then re-price tiers that drifted."""
    with tenant_context(staff=True):  # reference tables are staff-write only
        stored = pricing.fetch_ecb()
        return {"rates": stored, "repriced": pricing.refresh_tier_amounts()}


@shared_task(name="commerce.expire_checkouts")
def expire_checkouts_task() -> int:
    """Stripe Checkout sessions last 24 h; close our side if the expiry webhook was missed."""
    cutoff = timezone.now() - timedelta(hours=25)
    with tenant_context(staff=True):
        return Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff).update(
            status=Order.Status.EXPIRED, updated_at=timezone.now()
        )
