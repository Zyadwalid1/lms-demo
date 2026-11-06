"""Org background jobs (Celery)."""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(name="org.send_invite", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_invite_task(email: str, org_name: str, inviter: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/invite/{token}"
    send_mail(
        f"{inviter} invited you to {org_name} on LearnHub",
        f"Hello,\n\n{inviter} has invited you to join {org_name} on LearnHub.\n\n"
        f"Accept the invitation (valid for 7 days):\n{link}\n\nIf you were not expecting this, ignore this email.",
        None,
        [email],
    )
