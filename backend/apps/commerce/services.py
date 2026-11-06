"""Cart, checkout, fulfilment, refunds, subscriptions and add-ons (commerce).

Money rules:
  * every amount is computed HERE from the database: the browser sends course ids,
    a currency and an optional coupon code, never a price;
  * an order is paid only when Stripe's signed webhook says so (webhooks.py), and the
    amount and currency Stripe reports must match the order exactly;
  * fulfilment is idempotent: a webhook delivered twice enrols once.
"""

from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Case, F, PositiveIntegerField, Q, When
from django.utils import timezone

from apps.catalog.models import Course, CourseInstructor
from apps.learning import services as learning
from apps.learning.models import Enrollment
from core.errors import ServiceError

from . import gateway, pricing
from .models import (
    Addon,
    AddonPrice,
    AddonSubscription,
    CartItem,
    Coupon,
    CouponRedemption,
    Currency,
    Order,
    OrderItem,
    Payment,
    Plan,
    PlanPrice,
    Refund,
    Subscription,
    WishlistItem,
)
from .signals import notify_item_refunded, notify_order_paid

PAID_ACCESS = (Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED)


# ---------------------------------------------------------------- cart & wishlist
def _sellable(course_id) -> Course:
    course = Course.objects.filter(
        pk=course_id, live_version__isnull=False, owner_org_id__isnull=True
    ).first()
    if course is None:
        raise ServiceError("not_for_sale", "This course is not available.")
    return course


def add_to_cart(*, user, course_id) -> CartItem:
    course = _sellable(course_id)
    if _owns(user, [course.id]):
        raise ServiceError("already_owned", "You already have this course.")
    item, _ = CartItem.objects.get_or_create(user=user, course=course)
    WishlistItem.objects.filter(user=user, course=course).delete()  # moved from wishlist
    return item


def remove_from_cart(*, user, course_id) -> None:
    CartItem.objects.filter(user=user, course_id=course_id).delete()


def toggle_wishlist(*, user, course_id) -> bool:
    """Returns True if the course is now on the wishlist."""
    deleted, _ = WishlistItem.objects.filter(user=user, course_id=course_id).delete()
    if deleted:
        return False
    WishlistItem.objects.create(user=user, course=_sellable(course_id))
    return True


def _owns(user, course_ids) -> set:
    taught = set(
        CourseInstructor.objects.filter(user=user, course_id__in=course_ids).values_list(
            "course_id", flat=True
        )
    )
    enrolled = set(
        Enrollment.objects.filter(
            user=user, org__isnull=True, course_id__in=course_ids, status__in=PAID_ACCESS
        ).values_list("course_id", flat=True)
    )
    return taught | enrolled


# ---------------------------------------------------------------- checkout
def _coupon(code: str | None, now) -> Coupon | None:
    if not code:
        return None
    c = Coupon.objects.filter(code__iexact=code.strip(), is_active=True, starts_at__lte=now).first()
    if c is None or (c.ends_at and c.ends_at <= now):
        raise ServiceError("bad_coupon", "This coupon is not valid.")
    if c.max_redemptions is not None and c.redeemed_count >= c.max_redemptions:
        raise ServiceError("coupon_used_up", "This coupon has been fully redeemed.")
    return c


