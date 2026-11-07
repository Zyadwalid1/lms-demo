"""Console > Dashboard (mockup 26): KPIs, sales, approvals, attention, activity, health."""

from datetime import date, timedelta
from uuid import UUID

from django.db.models import Count, Sum
from django.utils import timezone
from ninja import Schema

from apps.catalog.models import CourseVersion
from apps.commerce import pricing
from apps.commerce.models import Order, StripeEvent, Subscription
from apps.engagement.models import Ticket
from apps.identity.models import InstructorProfile, User
from apps.org.models import Organization
from apps.payouts.models import Payout

from ..models import OutboxEvent, WebhookEvent
from .common import router, staff


class ConsoleOverviewOut(Schema):
    users: int
    new_users_30d: int
    orders_30d: int
    revenue_30d_gbp_minor: int
    active_subscriptions: int
    companies: int
    courses_in_review: int
    instructors_pending: int
    tickets_open: int
    payouts_pending: int


class ConsoleOutboxFailOut(Schema):
    id: UUID
    topic: str
    attempts: int
    last_error: str


class ConsoleStripeFailOut(Schema):
    event_id: str
    type: str
    error: str


class ConsoleHealthOut(Schema):
    outbox_pending: int
    outbox_stuck: int
    outbox_failing: list[ConsoleOutboxFailOut]
    stripe_failing: list[ConsoleStripeFailOut]
    webhooks_unprocessed: int
    fx_latest: date | None


@router.get("/overview", response=ConsoleOverviewOut)
def overview(request):
    staff(request)
    month = timezone.now() - timedelta(days=30)
    revenue = Order.objects.filter(status__in=["paid", "partially_refunded"], paid_at__gte=month).aggregate(
        orders=Count("id"), gbp=Sum("gbp_total_minor")
    )
    return {
        "users": User.objects.filter(is_active=True).count(),
        "new_users_30d": User.objects.filter(created_at__gte=month).count(),
        "orders_30d": revenue["orders"], "revenue_30d_gbp_minor": revenue["gbp"] or 0,
        "active_subscriptions": Subscription.objects.filter(status__in=["active", "trialing"]).count(),
        "companies": Organization.objects.exclude(status="cancelled").count(),
        "courses_in_review": CourseVersion.objects.filter(status="in_review").count(),
        "instructors_pending": InstructorProfile.objects.filter(status="pending").count(),
        "tickets_open": Ticket.objects.filter(status="open").count(),
        "payouts_pending": Payout.objects.filter(status="pending").count(),
    }  # fmt: skip


@router.get("/health", response=ConsoleHealthOut)
def health(request):
    """Background machinery: anything stuck or failing shows up here."""
    staff(request)
    stuck = timezone.now() - timedelta(minutes=10)
    return {
        "outbox_pending": OutboxEvent.objects.filter(processed_at__isnull=True).count(),
        "outbox_stuck": OutboxEvent.objects.filter(processed_at__isnull=True, created_at__lt=stuck).count(),
        "outbox_failing": list(OutboxEvent.objects.filter(processed_at__isnull=True, attempts__gt=0)
                               .values("id", "topic", "attempts", "last_error")[:20]),
        "stripe_failing": list(StripeEvent.objects.filter(processed_at__isnull=True).exclude(error="")
                               .values("event_id", "type", "error")[:20]),
        "webhooks_unprocessed": WebhookEvent.objects.filter(processed_at__isnull=True, created_at__lt=stuck).count(),
        "fx_latest": pricing.FxRate.objects.order_by("-rate_date").values_list("rate_date", flat=True).first(),
    }  # fmt: skip
