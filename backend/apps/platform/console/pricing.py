"""Console > Pricing (mockup 13, top): currencies and rates, price tiers."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Schema

from apps.commerce import pricing
from apps.commerce.models import Currency, PriceTier, PriceTierAmount
from core.errors import ServiceError

from ..services import audit_request
from .common import ConsoleOkOut, router, staff


class ConsoleCurrencyPatch(Schema):
    is_active: bool | None = None
    stripe_supported: bool | None = None


class ConsoleRateIn(Schema):
    code: str = Field(..., min_length=3, max_length=3)
    rate: Decimal = Field(..., gt=0, max_digits=20, decimal_places=10)


class ConsoleTierAmountIn(Schema):
    amount_minor: int = Field(..., ge=0, le=10**12)
    lock: bool = True


class ConsoleLatestRateOut(Schema):
    rate: str
    date: date
    source: str


class ConsoleCurrencyOut(Schema):
    code: str
    name: str
    exponent: int
    is_active: bool
    stripe_supported: bool
    rate_source: str
    latest: ConsoleLatestRateOut | None


class ConsoleRateDateOut(Schema):
    rate_date: date


class ConsoleRefreshOut(Schema):
    rates: int
    repriced: int


class ConsoleTierRowOut(Schema):
    id: UUID
    name: str
    gbp_minor: int
    is_active: bool
    amount_minor: int | None
    locked: bool


@router.get("/currencies", response=list[ConsoleCurrencyOut])
def currencies(request, active: bool | None = None):
    staff(request)
    qs = Currency.objects.order_by("code")
    if active is not None:
        qs = qs.filter(is_active=active)
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT ON (currency) currency, rate, rate_date, source FROM commerce.fx_rates "
                    "ORDER BY currency, rate_date DESC")  # fmt: skip
        latest = {c: {"rate": str(r), "date": d, "source": s} for c, r, d, s in cur.fetchall()}
    return [{"code": c.code, "name": c.name, "exponent": c.exponent, "is_active": c.is_active,
             "stripe_supported": c.stripe_supported, "rate_source": c.rate_source, "latest": latest.get(c.code)}
            for c in qs]  # fmt: skip


@router.patch("/currencies/{code}", response=ConsoleOkOut)
def update_currency(request, code: str, body: ConsoleCurrencyPatch):
    staff(request)
    changes = body.dict(exclude_unset=True)
    if changes.get("is_active") and code.upper() != "GBP":
        if not pricing.FxRate.objects.filter(currency_id=code.upper()).exists():
            raise ServiceError("no_rate", "Add an exchange rate before turning this currency on.")
    Currency.objects.filter(code=code.upper()).update(**changes, updated_at=timezone.now())
    if changes.get("is_active"):
        pricing.refresh_tier_amounts()
    audit_request(request, "currency.update", "currency", code.upper(), changes)
    return {"ok": True}


@router.post("/fx-rates", response=ConsoleRateDateOut)
def manual_rate(request, body: ConsoleRateIn):
    staff(request)
    fx = pricing.set_manual_rate(code=body.code.upper(), rate=body.rate)
    audit_request(request, "fx.manual", "currency", body.code.upper(), {"rate": str(body.rate)})
    return {"rate_date": fx.rate_date}


@router.post("/fx-rates/refresh", response=ConsoleRefreshOut)
def refresh_rates(request):
    staff(request)
    stored = pricing.fetch_ecb()
    repriced = pricing.refresh_tier_amounts()
    audit_request(request, "fx.refresh", "currency", "*", {"rates": stored, "repriced": repriced})
    return {"rates": stored, "repriced": repriced}


@router.get("/price-tiers", response=list[ConsoleTierRowOut])
def price_tiers(request, currency: str = "USD"):
    staff(request)
    code = currency.upper()
    rows = {a.tier_id: a for a in PriceTierAmount.objects.filter(currency_id=code)}
    return [{"id": t.id, "name": t.name, "gbp_minor": t.gbp_minor, "is_active": t.is_active,
             "amount_minor": rows[t.id].amount_minor if t.id in rows else None,
             "locked": bool(t.id in rows and rows[t.id].is_locked)}
            for t in PriceTier.objects.order_by("sort_order")]  # fmt: skip


@router.put("/price-tiers/{tier_id}/amounts/{code}", response=ConsoleOkOut)
def set_tier_amount(request, tier_id: str, code: str, body: ConsoleTierAmountIn):
    staff(request)
    tier = get_object_or_404(PriceTier, pk=tier_id)
    get_object_or_404(Currency, code=code.upper())
    pricing.set_tier_amount(tier=tier, code=code.upper(), amount_minor=body.amount_minor, lock=body.lock)
    audit_request(request, "tier.amount", "price_tier", tier_id, {"currency": code.upper(), **body.dict()})
    return {"ok": True}