def price_cart(*, user, course_ids: list, currency: str, coupon_code: str | None = None, now=None) -> dict:
    """The ONE place a basket is priced: the cart page and checkout call the same code,
    so what the learner sees is exactly what they are charged."""
    now = now or timezone.now()
    ids = list(dict.fromkeys(course_ids))  # de-duplicate, keep order
    if not ids or len(ids) > 50:
        raise ServiceError("bad_cart", "Choose between 1 and 50 courses.")
    cur = Currency.objects.filter(code=currency, is_active=True, stripe_supported=True).first()
    if cur is None:
        raise ServiceError("bad_currency", f"Payments in {currency} are not available.")
    courses = {
        c.id: c
        for c in Course.objects.filter(pk__in=ids, live_version__isnull=False, owner_org_id__isnull=True)
    }
    if len(courses) != len(ids):
        raise ServiceError("not_for_sale", "One of these courses is not available.")
    if owned := _owns(user, ids):
        raise ServiceError(
            "already_owned", "You already have some of these courses.", details=[str(i) for i in owned]
        )
    quotes = pricing.quote(ids, currency, now)
    if len(quotes) != len(ids):
        raise ServiceError("not_for_sale", "One of these courses has no price.")
    coupon = _coupon(coupon_code, now)
    if coupon and coupon.course_id and coupon.course_id not in courses:
        raise ServiceError("bad_coupon", "This coupon is for a different course.")

    lines = []
    for cid in ids:
        q = quotes[cid]
        list_minor = q["list_minor"]
        price = q["sale_minor"] if q["sale_minor"] is not None else list_minor
        if coupon and (coupon.course_id in (None, cid)):
            price = min(price, list_minor * (100 - coupon.percent_off) // 100)
        lines.append((cid, list_minor, price))
    return {
        "currency": cur,
        "courses": courses,
        "coupon": coupon,
        "lines": lines,
        "quotes": quotes,
        "subtotal": sum(lst for _, lst, _ in lines),
        "total": sum(p for _, _, p in lines),
    }


@transaction.atomic
def create_order(*, user, course_ids: list, currency: str, coupon_code: str | None = None) -> dict:
    """Personal purchase of one or more courses. Returns {"order", "checkout_url"}
    (checkout_url is None when the total is zero: the order is fulfilled at once)."""
    priced = price_cart(user=user, course_ids=course_ids, currency=currency, coupon_code=coupon_code)
    cur, courses, coupon, lines = priced["currency"], priced["courses"], priced["coupon"], priced["lines"]
    subtotal, total = priced["subtotal"], priced["total"]
    rate = pricing.latest_rate(currency)
    order = Order.objects.create(
        user=user,
        currency=cur,
        subtotal_minor=subtotal,
        discount_minor=subtotal - total,
        total_minor=total,
        fx_rate=rate,
        gbp_total_minor=pricing.gbp_equivalent(total, cur.exponent, rate),
        coupon=coupon,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                user=user,
                course_id=cid,
                list_minor=lst,
                discount_minor=lst - price,
                gross_minor=price,
                gbp_gross_minor=pricing.gbp_equivalent(price, cur.exponent, rate),
            )
            for cid, lst, price in lines
        ]
    )
    if total == 0:
        fulfil_order(order_id=order.id)
        order.refresh_from_db()
        return {"order": order, "checkout_url": None}

    session = gateway.create_checkout_session(
        mode="payment",
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": gateway.to_stripe_amount(price, currency, cur.exponent),
                    "product_data": {"name": courses[cid].title[:250]},
                },
            }
            for cid, _, price in lines
            if price > 0
        ],
        metadata={"kind": "order", "id": str(order.id)},
        customer_email=user.email,
        success_url=f"{settings.FRONTEND_URL}/checkout/success?order={order.id}",
        cancel_url=f"{settings.FRONTEND_URL}/cart",
        idempotency_key=f"order-{order.id}",
    )
    Order.objects.filter(pk=order.pk).update(stripe_session_id=session["id"])
    order.stripe_session_id = session["id"]
    return {"order": order, "checkout_url": session["url"]}


