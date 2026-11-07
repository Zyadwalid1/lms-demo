"""Console > Students and Instructors (mockup 05)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Schema

from apps.identity import services as identity
from apps.identity.models import InstructorProfile, User
from apps.payouts import services as payouts
from core import cursor as keyset

from ..services import audit_request
from .common import ConsoleOkOut, ConsoleStatusOut, clamp, pct, router, staff


class ConsoleInstructorOut(Schema):
    user_id: UUID
    name: str
    email: str
    headline: str
    bio: str
    website_url: str
    status: str
    applied_at: datetime
    platform_fee_pct: float | None
    fee_is_custom: bool


class ConsoleDecisionIn(Schema):
    approve: bool


@router.get("/instructors", response=list[ConsoleInstructorOut])
def instructors(request, status: str = "pending"):
    staff(request)
    rows = InstructorProfile.objects.filter(status=status).select_related("user").order_by("created_at")[:200]
    default = payouts.default_fee_bps()
    return [{"user_id": p.user_id, "name": p.user.full_name, "email": p.user.email, "headline": p.headline,
             "bio": p.bio, "website_url": p.website_url, "status": p.status, "applied_at": p.created_at,
             "platform_fee_pct": pct(p.platform_fee_bps if p.platform_fee_bps is not None else default),
             "fee_is_custom": p.platform_fee_bps is not None} for p in rows]  # fmt: skip


@router.post("/instructors/{user_id}/decision", response=ConsoleStatusOut)
def decide_instructor(request, user_id: str, body: ConsoleDecisionIn):
    staff(request)
    p = get_object_or_404(InstructorProfile, user_id=user_id)
    p.status = "approved" if body.approve else "rejected"
    p.approved_at = timezone.now() if body.approve else None
    p.public_slug = p.public_slug or f"i-{p.user_id.hex[:10]}"
    if body.approve and p.platform_fee_bps is None:
        p.platform_fee_bps = payouts.default_fee_bps()  # the default at approval time is theirs to keep
    p.save(update_fields=["status", "approved_at", "public_slug", "platform_fee_bps", "updated_at"])
    audit_request(request, "instructor.decision", "user", user_id, {"approved": body.approve})
    return {"status": p.status}


# ---------------------------------------------------------------- users
class ConsoleUserRowOut(Schema):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_staff: bool
    created_at: datetime
    last_login: datetime | None
    anonymized_at: datetime | None


class ConsoleUserPageOut(Schema):
    items: list[ConsoleUserRowOut]
    next_cursor: str | None


class ConsoleMembershipOut(Schema):
    org_id: UUID
    org__name: str
    role: str
    removed_at: datetime | None


class ConsoleUserOrderOut(Schema):
    id: UUID
    status: str
    currency: str
    total_minor: int
    created_at: datetime


class ConsoleUserEnrollmentOut(Schema):
    id: UUID
    course__title: str
    org__name: str | None
    status: str
    progress_pct: Decimal
    enrolled_at: datetime


class ConsoleUserDetailOut(ConsoleUserRowOut):
    memberships: list[ConsoleMembershipOut]
    orders: list[ConsoleUserOrderOut]
    enrollments: list[ConsoleUserEnrollmentOut]


class ConsoleUserPatch(Schema):
    is_active: bool


@router.get("/users", response=ConsoleUserPageOut)
def users(request, q: str | None = None, cursor: str | None = None, limit: int = 50):
    staff(request)
    limit = clamp(limit)
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


@router.get("/users/{user_id}", response=ConsoleUserDetailOut)
def user_detail(request, user_id: str):
    from apps.commerce.models import Order
    from apps.learning.models import Enrollment
    from apps.org.models import OrgMember

    staff(request)
    u = get_object_or_404(User, pk=user_id)
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "is_staff": u.is_staff,
        "created_at": u.created_at, "last_login": u.last_login, "anonymized_at": u.anonymized_at,
        "memberships": list(OrgMember.objects.filter(user=u).values("org_id", "org__name", "role", "removed_at")),
        "orders": list(Order.objects.filter(user=u).order_by("-created_at").values(
            "id", "status", "currency", "total_minor", "created_at")[:50]),
        "enrollments": list(Enrollment.objects.filter(user=u).order_by("-enrolled_at").values(
            "id", "course__title", "org__name", "status", "progress_pct", "enrolled_at")[:100]),
    }  # fmt: skip


@router.patch("/users/{user_id}", response=ConsoleOkOut)
def update_user(request, user_id: str, body: ConsoleUserPatch):
    staff(request)
    identity.set_active(user=get_object_or_404(User, pk=user_id), active=body.is_active)
    audit_request(request, "user.active", "user", user_id, {"is_active": body.is_active})
    return {"ok": True}


@router.post("/users/{user_id}/anonymize", response=ConsoleOkOut)
def anonymize(request, user_id: str):
    staff(request)
    identity.anonymize(user=get_object_or_404(User, pk=user_id))
    audit_request(request, "user.anonymize", "user", user_id)
    return {"ok": True}
