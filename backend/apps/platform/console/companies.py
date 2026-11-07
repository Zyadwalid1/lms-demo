"""Console > Companies: business customers, seats, status and entitlements."""

from datetime import datetime, timedelta
from uuid import UUID

from django.db.models import Count
from django.utils import timezone
from ninja import Field, Schema

from apps.identity.models import User
from apps.org import services as org_services
from apps.org.models import Organization, OrgMember
from core.errors import ServiceError

from .. import services
from ..services import audit_request
from .common import ConsoleIdOut, ConsoleOkOut, router, staff


class ConsoleCompanyIn(Schema):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(..., max_length=320)
    seat_limit: int | None = Field(None, ge=1, le=1000000)


class ConsoleCompanyPatch(Schema):
    status: str | None = None
    seat_limit: int | None = Field(None, ge=1, le=1000000)


class ConsoleCompanyOut(Schema):
    id: UUID
    name: str
    slug: str
    status: str
    seat_limit: int | None
    members: int
    created_at: datetime


class ConsoleGrantIn(Schema):
    feature: str = Field(..., max_length=60)
    days: int | None = Field(None, ge=1, le=3650)
    seats: int | None = Field(None, ge=1, le=1000000)
    note: str = Field("", max_length=300)


@router.get("/companies", response=list[ConsoleCompanyOut])
def companies(request):
    staff(request)
    rows = Organization.objects.order_by("name")[:500]
    counts = dict(OrgMember.objects.filter(removed_at__isnull=True).values("org_id").annotate(n=Count("id"))
                  .values_list("org_id", "n"))  # fmt: skip
    return [{"id": o.id, "name": o.name, "slug": o.slug, "status": o.status, "seat_limit": o.seat_limit,
             "members": counts.get(o.id, 0), "created_at": o.created_at} for o in rows]  # fmt: skip


@router.post("/companies", response=ConsoleIdOut)
def create_company(request, body: ConsoleCompanyIn):
    staff(request)
    owner = User.objects.filter(email__iexact=body.owner_email.strip(), is_active=True).first()
    if owner is None:
        raise ServiceError("no_owner", "The owner must already have an account.")
    if Organization.objects.filter(slug=body.slug).exists():
        raise ServiceError("slug_taken", "That address is taken.")
    org = org_services.create_organization(name=body.name.strip(), slug=body.slug, owner=owner)
    if body.seat_limit:
        Organization.objects.filter(pk=org.pk).update(seat_limit=body.seat_limit)
    audit_request(request, "company.create", "organization", org.id, {"name": org.name})
    return {"id": str(org.id)}


@router.patch("/companies/{org_id}", response=ConsoleOkOut)
def update_company(request, org_id: str, body: ConsoleCompanyPatch):
    staff(request)
    changes = body.dict(exclude_unset=True)
    if "status" in changes and changes["status"] not in Organization.Status.values:
        raise ServiceError("bad_status", "Unknown status.")
    Organization.objects.filter(pk=org_id).update(**changes, updated_at=timezone.now())
    audit_request(request, "company.update", "organization", org_id, changes)
    return {"ok": True}


@router.post("/companies/{org_id}/entitlements", response=ConsoleIdOut)
def grant(request, org_id: str, body: ConsoleGrantIn):
    staff(request)
    ent = services.grant(feature=body.feature, by=request.user, org_id=org_id, seats_count=body.seats, note=body.note,
                         ends_at=timezone.now() + timedelta(days=body.days) if body.days else None)  # fmt: skip
    return {"id": str(ent.id)}
