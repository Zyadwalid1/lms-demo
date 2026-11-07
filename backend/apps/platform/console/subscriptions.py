"""Console > Subscriptions (mockup 20): plans, prices, subscribers, plan changes."""

from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Schema

from apps.commerce.models import Plan, PlanPrice

from ..services import audit_request
from .common import ConsoleOkOut, router, staff


class ConsolePlanPriceIn(Schema):
    currency: str = Field(..., min_length=3, max_length=3)
    amount_minor: int = Field(..., ge=0)
    stripe_price_id: str = Field("", max_length=64, pattern=r"^(price_[A-Za-z0-9_]+)?$")


class ConsolePlanPriceOut(Schema):
    currency: str
    amount_minor: int
    stripe_price_id: str


class ConsolePlanOut(Schema):
    id: UUID
    code: str
    name: str
    audience: str
    interval: str
    is_active: bool
    prices: list[ConsolePlanPriceOut]


@router.get("/plans", response=list[ConsolePlanOut])
def plans(request):
    staff(request)
    return [{"id": p.id, "code": p.code, "name": p.name, "audience": p.audience, "interval": p.interval,
             "is_active": p.is_active,
             "prices": [{"currency": x.currency_id, "amount_minor": x.amount_minor, "stripe_price_id": x.stripe_price_id}
                        for x in p.prices.all()]}
            for p in Plan.objects.prefetch_related("prices").order_by("audience", "interval")]  # fmt: skip


@router.put("/plans/{plan_id}/prices", response=ConsoleOkOut)
def set_plan_price(request, plan_id: str, body: ConsolePlanPriceIn):
    staff(request)
    plan = get_object_or_404(Plan, pk=plan_id)
    PlanPrice.objects.update_or_create(plan=plan, currency_id=body.currency.upper(),
                                       defaults={"amount_minor": body.amount_minor,
                                                 "stripe_price_id": body.stripe_price_id})  # fmt: skip
    audit_request(request, "plan.price", "plan", plan_id, body.dict())
    return {"ok": True}
