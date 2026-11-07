"""Console > Promotions (mockup 13, bottom): promo codes, campaigns and offers."""

from datetime import datetime
from uuid import UUID

from django.utils import timezone
from ninja import Field, Schema

from apps.commerce.models import Coupon, Promotion
from core import html

from ..services import audit_request
from .common import ConsoleIdOut, ConsoleOkOut, router, staff


class ConsolePromotionIn(Schema):
    name: str = Field(..., min_length=2, max_length=120)
    percent_off: int = Field(..., ge=1, le=95)
    starts_at: datetime
    ends_at: datetime


class ConsolePromotionOut(Schema):
    id: UUID
    name: str
    percent_off: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool


@router.get("/promotions", response=list[ConsolePromotionOut])
def promotions(request):
    staff(request)
    return list(Promotion.objects.order_by("-starts_at").values("id", "name", "percent_off", "starts_at", "ends_at",
                                                                 "is_active")[:100])  # fmt: skip


@router.post("/promotions", response=ConsoleIdOut)
def create_promotion(request, body: ConsolePromotionIn):
    staff(request)
    p = Promotion.objects.create(name=html.plain(body.name, 120), percent_off=body.percent_off,
                                 starts_at=body.starts_at, ends_at=body.ends_at)  # fmt: skip
    audit_request(request, "promotion.create", "promotion", p.id, body.dict())
    return {"id": p.id}


@router.delete("/promotions/{promotion_id}", response=ConsoleOkOut)
def stop_promotion(request, promotion_id: str):
    staff(request)
    Promotion.objects.filter(pk=promotion_id).update(is_active=False, updated_at=timezone.now())
    audit_request(request, "promotion.stop", "promotion", promotion_id)
    return {"ok": True}


@router.delete("/coupons/{coupon_id}", response=ConsoleOkOut)
def stop_coupon(request, coupon_id: str):
    staff(request)
    Coupon.objects.filter(pk=coupon_id).update(is_active=False, updated_at=timezone.now())
    audit_request(request, "coupon.stop", "coupon", coupon_id)
    return {"ok": True}
