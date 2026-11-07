"""Instructor earnings and payouts. Every write here runs as a platform job (staff
RLS context): instructors can only read their own ledger.

Ledger rules:
  * one line per instructor per sale, written when the order is paid (signal)
  * a refund adds a negative line; nothing is ever edited or deleted
  * lines become payable after the refund window (available_at)
  * the monthly run bundles everything payable into one payout per instructor,
    if the balance reaches the minimum; staff approve before money moves
"""

import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import Course, CourseInstructor
from apps.commerce import gateway, pricing
from apps.commerce.models import Order, OrderItem
from core.errors import ServiceError
from core.tenancy import tenant_context

from .models import Earning, Payout, PayoutAccount, RevenueShare

C = RevenueShare.Channel


def _rates() -> dict[str, int]:
    return dict(RevenueShare.objects.values_list("channel", "instructor_bps"))


# ---------------------------------------------------------------- platform fee (basic, set by staff)
def default_fee_bps() -> int:
    """The platform's default cut of a marketplace sale (the marketplace channel's rest)."""
    share = (
        RevenueShare.objects.filter(channel=C.MARKETPLACE).values_list("instructor_bps", flat=True).first()
    )
    return 10000 - (share if share is not None else 10000)


def instructor_fees(user_ids) -> dict:
    """{user_id: platform fee bps} for instructors with their own fee (others use the default)."""
    from apps.identity.models import InstructorProfile

    return dict(
        InstructorProfile.objects.filter(user_id__in=user_ids, platform_fee_bps__isnull=False).values_list(
            "user_id", "platform_fee_bps"
        )
    )


def set_default_fee(*, fee_bps: int) -> None:
    """Changes the default for instructors approved FROM NOW ON (and anyone without a fee of
    their own). Instructors already approved keep the fee they were given."""
    if not 0 <= fee_bps <= 10000:
        raise ServiceError("bad_fee", "The fee must be between 0% and 100%.")
    RevenueShare.objects.update_or_create(channel=C.MARKETPLACE, defaults={"instructor_bps": 10000 - fee_bps})


def set_instructor_fee(*, user_id, fee_bps: int | None) -> None:
    """One instructor's own fee; None = follow the platform default."""
    from apps.identity.models import InstructorProfile

    if fee_bps is not None and not 0 <= fee_bps <= 10000:
        raise ServiceError("bad_fee", "The fee must be between 0% and 100%.")
    if not InstructorProfile.objects.filter(user_id=user_id).update(
        platform_fee_bps=fee_bps, updated_at=timezone.now()
    ):
        raise ServiceError("not_found", "Instructor not found.", status=404)


def _weights(course_ids) -> dict:
    """{course_id: [(user_id, weight 0..1)]}; equal split when no shares are set."""
    links: dict = {}
    for cid, uid, bps in CourseInstructor.objects.filter(course_id__in=course_ids).values_list(
        "course_id", "user_id", "revenue_share_bps"
    ):
        links.setdefault(cid, []).append((uid, bps))
    out = {}
    for cid, rows in links.items():
        total = sum(b for _, b in rows)
        out[cid] = [(u, Decimal(b) / total if total else Decimal(1) / len(rows)) for u, b in rows]
    return out


# ---------------------------------------------------------------- ledger
def record_sale(order_id) -> int:
    """Called after an order is paid. Idempotent (unique per instructor and item)."""
    with tenant_context(staff=True):
        order = Order.objects.select_related("coupon").get(pk=order_id)
        items = list(
            OrderItem.objects.filter(
                order=order, gbp_gross_minor__gt=0, course__ownership=Course.Ownership.INSTRUCTOR
            )
        )
        if not items:
            return 0
        rates, weights = _rates(), _weights([i.course_id for i in items])
        fees = instructor_fees({u for ws in weights.values() for u, _ in ws})
        available = order.paid_at + timedelta(days=settings.REFUND_WINDOW_DAYS)
        lines = []
        for item in items:
            instructors = weights.get(item.course_id, [])
            own_coupon = order.coupon and any(u == order.coupon.created_by_id for u, _ in instructors)
            channel = C.INSTRUCTOR_COUPON if own_coupon else C.MARKETPLACE
            for user_id, w in instructors:
                gross = int(item.gbp_gross_minor * w)
                # an instructor's own fee replaces the default on marketplace sales; the rate is
                # stored on the line, so later fee changes never rewrite past earnings
                bps = (
                    10000 - fees[user_id] if channel == C.MARKETPLACE and user_id in fees else rates[channel]
                )
                lines.append(
                    Earning(
                        user_id=user_id,
                        kind=Earning.Kind.SALE,
                        course_id=item.course_id,
                        order_item=item,
                        channel=channel,
                        gross_gbp_minor=gross,
                        share_bps=bps,
                        amount_gbp_minor=gross * bps // 10000,
                        earned_at=order.paid_at,
                        available_at=available,
                    )  # fmt: skip
                )
        return len(Earning.objects.bulk_create(lines, ignore_conflicts=True))


