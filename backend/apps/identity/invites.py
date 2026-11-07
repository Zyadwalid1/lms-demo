"""Staff invite someone to teach (console > Instructors > Add instructor).

The invite is a signed, time-limited token (Django's signing with the SECRET_KEY): no
table is needed, nothing secret is stored, and a changed or expired link is refused.
Accepting needs the signed-in account to own the invited email address; it then becomes
an approved marketplace instructor with the platform's default rate.
"""

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from core.errors import ServiceError
from core.tenancy import tenant_context

from .models import InstructorProfile

SALT = "lms.instructor-invite"
MAX_AGE = 7 * 24 * 3600  # 7 days, like company invites


def make_token(*, email: str, invited_by) -> str:
    return signing.dumps({"email": email.strip().lower(), "by": str(invited_by.id)}, salt=SALT, compress=True)


def read_token(token: str) -> dict:
    try:
        return signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired as e:
        raise ServiceError(
            "invite_expired", "This invitation has expired. Ask for a new one.", status=404
        ) from e
    except signing.BadSignature as e:
        raise ServiceError("invite_invalid", "This invitation is not valid.", status=404) from e


def send_invite(*, email: str, name: str, invited_by) -> str:
    """Emails the link after the transaction commits. Returns the token (tests, audit-free)."""
    from apps.platform.services import get_setting

    email = email.strip().lower()
    profile = InstructorProfile.objects.filter(user__email__iexact=email).first()
    if profile and profile.status == InstructorProfile.Status.APPROVED:
        raise ServiceError("already_instructor", "This person is already an instructor.")
    if profile and profile.status == InstructorProfile.Status.SUSPENDED:
        raise ServiceError("suspended", "This instructor is suspended. Reactivate them instead.")
    token = make_token(email=email, invited_by=invited_by)
    platform = get_setting("general.platform_name")
    inviter = invited_by.full_name or "The team"
    link = f"{settings.FRONTEND_URL}/teach/invite/{token}"
    hello = f"Hello {name.strip()}," if name.strip() else "Hello,"
    transaction.on_commit(lambda: send_mail(
        f"{inviter} invited you to teach on {platform}",
        f"{hello}\n\n{inviter} has invited you to teach on {platform}.\n\n"
        f"Accept the invitation (valid for 7 days):\n{link}\n\n"
        "Sign in or create an account with this email address. If you were not expecting this, ignore this email.",
        None, [email], fail_silently=True,
    ))  # fmt: skip
    return token


def preview(token: str) -> dict:
    data = read_token(token)
    return {"email": data["email"]}


@transaction.atomic
def accept(*, token: str, user) -> InstructorProfile:
    from apps.engagement.notify import notify
    from apps.payouts import services as payouts

    data = read_token(token)
    if data["email"] != user.email.lower():
        raise ServiceError("wrong_account", f"This invitation is for {data['email']}. Sign in with that address.",
                           status=403)  # fmt: skip
    with tenant_context(user_id=user.id, staff=True):  # a narrow, validated write on the user's own profile
        profile, _ = InstructorProfile.objects.select_for_update().get_or_create(user=user)
        if profile.status == InstructorProfile.Status.SUSPENDED:
            raise ServiceError(
                "suspended", "Your teaching account is suspended. Contact support.", status=403
            )
        if profile.status != InstructorProfile.Status.APPROVED:
            profile.status, profile.approved_at = InstructorProfile.Status.APPROVED, timezone.now()
            profile.public_slug = profile.public_slug or f"i-{user.id.hex[-12:]}"
            if profile.platform_fee_bps is None:
                profile.platform_fee_bps = payouts.default_fee_bps()
            profile.save()
            notify(
                [user.id], "instructor_approved", {}, url="/studio", dedupe=f"instructor-approved:{user.id}"
            )
    return profile
