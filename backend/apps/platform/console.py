"""Console: the platform staff back office. Mounted at /api/v1/console/.

Only staff accounts, and only on this path, get the staff RLS key (TenantMiddleware),
so staff powers never apply to ordinary pages. Every call checks is_staff again, and
every change is written to the audit log.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema

from apps.catalog import services as catalog
from apps.catalog.models import Course, CourseVersion
from apps.catalog.studio import _editor_tree
from apps.commerce import pricing
from apps.commerce import services as shop
from apps.commerce.models import (
    Coupon,
    Currency,
    Order,
    OrderItem,
    Plan,
    PlanPrice,
    PriceTier,
    PriceTierAmount,
    Promotion,
    StripeEvent,
    Subscription,
)
from apps.engagement import services as social
from apps.engagement.models import Answer, NotificationTemplate, Question, Review, Ticket, TicketMessage
from apps.identity import services as identity
from apps.identity.models import InstructorProfile, User
from apps.org import services as org_services
from apps.org.models import Organization, OrgMember
from apps.payouts import services as payouts
from apps.payouts.models import Payout, PayoutAccount
from core import cursor as keyset
from core import html
from core.auth import session_auth
from core.errors import ServiceError
from core.permissions import require_staff

from . import services
from .models import OutboxEvent, Setting, WebhookEvent
from .services import audit_request

router = Router(tags=["console"], auth=session_auth)


def _staff(request) -> None:
    require_staff(request)
    if not getattr(request, "platform_staff", False):  # belt and braces: must be the console path
        raise ServiceError("forbidden", "Console only.", status=403)


# ---------------------------------------------------------------- overview & health
@router.get("/overview")
def overview(request):
    _staff(request)
    now = timezone.now()
    month = now - timedelta(days=30)
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


@router.get("/health")
def health(request):
    """Background machinery: anything stuck or failing shows up here."""
    _staff(request)
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


# ---------------------------------------------------------------- course review
class NotesIn(Schema):
    notes: str = Field("", max_length=5000)


@router.get("/review/courses")
def review_queue(request):
    _staff(request)
    rows = (
        CourseVersion.objects.filter(status="in_review")
        .select_related("course", "submitted_by")
        .order_by("submitted_at")
    )
    return [{"version_id": v.id, "course_id": v.course_id, "title": v.course.title, "number": v.number,
             "submitted_by": v.submitted_by.full_name if v.submitted_by else None, "submitted_at": v.submitted_at,
             "change_summary": v.change_summary, "first_release": v.course.live_version_id is None} for v in rows]  # fmt: skip


@router.get("/review/versions/{version_id}")
def review_version(request, version_id: str):
    _staff(request)
    v = get_object_or_404(CourseVersion.objects.select_related("course"), pk=version_id)
    return {"version_id": v.id, "course": {"id": v.course_id, "title": v.course.title, "subtitle": v.course.subtitle,
                                           "description": v.course.description},
            "status": v.status, "checklist": catalog.publish_checklist(v), "sections": _editor_tree(v)}  # fmt: skip


@router.post("/review/versions/{version_id}/approve")
def approve(request, version_id: str, body: NotesIn):
    _staff(request)
    v = catalog.approve(version=get_object_or_404(CourseVersion, pk=version_id), reviewer=request.user,
                        notes=html.plain(body.notes, 5000))  # fmt: skip
    audit_request(request, "course.approve", "course_version", v.id)
    return {"status": v.status}


@router.post("/review/versions/{version_id}/request-changes")
def request_changes(request, version_id: str, body: NotesIn):
    _staff(request)
    if not body.notes.strip():
        raise ServiceError("notes_required", "Tell the instructor what to change.")
    v = catalog.request_changes(version=get_object_or_404(CourseVersion, pk=version_id), reviewer=request.user,
                                notes=html.plain(body.notes, 5000))  # fmt: skip
    audit_request(request, "course.request_changes", "course_version", v.id)
    return {"status": v.status}


@router.post("/courses/{course_id}/unpublish")
def unpublish(request, course_id: str, body: NotesIn):
    """Take a course off the marketplace (existing learners keep access)."""
    _staff(request)
    with catalog.authoring():
        Course.objects.filter(pk=course_id).update(status="unlisted", updated_at=timezone.now())
    audit_request(request, "course.unpublish", "course", course_id, {"notes": body.notes[:500]})
    return {"ok": True}


# ---------------------------------------------------------------- instructors & users
@router.get("/instructors")
def instructors(request, status: str = "pending"):
    _staff(request)
    rows = InstructorProfile.objects.filter(status=status).select_related("user").order_by("created_at")[:200]
    return [{"user_id": p.user_id, "name": p.user.full_name, "email": p.user.email, "headline": p.headline,
             "bio": p.bio, "website_url": p.website_url, "status": p.status, "applied_at": p.created_at} for p in rows]  # fmt: skip


class DecisionIn(Schema):
    approve: bool


@router.post("/instructors/{user_id}/decision")
def decide_instructor(request, user_id: str, body: DecisionIn):
    _staff(request)
    p = get_object_or_404(InstructorProfile, user_id=user_id)
    p.status = "approved" if body.approve else "rejected"
    p.approved_at = timezone.now() if body.approve else None
    p.public_slug = p.public_slug or f"i-{p.user_id.hex[:10]}"
    p.save(update_fields=["status", "approved_at", "public_slug", "updated_at"])
    audit_request(request, "instructor.decision", "user", user_id, {"approved": body.approve})
    return {"status": p.status}


@router.get("/users")
def users(request, q: str | None = None, cursor: str | None = None, limit: int = 50):
    _staff(request)
    limit = max(1, min(limit, 200))
    qs = User.objects.all()
    if q:
        qs = qs.filter(Q(email__icontains=q.strip()[:100]) | Q(full_name__icontains=q.strip()[:100]))
    after = keyset.decode(cursor, 1)
    if after:
        qs = qs.filter(id__lt=after[0])
    rows = list(qs.order_by("-id").values("id", "email", "full_name", "is_active", "is_staff", "created_at",
                                          "last_login", "anonymized_at")[: limit + 1])  # fmt: skip
    page = rows[:limit]
    return {"items": page, "next_cursor": keyset.encode(page[-1]["id"]) if len(rows) > limit else None}


@router.get("/users/{user_id}")
def user_detail(request, user_id: str):
    _staff(request)
    u = get_object_or_404(User, pk=user_id)
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "is_staff": u.is_staff,
        "created_at": u.created_at, "last_login": u.last_login, "anonymized_at": u.anonymized_at,
        "memberships": list(OrgMember.objects.filter(user=u).values("org_id", "org__name", "role", "removed_at")),
        "orders": list(Order.objects.filter(user=u).order_by("-created_at").values(
            "id", "status", "currency", "total_minor", "created_at")[:50]),
        "enrollments": u_enrollments(u),
    }  # fmt: skip


def u_enrollments(u) -> list:
    from apps.learning.models import Enrollment

    return list(Enrollment.objects.filter(user=u).order_by("-enrolled_at").values(
        "id", "course__title", "org__name", "status", "progress_pct", "enrolled_at")[:100])  # fmt: skip


class UserPatch(Schema):
    is_active: bool


@router.patch("/users/{user_id}")
def update_user(request, user_id: str, body: UserPatch):
    _staff(request)
    identity.set_active(user=get_object_or_404(User, pk=user_id), active=body.is_active)
    audit_request(request, "user.active", "user", user_id, {"is_active": body.is_active})
    return {"ok": True}


@router.post("/users/{user_id}/anonymize")
def anonymize(request, user_id: str):
    _staff(request)
    identity.anonymize(user=get_object_or_404(User, pk=user_id))
    audit_request(request, "user.anonymize", "user", user_id)
    return {"ok": True}


# ---------------------------------------------------------------- companies
class CompanyIn(Schema):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(..., max_length=320)
    seat_limit: int | None = Field(None, ge=1, le=1000000)


class CompanyPatch(Schema):
    status: str | None = None
    seat_limit: int | None = Field(None, ge=1, le=1000000)


@router.get("/companies")
def companies(request):
    _staff(request)
    rows = Organization.objects.order_by("name")[:500]
    counts = dict(OrgMember.objects.filter(removed_at__isnull=True).values("org_id").annotate(n=Count("id"))
                  .values_list("org_id", "n"))  # fmt: skip
    return [{"id": o.id, "name": o.name, "slug": o.slug, "status": o.status, "seat_limit": o.seat_limit,
             "members": counts.get(o.id, 0), "created_at": o.created_at} for o in rows]  # fmt: skip


@router.post("/companies")
def create_company(request, body: CompanyIn):
    _staff(request)
    owner = User.objects.filter(email__iexact=body.owner_email.strip(), is_active=True).first()
    if owner is None:
        raise ServiceError("no_owner", "The owner must already have an account.")
    if Organization.objects.filter(slug=body.slug).exists():
        raise ServiceError("slug_taken", "That address is taken.")
    org = org_services.create_organization(name=body.name.strip(), slug=body.slug, owner=owner)
    if body.seat_limit:
        Organization.objects.filter(pk=org.pk).update(seat_limit=body.seat_limit)
    audit_request(request, "company.create", "organization", org.id, {"name": org.name})
    return {"id": org.id}


@router.patch("/companies/{org_id}")
def update_company(request, org_id: str, body: CompanyPatch):
    _staff(request)
    changes = body.dict(exclude_unset=True)
    if "status" in changes and changes["status"] not in Organization.Status.values:
        raise ServiceError("bad_status", "Unknown status.")
    Organization.objects.filter(pk=org_id).update(**changes, updated_at=timezone.now())
    audit_request(request, "company.update", "organization", org_id, changes)
    return {"ok": True}


class GrantIn(Schema):
    feature: str = Field(..., max_length=60)
    days: int | None = Field(None, ge=1, le=3650)
    seats: int | None = Field(None, ge=1, le=1000000)
    note: str = Field("", max_length=300)


@router.post("/companies/{org_id}/entitlements")
def grant(request, org_id: str, body: GrantIn):
    _staff(request)
    ent = services.grant(feature=body.feature, by=request.user, org_id=org_id, seats_count=body.seats, note=body.note,
                         ends_at=timezone.now() + timedelta(days=body.days) if body.days else None)  # fmt: skip
    return {"id": ent.id}


# ---------------------------------------------------------------- money: currencies, rates, tiers, plans, promotions
class CurrencyPatch(Schema):
    is_active: bool | None = None
    stripe_supported: bool | None = None


class RateIn(Schema):
    code: str = Field(..., min_length=3, max_length=3)
    rate: Decimal = Field(..., gt=0, max_digits=20, decimal_places=10)


class TierAmountIn(Schema):
    amount_minor: int = Field(..., ge=0, le=10**12)
    lock: bool = True


@router.get("/currencies")
def currencies(request, active: bool | None = None):
    _staff(request)
    qs = Currency.objects.order_by("code")
    if active is not None:
        qs = qs.filter(is_active=active)
    latest = {}
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT ON (currency) currency, rate, rate_date, source FROM commerce.fx_rates "
                    "ORDER BY currency, rate_date DESC")  # fmt: skip
        latest = {c: {"rate": str(r), "date": d, "source": s} for c, r, d, s in cur.fetchall()}
    return [{"code": c.code, "name": c.name, "exponent": c.exponent, "is_active": c.is_active,
             "stripe_supported": c.stripe_supported, "rate_source": c.rate_source, "latest": latest.get(c.code)}
            for c in qs]  # fmt: skip


@router.patch("/currencies/{code}")
def update_currency(request, code: str, body: CurrencyPatch):
    _staff(request)
    changes = body.dict(exclude_unset=True)
    if changes.get("is_active") and code.upper() != "GBP":
        has_rate = pricing.FxRate.objects.filter(currency_id=code.upper()).exists()
        if not has_rate:
            raise ServiceError("no_rate", "Add an exchange rate before turning this currency on.")
    Currency.objects.filter(code=code.upper()).update(**changes, updated_at=timezone.now())
    if changes.get("is_active"):
        pricing.refresh_tier_amounts()
    audit_request(request, "currency.update", "currency", code.upper(), changes)
    return {"ok": True}


@router.post("/fx-rates")
def manual_rate(request, body: RateIn):
    _staff(request)
    fx = pricing.set_manual_rate(code=body.code.upper(), rate=body.rate)
    audit_request(request, "fx.manual", "currency", body.code.upper(), {"rate": str(body.rate)})
    return {"rate_date": fx.rate_date}


@router.post("/fx-rates/refresh")
def refresh_rates(request):
    _staff(request)
    stored = pricing.fetch_ecb()
    return {"rates": stored, "repriced": pricing.refresh_tier_amounts()}


@router.get("/price-tiers")
def price_tiers(request, currency: str = "USD"):
    _staff(request)
    amounts = dict(
        PriceTierAmount.objects.filter(currency_id=currency.upper()).values_list("tier_id", "amount_minor")
    )
    locked = set(
        PriceTierAmount.objects.filter(currency_id=currency.upper(), is_locked=True).values_list(
            "tier_id", flat=True
        )
    )
    return [{"id": t.id, "name": t.name, "gbp_minor": t.gbp_minor, "is_active": t.is_active,
             "amount_minor": amounts.get(t.id), "locked": t.id in locked}
            for t in PriceTier.objects.order_by("sort_order")]  # fmt: skip


@router.put("/price-tiers/{tier_id}/amounts/{code}")
def set_tier_amount(request, tier_id: str, code: str, body: TierAmountIn):
    _staff(request)
    tier = get_object_or_404(PriceTier, pk=tier_id)
    get_object_or_404(Currency, code=code.upper())
    pricing.set_tier_amount(tier=tier, code=code.upper(), amount_minor=body.amount_minor, lock=body.lock)
    audit_request(request, "tier.amount", "price_tier", tier_id, {"currency": code.upper(), **body.dict()})
    return {"ok": True}


class PlanPriceIn(Schema):
    currency: str = Field(..., min_length=3, max_length=3)
    amount_minor: int = Field(..., ge=0)
    stripe_price_id: str = Field("", max_length=64, pattern=r"^(price_[A-Za-z0-9_]+)?$")


@router.get("/plans")
def plans(request):
    _staff(request)
    return [{"id": p.id, "code": p.code, "name": p.name, "audience": p.audience, "interval": p.interval,
             "is_active": p.is_active, "prices": list(p.prices.values("currency", "amount_minor", "stripe_price_id"))}
            for p in Plan.objects.prefetch_related("prices").order_by("audience", "interval")]  # fmt: skip


@router.put("/plans/{plan_id}/prices")
def set_plan_price(request, plan_id: str, body: PlanPriceIn):
    _staff(request)
    plan = get_object_or_404(Plan, pk=plan_id)
    PlanPrice.objects.update_or_create(plan=plan, currency_id=body.currency.upper(),
                                       defaults={"amount_minor": body.amount_minor,
                                                 "stripe_price_id": body.stripe_price_id})  # fmt: skip
    audit_request(request, "plan.price", "plan", plan_id, body.dict())
    return {"ok": True}


class PromotionIn(Schema):
    name: str = Field(..., min_length=2, max_length=120)
    percent_off: int = Field(..., ge=1, le=95)
    starts_at: str
    ends_at: str


@router.get("/promotions")
def promotions(request):
    _staff(request)
    return list(Promotion.objects.order_by("-starts_at").values("id", "name", "percent_off", "starts_at", "ends_at",
                                                                 "is_active")[:100])  # fmt: skip


@router.post("/promotions")
def create_promotion(request, body: PromotionIn):
    _staff(request)
    p = Promotion.objects.create(name=html.plain(body.name, 120), percent_off=body.percent_off,
                                 starts_at=body.starts_at, ends_at=body.ends_at)  # fmt: skip
    audit_request(request, "promotion.create", "promotion", p.id, body.dict())
    return {"id": p.id}


@router.delete("/promotions/{promotion_id}")
def stop_promotion(request, promotion_id: str):
    _staff(request)
    Promotion.objects.filter(pk=promotion_id).update(is_active=False, updated_at=timezone.now())
    audit_request(request, "promotion.stop", "promotion", promotion_id)
    return {"ok": True}


@router.delete("/coupons/{coupon_id}")
def stop_coupon(request, coupon_id: str):
    _staff(request)
    Coupon.objects.filter(pk=coupon_id).update(is_active=False, updated_at=timezone.now())
    audit_request(request, "coupon.stop", "coupon", coupon_id)
    return {"ok": True}


# ---------------------------------------------------------------- orders, refunds & payouts
@router.get("/orders")
def orders(
    request, q: str | None = None, status: str | None = None, cursor: str | None = None, limit: int = 50
):
    _staff(request)
    limit = max(1, min(limit, 200))
    qs = Order.objects.select_related("user")
    if q:
        qs = qs.filter(user__email__icontains=q.strip()[:100])
    if status:
        qs = qs.filter(status=status)
    after = keyset.decode(cursor, 1)
    if after:
        qs = qs.filter(id__lt=after[0])
    rows = list(qs.order_by("-id")[: limit + 1])
    page = rows[:limit]
    return {"items": [{"id": o.id, "email": o.user.email, "status": o.status, "currency": o.currency_id,
                       "total_minor": o.total_minor, "gbp_total_minor": o.gbp_total_minor, "created_at": o.created_at,
                       "paid_at": o.paid_at, "payment_intent": o.stripe_payment_intent_id} for o in page],
            "next_cursor": keyset.encode(page[-1].id) if len(rows) > limit else None}  # fmt: skip


class StaffReasonIn(Schema):
    reason: str = Field(..., min_length=3, max_length=300)


@router.post("/orders/items/{item_id}/refund")
def refund(request, item_id: str, body: StaffReasonIn):
    _staff(request)
    item = get_object_or_404(OrderItem, pk=item_id)
    r = shop.request_refund(item=item, by=request.user, reason=body.reason)
    audit_request(request, "order.refund", "order_item", item_id, {"reason": body.reason})
    return {"status": r.status}


@router.get("/payouts")
def payout_queue(request, status: str = "pending"):
    _staff(request)
    rows = (
        Payout.objects.filter(status=status)
        .select_related("user")
        .order_by("period_end", "user__full_name")[:500]
    )
    accounts = {a.user_id: a for a in PayoutAccount.objects.filter(user_id__in=[p.user_id for p in rows])}
    return [{"id": p.id, "instructor": p.user.full_name, "period_end": p.period_end,
             "amount_gbp_minor": p.amount_gbp_minor, "method": p.method, "status": p.status,
             "account_verified": bool(accounts.get(p.user_id) and accounts[p.user_id].verified_at)} for p in rows]  # fmt: skip


class ApproveIn(Schema):
    provider_ref: str = Field("", max_length=128)


@router.post("/payouts/{payout_id}/approve")
def approve_payout(request, payout_id: str, body: ApproveIn):
    _staff(request)
    p = payouts.approve_payout(payout=get_object_or_404(Payout, pk=payout_id), by=request.user,
                               provider_ref=body.provider_ref.strip())  # fmt: skip
    audit_request(request, "payout.approve", "payout", payout_id, {"amount": p.amount_gbp_minor})
    return {"status": p.status, "provider_ref": p.provider_ref}


@router.post("/payouts/{payout_id}/fail")
def fail_payout(request, payout_id: str, body: StaffReasonIn):
    _staff(request)
    payouts.fail_payout(payout=get_object_or_404(Payout, pk=payout_id), reason=body.reason)
    audit_request(request, "payout.fail", "payout", payout_id, {"reason": body.reason})
    return {"ok": True}


@router.get("/payout-accounts")
def payout_accounts(request, unverified: bool = True):
    _staff(request)
    qs = PayoutAccount.objects.select_related("user")
    if unverified:
        qs = qs.filter(verified_at__isnull=True)
    return [{"user_id": a.user_id, "name": a.user.full_name, "method": a.method, "paypal_email": a.paypal_email,
             "stripe_account_id": a.stripe_account_id, "country": a.country, "verified_at": a.verified_at}
            for a in qs.order_by("created_at")[:500]]  # fmt: skip


@router.post("/payout-accounts/{user_id}/verify")
def verify_account(request, user_id: str):
    _staff(request)
    payouts.verify_account(account=get_object_or_404(PayoutAccount, user_id=user_id))
    audit_request(request, "payout_account.verify", "user", user_id)
    return {"ok": True}


# ---------------------------------------------------------------- moderation
class HideIn(Schema):
    hide: bool


@router.get("/moderation/reviews")
def reviews(request, max_rating: int = 5, limit: int = 100):
    _staff(request)
    rows = (
        Review.objects.filter(rating__lte=max_rating)
        .select_related("user", "course")
        .order_by("-created_at")[: max(1, min(limit, 500))]
    )
    return [{"id": r.id, "course": r.course.title, "author": r.user.full_name, "rating": r.rating, "body": r.body,
             "status": r.status, "created_at": r.created_at} for r in rows]  # fmt: skip


@router.post("/moderation/reviews/{review_id}")
def moderate_review(request, review_id: str, body: HideIn):
    _staff(request)
    social.moderate_review(review=get_object_or_404(Review, pk=review_id), hide=body.hide)
    audit_request(request, "review.moderate", "review", review_id, {"hide": body.hide})
    return {"ok": True}


@router.post("/moderation/questions/{question_id}")
def moderate_question(request, question_id: str, body: HideIn):
    _staff(request)
    Question.objects.filter(pk=question_id).update(hidden_at=timezone.now() if body.hide else None)
    audit_request(request, "question.moderate", "question", question_id, {"hide": body.hide})
    return {"ok": True}


@router.post("/moderation/answers/{answer_id}")
def moderate_answer(request, answer_id: str, body: HideIn):
    _staff(request)
    a = get_object_or_404(Answer, pk=answer_id)
    Answer.objects.filter(pk=a.pk).update(
        hidden_at=timezone.now() if body.hide else None
    )  # counters: trigger
    audit_request(request, "answer.moderate", "answer", answer_id, {"hide": body.hide})
    return {"ok": True}


# ---------------------------------------------------------------- support desk
class StaffReplyIn(Schema):
    body: str = Field(..., min_length=1, max_length=10000)
    internal: bool = False


class TicketPatch(Schema):
    status: str | None = None
    priority: str | None = None
    assign_to_me: bool = False


@router.get("/tickets")
def tickets(request, status: str | None = "open", mine: bool = False):
    _staff(request)
    qs = Ticket.objects.select_related("user", "assigned_to")
    if status:
        qs = qs.filter(status=status)
    if mine:
        qs = qs.filter(assigned_to=request.user)
    rows = qs.order_by("-priority", "last_message_at")[:500]
    return [{"id": t.id, "reference": t.reference, "subject": t.subject, "category": t.category, "status": t.status,
             "priority": t.priority, "requester": t.user.email, "assigned_to": t.assigned_to.full_name if t.assigned_to else None,
             "last_message_at": t.last_message_at} for t in rows]  # fmt: skip


@router.get("/tickets/{ticket_id}")
def ticket(request, ticket_id: str):
    _staff(request)
    t = get_object_or_404(Ticket.objects.select_related("user"), pk=ticket_id)
    msgs = TicketMessage.objects.filter(ticket=t).select_related("author").order_by("created_at")
    return {"id": t.id, "reference": t.reference, "subject": t.subject, "status": t.status, "priority": t.priority,
            "requester": {"id": t.user_id, "email": t.user.email, "name": t.user.full_name},
            "messages": [{"id": m.id, "author": m.author.full_name, "is_staff": m.author.is_staff, "body": m.body,
                          "internal": m.is_internal, "created_at": m.created_at} for m in msgs]}  # fmt: skip


@router.post("/tickets/{ticket_id}/messages")
def staff_reply(request, ticket_id: str, body: StaffReplyIn):
    _staff(request)
    m = social.reply(ticket=get_object_or_404(Ticket, pk=ticket_id), author=request.user, body=body.body,
                     internal=body.internal)  # fmt: skip
    return {"id": m.id}


@router.patch("/tickets/{ticket_id}")
def update_ticket(request, ticket_id: str, body: TicketPatch):
    _staff(request)
    t = get_object_or_404(Ticket, pk=ticket_id)
    if body.status:
        social.set_ticket_status(ticket=t, status=body.status, by=request.user)
    if body.priority:
        if body.priority not in Ticket.Priority.values:
            raise ServiceError("bad_priority", "Unknown priority.")
        Ticket.objects.filter(pk=t.pk).update(priority=body.priority)
    if body.assign_to_me:
        social.assign_ticket(ticket=t, agent=request.user)
    return {"ok": True}


# ---------------------------------------------------------------- settings, templates, audit
class SettingIn(Schema):
    value: dict | list | str | int | float | bool
    description: str = Field("", max_length=300)
    is_public: bool | None = None


class TemplateIn(Schema):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
    email_enabled: bool = True
    is_active: bool = True


@router.get("/settings")
def settings_list(request):
    _staff(request)
    return list(
        Setting.objects.order_by("key").values("key", "value", "description", "is_public", "updated_at")
    )


@router.put("/settings/{key}")
def set_setting(request, key: str, body: SettingIn):
    _staff(request)
    if not key.replace(".", "").replace("_", "").isalnum() or len(key) > 100:
        raise ServiceError("bad_key", "Keys use letters, digits, dots and underscores.")
    services.set_setting(key=key, value=body.value, by=request.user, description=body.description,
                         is_public=body.is_public)  # fmt: skip
    audit_request(request, "setting.update", "setting", key, {"value": body.value})
    return {"ok": True}


@router.get("/templates")
def templates(request):
    _staff(request)
    return list(
        NotificationTemplate.objects.order_by("code").values(
            "code", "title", "body", "email_enabled", "is_active"
        )
    )


@router.put("/templates/{code}")
def set_template(request, code: str, body: TemplateIn):
    _staff(request)
    tpl = get_object_or_404(NotificationTemplate, code=code)
    NotificationTemplate.objects.filter(pk=tpl.pk).update(title=html.plain(body.title, 200),
                                                          body=html.plain(body.body, 5000),
                                                          email_enabled=body.email_enabled, is_active=body.is_active,
                                                          updated_at=timezone.now())  # fmt: skip
    audit_request(request, "template.update", "notification_template", code)
    return {"ok": True}


@router.get("/audit")
def audit(request, org_id: str | None = None, actor_id: str | None = None, action: str | None = None,
          cursor: str | None = None, limit: int = 100):  # fmt: skip
    _staff(request)
    import json

    limit = max(1, min(limit, 500))
    sql = ["SELECT a.id, a.created_at, a.actor_id, u.email, a.org_id, a.action, a.target_type, a.target_id, a.ip,",
           "a.request_id, a.data FROM platform.audit_logs a LEFT JOIN identity.users u ON u.id = a.actor_id WHERE true"]  # fmt: skip
    params: list = []
    for column, value in (("a.org_id", org_id), ("a.actor_id", actor_id)):
        if value:
            sql.append(f"AND {column} = %s")
            params.append(value)
    if action:
        sql.append("AND a.action LIKE %s")
        params.append(action.replace("%", "") + "%")
    after = keyset.decode(cursor, 2)
    if after:
        sql.append("AND (a.created_at, a.id) < (%s::timestamptz, %s::bigint)")
        params += after
    sql.append("ORDER BY a.created_at DESC, a.id DESC LIMIT %s")
    params.append(limit + 1)
    with connection.cursor() as cur:
        cur.execute(" ".join(sql), params)
        rows = cur.fetchall()
    page = rows[:limit]
    items = [{"id": r[0], "created_at": r[1], "actor_id": r[2], "actor_email": r[3], "org_id": r[4], "action": r[5],
              "target_type": r[6], "target_id": r[7], "ip": str(r[8]) if r[8] else None, "request_id": r[9],
              "data": r[10] if isinstance(r[10], dict) else json.loads(r[10] or "{}")} for r in page]  # fmt: skip
    return {
        "items": items,
        "next_cursor": keyset.encode(page[-1][1].isoformat(), page[-1][0]) if len(rows) > limit else None,
    }