def record_refund(item_id) -> int:
    """A negative line for every sale line of the refunded item. If the sale was not
    paid out yet, both land in the same payout and cancel; if it was, the next payout
    is reduced."""
    now = timezone.now()
    with tenant_context(staff=True):
        sales = list(Earning.objects.filter(order_item_id=item_id, kind=Earning.Kind.SALE))
        lines = [
            Earning(
                user_id=s.user_id,
                kind=Earning.Kind.REFUND,
                course_id=s.course_id,
                order_item_id=item_id,
                channel=s.channel,
                gross_gbp_minor=-s.gross_gbp_minor,
                share_bps=s.share_bps,
                amount_gbp_minor=-s.amount_gbp_minor,
                earned_at=now,
                available_at=s.available_at if s.payout_id is None else now,
            )  # fmt: skip
            for s in sales
        ]
        return len(Earning.objects.bulk_create(lines, ignore_conflicts=True))


def _month_bounds(month: date) -> tuple[datetime, datetime]:
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    days = calendar.monthrange(month.year, month.month)[1]
    return start, start + timedelta(days=days)


def settle_subscription_pool(month: date) -> int:
    """Personal-plan revenue of the month x pool share, split by seconds watched on
    instructor courses through plan enrolments. Two aggregate queries, any volume."""
    start, end = _month_bounds(month)
    with tenant_context(staff=True), connection.cursor() as cur:
        if Earning.objects.filter(kind=Earning.Kind.SUBSCRIPTION, period=month.replace(day=1)).exists():
            return 0  # already settled (the unique constraint also guards a parallel run)
        cur.execute(
            """
            SELECT i.currency, i.issued_at::date, sum(i.amount_minor)
              FROM commerce.invoices i
              JOIN commerce.subscriptions s ON s.id = i.subscription_id
              JOIN commerce.plans p ON p.id = s.plan_id AND p.audience = 'personal'
             WHERE i.issued_at >= %s AND i.issued_at < %s AND i.status = 'paid'
             GROUP BY 1, 2
            """,
            [start, end],
        )
        revenue_rows = cur.fetchall()
        cur.execute("SELECT code, exponent FROM commerce.currencies")
        exps = dict(cur.fetchall())
        revenue = sum(
            pricing.gbp_equivalent(amount, exps[code], pricing.latest_rate(code, day))
            for code, day, amount in revenue_rows
        )
        cur.execute(
            """
            SELECT pe.course_id, sum(pe.seconds)
              FROM learning.progress_events pe
              JOIN learning.enrollments e ON e.id = pe.enrollment_id AND e.source = 'subscription'
              JOIN catalog.courses c ON c.id = pe.course_id AND c.ownership = 'instructor'
             WHERE pe.created_at >= %s AND pe.created_at < %s
             GROUP BY 1
            """,
            [start, end],
        )
        seconds = dict(cur.fetchall())
        total = sum(seconds.values())
        if not revenue or not total:
            return 0
        bps = _rates()[C.SUBSCRIPTION_POOL]
        weights = _weights(list(seconds))
        lines = []
        for course_id, secs in seconds.items():
            course_revenue = Decimal(revenue) * secs / total
            for user_id, w in weights.get(course_id, []):
                gross = int(course_revenue * w)
                lines.append(
                    Earning(
                        user_id=user_id,
                        kind=Earning.Kind.SUBSCRIPTION,
                        course_id=course_id,
                        period=month.replace(day=1),
                        channel=C.SUBSCRIPTION_POOL,
                        gross_gbp_minor=gross,
                        share_bps=bps,
                        amount_gbp_minor=gross * bps // 10000,
                        earned_at=end,
                        available_at=end,
                        note=f"{secs // 60} minutes watched",
                    )  # fmt: skip
                )
        return len(Earning.objects.bulk_create(lines, ignore_conflicts=True))


