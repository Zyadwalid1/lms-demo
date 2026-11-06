"""Identity endpoints. Sign-in itself (login, signup, verify, reset, Google,
Microsoft, 2FA) is served by django-allauth headless at /_allauth/browser/v1/.
"""

import zoneinfo

from django.middleware.csrf import get_token
from ninja import Router

from apps.commerce.models import Currency
from core import html
from core.auth import session_auth
from core.errors import ServiceError

from .schemas import MeOut, MePatchIn, OkOut

router = Router(tags=["identity"])


@router.get("/csrf", response=OkOut, auth=None)
def csrf(request):
    """Sets the csrftoken cookie. The React app calls it once on load."""
    get_token(request)
    return {"ok": True}


def _me(user) -> dict:
    from apps.org.models import OrgBranding, OrgMember

    members = list(
        OrgMember.objects.filter(user=user, removed_at__isnull=True)
        .select_related("org")
        .order_by("org__name")
    )
    branding = {
        b.org_id: b for b in OrgBranding.objects.filter(org_id__in=[m.org_id for m in members])
    }  # RLS: only the current company's branding is visible; others fall back to defaults
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name, "avatar_url": user.avatar_url,
        "timezone": user.timezone, "is_staff": user.is_staff, "preferred_currency": user.preferred_currency,
        "is_instructor": hasattr(user, "instructor_profile"),
        "memberships": [
            {"org_id": m.org_id, "name": m.org.name, "slug": m.org.slug, "role": m.role,
             "logo_url": branding[m.org_id].logo_url if m.org_id in branding else "",
             "primary_color": branding[m.org_id].primary_color if m.org_id in branding else ""}
            for m in members
        ],
    }  # fmt: skip


@router.get("/me", response=MeOut, auth=session_auth)
def me(request):
    """Who am I, and which company workspaces can I switch to (sent as X-Org-Id)."""
    return _me(request.user)


@router.patch("/me", response=MeOut, auth=session_auth)
def update_me(request, body: MePatchIn):
    user = request.user
    if body.full_name is not None:
        # printed on certificates and in emails: plain text only, and never blank
        name = html.plain(body.full_name, 200).strip()
        if not name:
            raise ServiceError("name_required", "Enter your name.")
        user.full_name = name
    if body.timezone is not None:
        if body.timezone not in zoneinfo.available_timezones():
            raise ServiceError("bad_timezone", "Unknown time zone.")
        user.timezone = body.timezone
    if body.preferred_currency is not None:
        code = body.preferred_currency.upper()
        if code and not Currency.objects.filter(code=code, is_active=True).exists():
            raise ServiceError("bad_currency", "That currency is not available.")
        user.preferred_currency = code
    user.save(update_fields=["full_name", "timezone", "preferred_currency"])
    return _me(user)
