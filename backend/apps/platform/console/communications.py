"""Console > Communications (mockup 36): support tickets, notifications, announcements and
notification templates."""

from datetime import datetime
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Schema

from apps.engagement import services as social
from apps.engagement.models import NotificationTemplate, Ticket, TicketMessage
from core import html
from core.errors import ServiceError

from ..services import audit_request
from .common import ConsoleIdOut, ConsoleOkOut, router, staff


class ConsoleStaffReplyIn(Schema):
    body: str = Field(..., min_length=1, max_length=10000)
    internal: bool = False


class ConsoleTicketPatch(Schema):
    status: str | None = None
    priority: str | None = None
    assign_to_me: bool = False


class ConsoleTicketRowOut(Schema):
    id: UUID
    reference: str
    subject: str
    category: str
    status: str
    priority: str
    requester: str
    assigned_to: str | None
    last_message_at: datetime


class ConsoleRequesterOut(Schema):
    id: UUID
    email: str
    name: str


class ConsoleTicketMessageOut(Schema):
    id: UUID
    author: str
    is_staff: bool
    body: str
    internal: bool
    created_at: datetime


class ConsoleTicketOut(Schema):
    id: UUID
    reference: str
    subject: str
    status: str
    priority: str
    requester: ConsoleRequesterOut
    messages: list[ConsoleTicketMessageOut]


class ConsoleTemplateIn(Schema):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
    email_enabled: bool = True
    is_active: bool = True


class ConsoleTemplateOut(Schema):
    code: str
    title: str
    body: str
    email_enabled: bool
    is_active: bool


@router.get("/tickets", response=list[ConsoleTicketRowOut])
def tickets(request, status: str | None = "open", mine: bool = False):
    staff(request)
    qs = Ticket.objects.select_related("user", "assigned_to")
    if status:
        qs = qs.filter(status=status)
    if mine:
        qs = qs.filter(assigned_to=request.user)
    rows = qs.order_by("-priority", "last_message_at")[:500]
    return [{"id": t.id, "reference": t.reference, "subject": t.subject, "category": t.category, "status": t.status,
             "priority": t.priority, "requester": t.user.email,
             "assigned_to": t.assigned_to.full_name if t.assigned_to else None,
             "last_message_at": t.last_message_at} for t in rows]  # fmt: skip


@router.get("/tickets/{ticket_id}", response=ConsoleTicketOut)
def ticket(request, ticket_id: str):
    staff(request)
    t = get_object_or_404(Ticket.objects.select_related("user"), pk=ticket_id)
    msgs = TicketMessage.objects.filter(ticket=t).select_related("author").order_by("created_at")
    return {"id": t.id, "reference": t.reference, "subject": t.subject, "status": t.status, "priority": t.priority,
            "requester": {"id": t.user_id, "email": t.user.email, "name": t.user.full_name},
            "messages": [{"id": m.id, "author": m.author.full_name, "is_staff": m.author.is_staff, "body": m.body,
                          "internal": m.is_internal, "created_at": m.created_at} for m in msgs]}  # fmt: skip


@router.post("/tickets/{ticket_id}/messages", response=ConsoleIdOut)
def staff_reply(request, ticket_id: str, body: ConsoleStaffReplyIn):
    staff(request)
    m = social.reply(ticket=get_object_or_404(Ticket, pk=ticket_id), author=request.user, body=body.body,
                     internal=body.internal)  # fmt: skip
    return {"id": m.id}


@router.patch("/tickets/{ticket_id}", response=ConsoleOkOut)
def update_ticket(request, ticket_id: str, body: ConsoleTicketPatch):
    staff(request)
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


@router.get("/templates", response=list[ConsoleTemplateOut])
def templates(request):
    staff(request)
    return list(NotificationTemplate.objects.order_by("code").values("code", "title", "body", "email_enabled",
                                                                       "is_active"))  # fmt: skip


@router.put("/templates/{code}", response=ConsoleOkOut)
def set_template(request, code: str, body: ConsoleTemplateIn):
    staff(request)
    tpl = get_object_or_404(NotificationTemplate, code=code)
    NotificationTemplate.objects.filter(pk=tpl.pk).update(
        title=html.plain(body.title, 200), body=html.plain(body.body, 5000), email_enabled=body.email_enabled,
        is_active=body.is_active, updated_at=timezone.now(),
    )  # fmt: skip
    audit_request(request, "template.update", "notification_template", code)
    return {"ok": True}
