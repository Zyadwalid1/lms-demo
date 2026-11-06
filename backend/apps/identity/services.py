"""Business logic that WRITES (identity). Endpoints call these; keep Ninja out of here."""

from django.db import transaction
from django.utils import timezone

from core.errors import ServiceError

from .models import User


@transaction.atomic
def anonymize(*, user: User) -> None:
    """Right to erasure (decision 8): personal details are removed from the ONE place
    they live (identity); learning, purchases and compliance records stay as anonymous
    history. Certificates keep the printed name: the documented exception, because a
    certificate is a public record the person was issued."""
    if user.is_staff:
        raise ServiceError("staff", "Remove staff rights before anonymising this account.")
    if user.anonymized_at:
        return
    from allauth.account.models import EmailAddress
    from allauth.mfa.models import Authenticator
    from allauth.socialaccount.models import SocialAccount

    EmailAddress.objects.filter(user=user).delete()
    SocialAccount.objects.filter(user=user).delete()
    Authenticator.objects.filter(user=user).delete()
    user.email = f"deleted-{user.id.hex}@deleted.invalid"
    user.full_name = "Deleted user"
    user.avatar_url = ""
    user.is_active = False
    user.anonymized_at = timezone.now()
    user.set_unusable_password()
    user.save()
    # is_active=False: Django treats every existing session of this user as signed out


def set_active(*, user: User, active: bool) -> None:
    if user.is_staff and not active:
        raise ServiceError("staff", "Remove staff rights before suspending this account.")
    User.objects.filter(pk=user.pk).update(is_active=active)
