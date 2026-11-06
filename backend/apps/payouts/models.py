"""Payouts: money out to marketplace instructors.

Postgres schema: payouts. Amounts are integer pence (GBP, the platform base currency).

    revenue_shares    reference: % of a sale the instructors earn, per channel
    payout_accounts   where an instructor is paid (Stripe Connect or PayPal), verified by staff
    earnings          append-only ledger, one line per instructor per sale / refund / month
                      of subscription minutes. A refund is a NEGATIVE line, never an edit.
    payouts           a monthly bundle of available earnings, approved by staff

RLS (core.rls.personal_readonly): instructors READ their own rows; only platform jobs
and staff write. A bug in an instructor endpoint can never create or change earnings.
Only instructor-owned marketplace courses earn: platform and company courses do not.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.db import table
from core.models import BaseModel

SCHEMA = "payouts"
User = settings.AUTH_USER_MODEL


class RevenueShare(BaseModel):
    class Channel(models.TextChoices):
        MARKETPLACE = "marketplace", "Marketplace sale"
        INSTRUCTOR_COUPON = "instructor_coupon", "Sale through the instructor's own coupon"
        SUBSCRIPTION_POOL = "subscription_pool", "Share of personal-plan revenue"

    channel = models.CharField(max_length=20, choices=Channel.choices, unique=True)
    instructor_bps = models.PositiveIntegerField()  # 3700 = 37%

    class Meta:
        db_table = table(SCHEMA, "revenue_shares")
        constraints = [models.CheckConstraint(condition=Q(instructor_bps__lte=10000), name="ck_share_bps")]


class PayoutAccount(BaseModel):
    class Method(models.TextChoices):
        STRIPE = "stripe", "Stripe Connect"
        PAYPAL = "paypal", "PayPal"

    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="payout_account")
    method = models.CharField(max_length=8, choices=Method.choices)
    stripe_account_id = models.CharField(max_length=64, blank=True)
    paypal_email = models.EmailField(max_length=320, blank=True)
    country = models.CharField(max_length=2, blank=True)
    tax_form_received_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)  # staff check; reset on any change

    class Meta:
        db_table = table(SCHEMA, "payout_accounts")


class Payout(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting approval"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        HELD = "held", "On hold"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", db_index=False)
    period_end = models.DateField()  # the month this run closed
    amount_gbp_minor = models.PositiveIntegerField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    method = models.CharField(max_length=8, choices=PayoutAccount.Method.choices)
    provider_ref = models.CharField(max_length=128, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    paid_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = table(SCHEMA, "payouts")
        constraints = [models.UniqueConstraint(fields=["user", "period_end"], name="uq_payout_month")]
        indexes = [
            models.Index(fields=["user", "-period_end"], name="ix_payouts_user"),
            models.Index(fields=["status", "period_end"], name="ix_payouts_status"),
        ]


class Earning(BaseModel):
    class Kind(models.TextChoices):
        SALE = "sale", "Sale"
        REFUND = "refund", "Refund"
        SUBSCRIPTION = "subscription", "Personal-plan minutes"
        ADJUSTMENT = "adjustment", "Adjustment by staff"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", db_index=False)  # instructor
    kind = models.CharField(max_length=12, choices=Kind.choices)
    course = models.ForeignKey("catalog.Course", on_delete=models.PROTECT, related_name="+")
    order_item = models.ForeignKey(
        "commerce.OrderItem", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    period = models.DateField(null=True, blank=True)  # first day of the month (subscription lines)
    channel = models.CharField(max_length=20, choices=RevenueShare.Channel.choices)
    gross_gbp_minor = models.IntegerField()  # this instructor's part of what the customer paid
    share_bps = models.PositiveIntegerField()
    amount_gbp_minor = models.IntegerField()  # signed: refunds are negative
    earned_at = models.DateTimeField()
    available_at = models.DateTimeField()  # after the refund window
    payout = models.ForeignKey(
        Payout, on_delete=models.PROTECT, null=True, blank=True, related_name="earnings"
    )
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = table(SCHEMA, "earnings")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "order_item", "kind"],
                condition=Q(order_item__isnull=False),
                name="uq_earning_item",
            ),
            models.UniqueConstraint(
                fields=["user", "course", "period"],
                condition=Q(kind="subscription"),
                name="uq_earning_sub_month",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-earned_at"], name="ix_earnings_user"),
            models.Index(
                fields=["user", "available_at"], name="ix_earnings_unpaid", condition=Q(payout__isnull=True)
            ),
            models.Index(fields=["course", "earned_at"], name="ix_earnings_course"),
        ]
