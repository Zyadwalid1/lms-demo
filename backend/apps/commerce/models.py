"""Commerce: money in (decisions 9 and 10).

Postgres schema: commerce. Money is always an integer in the currency's MINOR unit
(pence, cents; yen have none, dinars have three: Currency.exponent). Never floats.

    GLOBAL (no RLS, written only by staff endpoints and jobs)
        currencies, fx_rates            every ISO currency; ECB rates daily, manual for the rest
        price_tiers, price_tier_amounts Udemy-style tiers: a GBP base and a per-currency
                                        amount (auto from FX with natural rounding, or locked by admin)
        course_prices                   a course is free or uses a tier
        promotions, coupons             site-wide sales; instructor or staff coupon codes
        plans, plan_prices              personal and team subscriptions
        addons, addon_prices            e.g. content protection (DRM library)
    PERSONAL (core.rls.personal)        cart_items, wishlist_items
    MIXED (core.rls.mixed)              orders, order_items, payments, refunds, coupon_redemptions,
                                        subscriptions, addon_subscriptions, invoices
                                        (org_id set = bought by a company)
    STAFF ONLY (core.rls.staff_only)    stripe_events (raw webhooks, idempotency)

Enrolment happens only after Stripe's signed webhook says the money arrived.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.db import table
from core.models import BaseModel, MixedTenantModel

SCHEMA = "commerce"
User = settings.AUTH_USER_MODEL


def currency_fk(**kw):
    return models.ForeignKey(
        "commerce.Currency",
        to_field="code",
        db_column=kw.pop("db_column", "currency"),
        on_delete=models.PROTECT,
        related_name="+",
        **kw,
    )


# ======================================================================= global
class Currency(BaseModel):
    class RateSource(models.TextChoices):
        ECB = "ecb", "European Central Bank (daily)"
        MANUAL = "manual", "Entered by an admin"

    code = models.CharField(max_length=3, unique=True)  # ISO 4217
    name = models.CharField(max_length=80)
    exponent = models.PositiveSmallIntegerField(default=2)  # minor units: GBP 2, JPY 0, KWD 3
    stripe_supported = models.BooleanField(default=True)
    rate_source = models.CharField(max_length=8, choices=RateSource.choices, default=RateSource.MANUAL)
    is_active = models.BooleanField(default=False)  # offered at checkout

    class Meta:
        db_table = table(SCHEMA, "currencies")
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class FxRate(BaseModel):
    """Units of `currency` for 1 GBP on rate_date (the platform base currency)."""

    currency = currency_fk()
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    source = models.CharField(max_length=8, choices=Currency.RateSource.choices)

    class Meta:
        db_table = table(SCHEMA, "fx_rates")
        constraints = [models.UniqueConstraint(fields=["currency", "rate_date"], name="uq_fx_day")]
        indexes = [models.Index(fields=["currency", "-rate_date"], name="ix_fx_latest")]


class PriceTier(BaseModel):
    name = models.CharField(max_length=40, unique=True)  # "Tier 5"
    gbp_minor = models.PositiveIntegerField()  # base price in pence
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = table(SCHEMA, "price_tiers")
        ordering = ["sort_order", "gbp_minor"]

    def __str__(self) -> str:
        return self.name


class PriceTierAmount(BaseModel):
    """The price shown in a currency. Recomputed from FX only when it drifts > 5%,
    so prices stay stable; is_locked = an admin set it by hand and FX never touches it."""

    tier = models.ForeignKey(PriceTier, on_delete=models.CASCADE, related_name="amounts")
    currency = currency_fk()
    amount_minor = models.PositiveIntegerField()
    is_locked = models.BooleanField(default=False)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "price_tier_amounts")
        constraints = [models.UniqueConstraint(fields=["tier", "currency"], name="uq_tier_currency")]


class CoursePrice(BaseModel):
    course = models.OneToOneField("catalog.Course", on_delete=models.CASCADE, related_name="price")
    tier = models.ForeignKey(PriceTier, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    is_free = models.BooleanField(default=False)

    class Meta:
        db_table = table(SCHEMA, "course_prices")
        constraints = [
            models.CheckConstraint(
                condition=Q(is_free=True, tier__isnull=True) | Q(is_free=False, tier__isnull=False),
                name="ck_price_free_xor_tier",
            )
        ]


class Promotion(BaseModel):
    """Site-wide sale, e.g. 'Black Friday: 60% off every paid course'."""

    name = models.CharField(max_length=120)
    percent_off = models.PositiveSmallIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = table(SCHEMA, "promotions")
        constraints = [
            models.CheckConstraint(condition=Q(percent_off__gte=1, percent_off__lte=95), name="ck_promo_pct"),
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="ck_promo_dates"),
        ]
        indexes = [models.Index(fields=["starts_at", "ends_at"], name="ix_promo_window")]


class Coupon(BaseModel):
    """A code for one course (instructor's own) or every course (staff). 100% = free."""

    code = models.CharField(max_length=40)
    course = models.ForeignKey(
        "catalog.Course", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    percent_off = models.PositiveSmallIntegerField()
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redeemed_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "coupons")
        constraints = [
            models.UniqueConstraint(Lower("code"), name="uq_coupon_code"),
            models.CheckConstraint(
                condition=Q(percent_off__gte=1, percent_off__lte=100), name="ck_coupon_pct"
            ),
            models.CheckConstraint(
                condition=Q(max_redemptions__isnull=True)
                | Q(redeemed_count__lte=models.F("max_redemptions")),
                name="ck_coupon_limit",
            ),
        ]


class Plan(BaseModel):
    class Audience(models.TextChoices):
        PERSONAL = "personal", "Personal plan"
        TEAM = "team", "Team plan (per seat)"

    class Interval(models.TextChoices):
        MONTH = "month", "Monthly"
        YEAR = "year", "Yearly"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    audience = models.CharField(max_length=8, choices=Audience.choices)
    interval = models.CharField(max_length=5, choices=Interval.choices)
    trial_days = models.PositiveSmallIntegerField(default=0)
    min_seats = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = table(SCHEMA, "plans")

    def __str__(self) -> str:
        return self.name


class PlanPrice(BaseModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="prices")
    currency = currency_fk()
    amount_minor = models.PositiveIntegerField()  # per seat for team plans
    stripe_price_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = table(SCHEMA, "plan_prices")
        constraints = [models.UniqueConstraint(fields=["plan", "currency"], name="uq_plan_currency")]


class Addon(BaseModel):
    code = models.SlugField(max_length=40, unique=True)  # "content_protection"
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = table(SCHEMA, "addons")

    def __str__(self) -> str:
        return self.name


class AddonPrice(BaseModel):
    addon = models.ForeignKey(Addon, on_delete=models.CASCADE, related_name="prices")
    currency = currency_fk()
    interval = models.CharField(max_length=5, choices=Plan.Interval.choices)
    amount_minor = models.PositiveIntegerField()
    stripe_price_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = table(SCHEMA, "addon_prices")
        constraints = [
            models.UniqueConstraint(fields=["addon", "currency", "interval"], name="uq_addon_price")
        ]


class StripeEvent(BaseModel):
    """Every webhook Stripe sends, once. The unique event id makes retries harmless."""

    event_id = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=80)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        db_table = table(SCHEMA, "stripe_events")
        indexes = [
            models.Index(
                fields=["created_at"], name="ix_stripe_unprocessed", condition=Q(processed_at__isnull=True)
            )
        ]


