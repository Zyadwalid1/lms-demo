"""Instructor revenue screens (studio). RLS limits every query to the instructor's own rows."""

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Earning, Payout


def balance(*, user_id) -> dict:
    """One query: payable now, still in the refund window, paid out to date."""
    now = timezone.now()
    unpaid = Q(payout__isnull=True)
    agg = Earning.objects.filter(user_id=user_id).aggregate(
        available=Sum("amount_gbp_minor", filter=unpaid & Q(available_at__lte=now), default=0),
        pending=Sum("amount_gbp_minor", filter=unpaid & Q(available_at__gt=now), default=0),
        paid=Sum("amount_gbp_minor", filter=Q(payout__status=Payout.Status.PAID), default=0),
    )
    return agg


def by_month(*, user_id, months: int = 12) -> list[dict]:
    since = timezone.now() - timezone.timedelta(days=31 * months)
    return list(
        Earning.objects.filter(user_id=user_id, earned_at__gte=since)
        .annotate(month=TruncMonth("earned_at"))
        .values("month", "channel")
        .annotate(amount=Sum("amount_gbp_minor"))
        .order_by("month", "channel")
    )


def by_course(*, user_id):
    return (
        Earning.objects.filter(user_id=user_id)
        .values("course_id", "course__title")
        .annotate(amount=Sum("amount_gbp_minor"))
        .order_by("-amount")
    )