# ---------------------------------------------------------------- payouts
def create_payouts(*, period_end: date, now=None) -> list:
    """One payout per verified instructor whose payable balance reaches the minimum.
    A single statement bundles the lines, so a line can never be in two payouts."""
    now = now or timezone.now()
    with tenant_context(staff=True), connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('payouts:run', 0))")
        cur.execute(
            """
            WITH due AS (
                SELECT e.user_id, sum(e.amount_gbp_minor) AS total
                  FROM payouts.earnings e
                 WHERE e.payout_id IS NULL AND e.available_at <= %(now)s
                 GROUP BY e.user_id
                HAVING sum(e.amount_gbp_minor) >= %(min)s
            ), made AS (
                INSERT INTO payouts.payouts
                       (id, created_at, updated_at, user_id, period_end, amount_gbp_minor, status, method,
                        provider_ref, failure_reason)
                SELECT uuidv7(), %(now)s, %(now)s, d.user_id, %(period)s, d.total, 'pending', a.method, '', ''
                  FROM due d
                  JOIN payouts.payout_accounts a ON a.user_id = d.user_id AND a.verified_at IS NOT NULL
                ON CONFLICT (user_id, period_end) DO NOTHING
                RETURNING id, user_id
            )
            UPDATE payouts.earnings e SET payout_id = made.id, updated_at = %(now)s
              FROM made
             WHERE e.user_id = made.user_id AND e.payout_id IS NULL AND e.available_at <= %(now)s
            RETURNING made.id
            """,
            {"now": now, "min": settings.PAYOUT_MINIMUM_GBP_MINOR, "period": period_end},
        )
        return list({r[0] for r in cur.fetchall()})


@transaction.atomic
def approve_payout(*, payout: Payout, by, provider_ref: str = "") -> Payout:
    """Staff only (console). Stripe Connect transfers automatically; PayPal needs the
    reference of the payment made in PayPal."""
    payout = Payout.objects.select_for_update().get(pk=payout.pk)
    if payout.status != Payout.Status.PENDING:
        raise ServiceError("not_pending", f"Payout is {payout.status}.")
    total = payout.earnings.aggregate(t=Sum("amount_gbp_minor"))["t"] or 0
    if total != payout.amount_gbp_minor:  # defence in depth: the bundle was tampered with
        raise ServiceError("mismatch", "Payout total does not match its earnings.")
    account = PayoutAccount.objects.get(user_id=payout.user_id, verified_at__isnull=False)
    if payout.method == PayoutAccount.Method.STRIPE:
        provider_ref = gateway.transfer(
            destination=account.stripe_account_id, amount_gbp_minor=payout.amount_gbp_minor,
            idempotency_key=f"payout-{payout.id}", description=f"LearnHub payout {payout.period_end:%B %Y}",
        )  # fmt: skip
    elif not provider_ref.strip():
        raise ServiceError("reference_required", "Enter the PayPal payment reference.")
    payout.status, payout.provider_ref, payout.approved_by, payout.paid_at = (
        "paid",
        provider_ref,
        by,
        timezone.now(),
    )
    payout.save(update_fields=["status", "provider_ref", "approved_by", "paid_at", "updated_at"])
    return payout


@transaction.atomic
def fail_payout(*, payout: Payout, reason: str) -> None:
    """Release the lines so they roll into next month's payout."""
    Payout.objects.filter(pk=payout.pk, status=Payout.Status.PENDING).update(
        status=Payout.Status.FAILED, failure_reason=reason[:300], updated_at=timezone.now()
    )
    Earning.objects.filter(payout=payout).update(payout=None, updated_at=timezone.now())


def set_payout_account(
    *, user, method: str, stripe_account_id: str = "", paypal_email: str = "", country: str = ""
):
    """The instructor's own details. Any change clears verification until staff re-check."""
    if method == PayoutAccount.Method.PAYPAL and not paypal_email:
        raise ServiceError("email_required", "Enter your PayPal email.")
    if method == PayoutAccount.Method.STRIPE and not stripe_account_id.startswith("acct_"):
        raise ServiceError("bad_account", "Connect your Stripe account first.")
    with tenant_context(user_id=user.id, staff=True):  # narrow, validated write on the user's own row
        account, _ = PayoutAccount.objects.update_or_create(
            user=user,
            defaults={
                "method": method, "stripe_account_id": stripe_account_id, "paypal_email": paypal_email,
                "country": country.upper()[:2], "verified_at": None,
            },
        )  # fmt: skip
    return account


def verify_account(*, account: PayoutAccount) -> None:
    PayoutAccount.objects.filter(pk=account.pk).update(verified_at=timezone.now(), updated_at=timezone.now())


def monthly_run(today: date | None = None) -> dict:
    """1st of the month: settle last month's subscription pool, then create payouts."""
    today = today or timezone.now().date()
    last_month_end = today.replace(day=1) - timedelta(days=1)
    pool = settle_subscription_pool(last_month_end.replace(day=1))
    made = create_payouts(period_end=last_month_end)
    return {"subscription_lines": pool, "payouts": len(made)}