# ===================================================================== personal
class CartItem(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+", db_index=False)
    course = models.ForeignKey("catalog.Course", on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "cart_items")
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uq_cart_course")]


class WishlistItem(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+", db_index=False)
    course = models.ForeignKey("catalog.Course", on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "wishlist_items")
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uq_wishlist_course")]


# ======================================================================== mixed
class Order(MixedTenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"
        EXPIRED = "expired", "Checkout expired"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partly refunded"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    currency = currency_fk()
    subtotal_minor = models.PositiveIntegerField()  # list prices
    discount_minor = models.PositiveIntegerField(default=0)
    tax_minor = models.PositiveIntegerField(default=0)  # prices are tax-inclusive; Stripe Tax later
    total_minor = models.PositiveIntegerField()
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10)  # currency per GBP at checkout
    gbp_total_minor = models.PositiveIntegerField()  # for reporting and instructor revenue
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    stripe_session_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    stripe_payment_intent_id = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "orders")
        constraints = [models.UniqueConstraint(fields=["org", "id"], name="uq_orders_org_id")]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="ix_orders_user"),
            models.Index(fields=["org", "-created_at"], name="ix_orders_org", condition=Q(org__isnull=False)),
            models.Index(
                fields=["status", "created_at"], name="ix_orders_pending", condition=Q(status="pending")
            ),
        ]


