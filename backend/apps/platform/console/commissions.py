"""Console > Commissions (mockup 33, top): the default fee, per-instructor fees, rules."""

from uuid import UUID

from ninja import Field, Schema

from apps.payouts import services as payouts

from ..services import audit_request
from .common import pct, router, staff


class ConsoleFeeOut(Schema):
    default_fee_pct: float


class ConsoleFeeIn(Schema):
    fee_pct: float = Field(ge=0, le=100)


class ConsoleInstructorFeeIn(Schema):
    fee_pct: float | None = Field(None, ge=0, le=100)  # None = follow the default


class ConsoleInstructorFeeOut(Schema):
    user_id: UUID
    platform_fee_pct: float
    fee_is_custom: bool


@router.get("/platform-fee", response=ConsoleFeeOut)
def platform_fee(request):
    staff(request)
    return {"default_fee_pct": pct(payouts.default_fee_bps())}


@router.put("/platform-fee", response=ConsoleFeeOut)
def set_platform_fee(request, body: ConsoleFeeIn):
    """The cut new instructors get on approval. Instructors already approved keep theirs."""
    staff(request)
    payouts.set_default_fee(fee_bps=round(body.fee_pct * 100))
    audit_request(request, "payouts.default_fee", "revenue_share", "marketplace", {"fee_pct": body.fee_pct})
    return {"default_fee_pct": pct(payouts.default_fee_bps())}


@router.put("/instructors/{user_id}/fee", response=ConsoleInstructorFeeOut)
def set_instructor_fee(request, user_id: str, body: ConsoleInstructorFeeIn):
    staff(request)
    bps = None if body.fee_pct is None else round(body.fee_pct * 100)
    payouts.set_instructor_fee(user_id=user_id, fee_bps=bps)
    audit_request(request, "payouts.instructor_fee", "user", user_id, {"fee_pct": body.fee_pct})
    return {"user_id": user_id, "platform_fee_pct": pct(bps if bps is not None else payouts.default_fee_bps()),
            "fee_is_custom": bps is not None}  # fmt: skip
