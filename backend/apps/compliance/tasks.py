"""Compliance background jobs (Celery). Each job works on ONE company inside its own
RLS context and transaction, so a big company never blocks the others and a failure
is retried for that company only."""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.tenancy import tenant_context

from . import engine
from .models import Reminder, Requirement

log = logging.getLogger(__name__)


@shared_task(name="compliance.nightly")
def nightly_task() -> int:
    """00:05 UTC: fan out one refresh per company that has active requirements."""
    with tenant_context(staff=True):
        org_ids = list(
            Requirement.objects.filter(archived_at__isnull=True).values_list("org_id", flat=True).distinct()
        )
    for org_id in org_ids:
        refresh_org_task.delay(str(org_id), reminders=True)
    return len(org_ids)


@shared_task(name="compliance.refresh_org", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def refresh_org_task(org_id: str, requirement_ids=None, member_ids=None, reminders: bool = False) -> dict:
    with tenant_context(org_id=org_id):
        engine.allow_long_statements()
        result = engine.refresh_org(
            org_id, requirement_ids=requirement_ids, member_ids=member_ids, reminders=reminders
        )
    if result["reminders"]:
        deliver_reminders_task.delay(org_id, [str(r) for r in result["reminders"]])
    return {**result, "reminders": len(result["reminders"])}


@shared_task(
    name="compliance.course_completed", autoretry_for=(Exception,), retry_backoff=True, max_retries=5
)
def course_completed_task(org_id: str, enrollment_id: str) -> int:
    with tenant_context(org_id=org_id):
        engine.lock_org(org_id)
        members = engine.record_completions(org_id, enrollment_id=enrollment_id)
        if members:
            engine.recompute(org_id, member_ids=members)
        return len(members)


SUBJECTS = {
    Reminder.Kind.DUE_SOON: "Due soon: {name}",
    Reminder.Kind.OVERDUE: "Overdue: {name}",
    Reminder.Kind.EXPIRING_SOON: "Renewal due: {name}",
    Reminder.Kind.EXPIRED: "Expired: {name}",
    Reminder.Kind.MANUAL: "Reminder: {name}",
}


@shared_task(name="compliance.deliver_reminders")
def deliver_reminders_task(org_id: str, reminder_ids: list[str]) -> int:
    """Read what to send, send it outside any transaction, then mark each one.
    A failed email records its error and does not stop the others."""
    with tenant_context(org_id=org_id):
        rows = list(
            Reminder.objects.filter(org_id=org_id, id__in=reminder_ids, sent_at__isnull=True).values(
                "id",
                "kind",
                "due_at",
                "member_status__requirement__name",
                "member_status__member__user__email",
                "member_status__member__user__full_name",
            )
        )
    sent = 0
    for r in rows:
        name = r["member_status__requirement__name"]
        due = r["due_at"].strftime("%d %b %Y %H:%M UTC")
        hello = r["member_status__member__user__full_name"] or "there"
        error = ""
        try:
            send_mail(
                SUBJECTS[r["kind"]].format(name=name),
                f"Hi {hello},\n\n'{name}' is required by your organisation. Deadline: {due}.\n\n"
                f"Open your required training: {settings.FRONTEND_URL}/learn/required\n",
                None,
                [r["member_status__member__user__email"]],
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001 - one bad address must not stop the batch
            log.warning("reminder %s failed: %s", r["id"], exc)
            error = str(exc)[:300]
        with tenant_context(org_id=org_id):
            Reminder.objects.filter(pk=r["id"]).update(
                sent_at=timezone.now() if not error else None, error=error, updated_at=timezone.now()
            )
    return sent