class OrderItem(MixedTenantModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    course = models.ForeignKey("catalog.Course", on_delete=models.PROTECT, related_name="+")
    list_minor = models.PositiveIntegerField()
    discount_minor = models.PositiveIntegerField(default=0)
    tax_minor = models.PositiveIntegerField(default=0)
    gross_minor = models.PositiveIntegerField()  # what was paid for this item
    gbp_gross_minor = models.PositiveIntegerField()
    enrollment = models.ForeignKey(
        "learning.Enrollment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "order_items")
        constraints = [models.UniqueConstraint(fields=["order", "course"], name="uq_order_course")]
        indexes = [
            models.Index(fields=["course", "created_at"], name="ix_items_course")
        ]  # instructor revenue


class Payment(MixedTenantModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider_ref = models.CharField(max_length=64, unique=True)  # payment intent id
    amount_minor = models.PositiveIntegerField()
    currency = currency_fk()
    status = models.CharField(max_length=16)  # succeeded / failed

    class Meta:
        db_table = table(SCHEMA, "payments")


class Refund(MixedTenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Refunded"
        FAILED = "failed", "Failed"

    item = models.OneToOneField(OrderItem, on_delete=models.PROTECT, related_name="refund")
    amount_minor = models.PositiveIntegerField()
    reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_ref = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "refunds")


class CouponRedemption(MixedTenantModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="redemption")

    class Meta:
        db_table = table(SCHEMA, "coupon_redemptions")


class Subscription(MixedTenantModel):
    class Status(models.TextChoices):  # mirrors Stripe's subscription statuses
        INCOMPLETE = "incomplete", "Incomplete"
        TRIALING = "trialing", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Cancelled"
        UNPAID = "unpaid", "Unpaid"

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INCOMPLETE)
    currency = currency_fk()
    seats = models.PositiveIntegerField(default=1)
    stripe_subscription_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    stripe_session_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "subscriptions")
        constraints = [models.UniqueConstraint(fields=["org", "id"], name="uq_subs_org_id")]
        indexes = [
            models.Index(fields=["user", "status"], name="ix_subs_user"),
            models.Index(fields=["org", "status"], name="ix_subs_org", condition=Q(org__isnull=False)),
        ]


class AddonSubscription(MixedTenantModel):
    addon = models.ForeignKey(Addon, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=12, choices=Subscription.Status.choices, default="incomplete")
    currency = currency_fk()
    stripe_subscription_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    stripe_session_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "addon_subscriptions")
        indexes = [models.Index(fields=["user", "addon", "status"], name="ix_addon_subs")]


class Invoice(MixedTenantModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, null=True, blank=True, related_name="invoices"
    )
    stripe_invoice_id = models.CharField(max_length=64, unique=True)
    number = models.CharField(max_length=40, blank=True)
    currency = currency_fk()
    amount_minor = models.PositiveIntegerField()
    status = models.CharField(max_length=16)
    hosted_url = models.URLField(max_length=500, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    issued_at = models.DateTimeField()

    class Meta:
        db_table = table(SCHEMA, "invoices")
        indexes = [models.Index(fields=["user", "-issued_at"], name="ix_invoices_user")]
