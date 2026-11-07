"""Console > Sales & orders (mockup 22): orders, refunds and invoices."""

from datetime import datetime
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.commerce import services as shop
from apps.commerce.models import Order, OrderItem
from core import cursor as keyset

from ..services import audit_request
from .common import ConsoleReasonIn, ConsoleStatusOut, clamp, router, staff


class ConsoleOrderRowOut(Schema):
    id: UUID
    email: str
    status: str
    currency: str
    total_minor: int
    gbp_total_minor: int
    created_at: datetime
    paid_at: datetime | None
    payment_intent: str


class ConsoleOrderPageOut(Schema):
    items: list[ConsoleOrderRowOut]
    next_cursor: str | None


@router.get("/orders", response=ConsoleOrderPageOut)
def orders(
    request, q: str | None = None, status: str | None = None, cursor: str | None = None, limit: int = 50
):
    staff(request)
    limit = clamp(limit)
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


@router.post("/orders/items/{item_id}/refund", response=ConsoleStatusOut)
def refund(request, item_id: str, body: ConsoleReasonIn):
    staff(request)
    item = get_object_or_404(OrderItem, pk=item_id)
    r = shop.request_refund(item=item, by=request.user, reason=body.reason)
    audit_request(request, "order.refund", "order_item", item_id, {"reason": body.reason})
    return {"status": r.status}
