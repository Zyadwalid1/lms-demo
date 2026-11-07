"""Console > Payouts (mockup 33, bottom): requests, balances, schedule, methods."""

from datetime import date, datetime
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Schema

from apps.payouts import services as payouts
from apps.payouts.models import Payout, PayoutAccount

from ..services import audit_request
from .common import ConsoleOkOut, ConsoleReasonIn, router, staff


class ConsolePayoutRowOut(Schema):
    id: UUID
    instructor: str
    period_end: date
    amount_gbp_minor: int
    method: str
    status: str
    account_verified: bool


class ConsoleApproveIn(Schema):
    provider_ref: str = Field("", max_length=128)


class ConsolePayoutApprovedOut(Schema):
    status: str
    provider_ref: str


class ConsolePayoutAccountOut(Schema):
    user_id: UUID
    name: str
    method: str
    paypal_email: str
    stripe_account_id: str
    country: str
    verified_at: datetime | None


@router.get("/payouts", response=list[ConsolePayoutRowOut])
def payout_queue(request, status: str = "pending"):
    staff(request)
    rows = (
        Payout.objects.filter(status=status)
        .select_related("user")
        .order_by("period_end", "user__full_name")[:500]
    )
    accounts = {a.user_id: a for a in PayoutAccount.objects.filter(user_id__in=[p.user_id for p in rows])}
    return [{"id": p.id, "instructor": p.user.full_name, "period_end": p.period_end,
             "amount_gbp_minor": p.amount_gbp_minor, "method": p.method, "status": p.status,
             "account_verified": bool(accounts.get(p.user_id) and accounts[p.user_id].verified_at)} for p in rows]  # fmt: skip


@router.post("/payouts/{payout_id}/approve", response=ConsolePayoutApprovedOut)
def approve_payout(request, payout_id: str, body: ConsoleApproveIn):
    staff(request)
    p = payouts.approve_payout(payout=get_object_or_404(Payout, pk=payout_id), by=request.user,
                               provider_ref=body.provider_ref.strip())  # fmt: skip
    audit_request(request, "payout.approve", "payout", payout_id, {"amount": p.amount_gbp_minor})
    return {"status": p.status, "provider_ref": p.provider_ref}


@router.post("/payouts/{payout_id}/fail", response=ConsoleOkOut)
def fail_payout(request, payout_id: str, body: ConsoleReasonIn):
    staff(request)
    payouts.fail_payout(payout=get_object_or_404(Payout, pk=payout_id), reason=body.reason)
    audit_request(request, "payout.fail", "payout", payout_id, {"reason": body.reason})
    return {"ok": True}


@router.get("/payout-accounts", response=list[ConsolePayoutAccountOut])
def payout_accounts(request, unverified: bool = True):
    staff(request)
    qs = PayoutAccount.objects.select_related("user")
    if unverified:
        qs = qs.filter(verified_at__isnull=True)
    return [{"user_id": a.user_id, "name": a.user.full_name, "method": a.method, "paypal_email": a.paypal_email,
             "stripe_account_id": a.stripe_account_id, "country": a.country, "verified_at": a.verified_at}
            for a in qs.order_by("created_at")[:500]]  # fmt: skip


@router.post("/payout-accounts/{user_id}/verify", response=ConsoleOkOut)
def verify_account(request, user_id: str):
    staff(request)
    payouts.verify_account(account=get_object_or_404(PayoutAccount, user_id=user_id))
    audit_request(request, "payout_account.verify", "user", user_id)
    return {"ok": True}