@transaction.atomic
def fulfil_order(
    *, order_id, payment_intent: str = "", amount_minor: int | None = None, currency: str = ""
) -> Order:
    """Mark paid and enrol. Safe to call twice. A mismatch between what Stripe charged and
    what the order says is refused (and surfaces as a webhook error to investigate)."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.PAID:
        return order
    if order.status != Order.Status.PENDING:
        raise ServiceError("not_pending", f"Order is {order.status}.")
    if order.total_minor > 0:
        cur = order.currency
        expected = gateway.to_stripe_amount(order.total_minor, cur.code, cur.exponent)
        if amount_minor != expected or currency.upper() != cur.code:
            raise ServiceError("amount_mismatch", "Paid amount does not match the order.")
        Payment.objects.create(
            order=order, user_id=order.user_id, provider_ref=payment_intent, amount_minor=order.total_minor,
            currency=cur, status="succeeded",
        )  # fmt: skip
    now = timezone.now()
    order.status, order.paid_at, order.stripe_payment_intent_id = Order.Status.PAID, now, payment_intent
    order.save(update_fields=["status", "paid_at", "stripe_payment_intent_id", "updated_at"])
    if order.coupon_id:
        CouponRedemption.objects.create(coupon_id=order.coupon_id, order=order, user_id=order.user_id)
        # count it even if a parallel checkout raced past the limit: the money is already taken
        Coupon.objects.filter(pk=order.coupon_id).update(
            redeemed_count=F("redeemed_count") + 1, max_redemptions=_raise_limit_if_needed()
        )
    user = order.user
    for item in order.items.select_related("course"):
        source = (
            Enrollment.Source.FREE
            if item.gross_minor == 0 and item.list_minor == 0
            else Enrollment.Source.PURCHASE
        )
        e = learning.enrol(user=user, course=item.course, source=source, source_ref=item.id)
        if e.status == Enrollment.Status.REVOKED:  # bought again after a refund
            Enrollment.objects.filter(pk=e.pk).update(status=Enrollment.Status.ACTIVE, source_ref=item.id)
        OrderItem.objects.filter(pk=item.pk).update(enrollment=e)
    CartItem.objects.filter(user_id=order.user_id, course_id__in=order.items.values("course_id")).delete()
    notify_order_paid(order.id)
    return order


def _raise_limit_if_needed():
    return Case(
        When(
            Q(max_redemptions__isnull=False) & Q(redeemed_count__gte=F("max_redemptions")),
            then=F("redeemed_count") + 1,
        ),
        default=F("max_redemptions"),
        output_field=PositiveIntegerField(),
    )


def expire_order(*, order_id) -> None:
    Order.objects.filter(pk=order_id, status=Order.Status.PENDING).update(
        status=Order.Status.EXPIRED, updated_at=timezone.now()
    )


@transaction.atomic
def request_refund(*, item: OrderItem, by, reason: str = "") -> Refund:
    """Learner refund within REFUND_WINDOW_DAYS of payment: money back and access removed."""
    order = Order.objects.select_for_update().get(pk=item.order_id)
    item = OrderItem.objects.get(pk=item.pk)  # re-read under the order lock: no double refunds
    if order.status not in (Order.Status.PAID, Order.Status.PARTIALLY_REFUNDED) or item.refunded_at:
        raise ServiceError("not_refundable", "This purchase cannot be refunded.")
    if order.paid_at < timezone.now() - timedelta(days=settings.REFUND_WINDOW_DAYS):
        raise ServiceError("refund_window", f"Refunds are available for {settings.REFUND_WINDOW_DAYS} days.")
    refund = Refund.objects.create(
        item=item, user_id=item.user_id, amount_minor=item.gross_minor, reason=reason[:300], requested_by=by
    )
    if item.gross_minor > 0:
        cur = order.currency
        refund.provider_ref = gateway.refund(
            payment_intent=order.stripe_payment_intent_id,
            amount=gateway.to_stripe_amount(item.gross_minor, cur.code, cur.exponent),
            idempotency_key=f"refund-{refund.id}",
        )
    refund.status = Refund.Status.SUCCEEDED
    refund.save(update_fields=["provider_ref", "status", "updated_at"])
    now = timezone.now()
    OrderItem.objects.filter(pk=item.pk).update(refunded_at=now, updated_at=now)
    if item.enrollment_id:
        Enrollment.objects.filter(pk=item.enrollment_id).update(
            status=Enrollment.Status.REVOKED, updated_at=now
        )
    remaining = order.items.filter(refunded_at__isnull=True).exists()
    order.status = Order.Status.PARTIALLY_REFUNDED if remaining else Order.Status.REFUNDED
    order.save(update_fields=["status", "updated_at"])
    notify_item_refunded(item.id)
    return refund


# ---------------------------------------------------------------- subscriptions & add-ons
def _price_for(model, code: str, **filters):
    price = model.objects.filter(currency_id=code, **filters).exclude(stripe_price_id="").first()
    if price is None:
        raise ServiceError("bad_currency", f"Not available in {code}.")
    return price


@transaction.atomic
def start_subscription(*, user, plan: Plan, currency: str, seats: int = 1, org_id=None) -> dict:
    """Personal plan (org_id None) or a company team plan (org_id set, seats >= min_seats)."""
    if not plan.is_active:
        raise ServiceError("plan_unavailable", "This plan is not available.")
    if (plan.audience == Plan.Audience.TEAM) != (org_id is not None):
        raise ServiceError(
            "wrong_audience", "Team plans are bought by a company; personal plans by a person."
        )
    if seats < plan.min_seats:
        raise ServiceError("too_few_seats", f"This plan needs at least {plan.min_seats} seats.")
    live = Subscription.objects.filter(
        org_id=org_id, plan__audience=plan.audience, status__in=["trialing", "active", "past_due"]
    )
    live = live.filter(user=user) if org_id is None else live
    if live.exists():
        raise ServiceError("already_subscribed", "There is already an active subscription.")
    price = _price_for(PlanPrice, currency, plan=plan)
    sub = Subscription.objects.create(user=user, org_id=org_id, plan=plan, currency_id=currency, seats=seats)
    session = gateway.create_checkout_session(
        mode="subscription",
        line_items=[{"price": price.stripe_price_id, "quantity": seats}],
        metadata={"kind": "subscription", "id": str(sub.id)},
        customer_email=user.email,
        success_url=f"{settings.FRONTEND_URL}/checkout/success?subscription={sub.id}",
        cancel_url=f"{settings.FRONTEND_URL}/plans",
        idempotency_key=f"sub-{sub.id}",
        trial_days=plan.trial_days,
        customer=_customer_id(user, org_id),
    )
    Subscription.objects.filter(pk=sub.pk).update(stripe_session_id=session["id"])
    return {"subscription": sub, "checkout_url": session["url"]}


@transaction.atomic
def start_addon(*, user, addon: Addon, currency: str, interval: str = "month", org_id=None) -> dict:
    price = _price_for(AddonPrice, currency, addon=addon, interval=interval)
    sub = AddonSubscription.objects.create(user=user, org_id=org_id, addon=addon, currency_id=currency)
    session = gateway.create_checkout_session(
        mode="subscription",
        line_items=[{"price": price.stripe_price_id, "quantity": 1}],
        metadata={"kind": "addon", "id": str(sub.id)},
        customer_email=user.email,
        success_url=f"{settings.FRONTEND_URL}/checkout/success?addon={sub.id}",
        cancel_url=f"{settings.FRONTEND_URL}/studio/addons",
        idempotency_key=f"addon-{sub.id}",
        customer=_customer_id(user, org_id),
    )
    AddonSubscription.objects.filter(pk=sub.pk).update(stripe_session_id=session["id"])
    return {"addon_subscription": sub, "checkout_url": session["url"]}


def _customer_id(user, org_id) -> str:
    if org_id:
        from apps.org.models import Organization

        return (
            Organization.objects.filter(pk=org_id).values_list("stripe_customer_id", flat=True).first() or ""
        )
    return user.stripe_customer_id or ""


def remember_customer(*, kind: str, row_id, customer: str) -> None:
    """After the first checkout, the Stripe customer is reused (no duplicate customers)."""
    if not customer:
        return
    from apps.identity.models import User
    from apps.org.models import Organization

    model = Subscription if kind == "subscription" else AddonSubscription
    row = model.objects.filter(pk=row_id).values("org_id", "user_id").first()
    if row is None:
        return
    if row["org_id"]:
        Organization.objects.filter(pk=row["org_id"], stripe_customer_id="").update(
            stripe_customer_id=customer
        )
    else:
        User.objects.filter(pk=row["user_id"], stripe_customer_id="").update(stripe_customer_id=customer)


def cancel_subscription(*, subscription: Subscription) -> None:
    """Stops renewal; access continues to the end of the paid period."""
    if subscription.stripe_subscription_id:
        gateway.cancel_at_period_end(subscription.stripe_subscription_id)
    Subscription.objects.filter(pk=subscription.pk).update(
        cancel_at_period_end=True, updated_at=timezone.now()
    )


def enrol_with_plan(*, user, course: Course) -> Enrollment:
    """Personal-plan learners enrol without buying; access ends with the subscription."""
    sub = (
        Subscription.objects.filter(
            user=user,
            org__isnull=True,
            plan__audience=Plan.Audience.PERSONAL,
            status__in=["trialing", "active"],
        )
        .order_by("-current_period_end")
        .first()
    )
    if sub is None or not sub.current_period_end:
        raise ServiceError("no_plan", "Subscribe to a plan to enrol in this course.", status=402)
    if course.owner_org_id is not None or course.live_version_id is None:
        raise ServiceError("not_for_sale", "This course is not available.")
    if not course.in_subscription:
        raise ServiceError(
            "not_in_plan", "This course is not included in the plan; buy it instead.", status=402
        )
    return learning.enrol(
        user=user, course=course, source=Enrollment.Source.SUBSCRIPTION, source_ref=sub.id,
        access_expires_at=sub.current_period_end,
    )  # fmt: skip


def sync_subscription_access(sub_id, period_end) -> int:
    """Renewal or cancellation moves the access end of every plan enrolment in one UPDATE."""
    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE learning.enrollments SET access_expires_at = %s, updated_at = now()
             WHERE source = 'subscription' AND source_ref = %s
            """,
            [period_end, sub_id],
        )
        return cur.rowcount
