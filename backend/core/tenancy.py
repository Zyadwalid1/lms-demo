"""Per-request security context for Postgres Row-Level Security (see core/rls.py).

Behind Neon's pooler (PgBouncer, transaction mode) a session-level SET would leak
to the next client, so every key is set with set_config(..., true): local to the
transaction this middleware opens around each authenticated request.
"""

from contextlib import contextmanager
from uuid import UUID

from django.db import connection, transaction

ORG_HEADER = "HTTP_X_ORG_ID"
CONSOLE_PREFIX = "/api/v1/console/"


def _set(cur, key: str, value: str) -> None:
    cur.execute("SELECT set_config(%s, %s, true)", [f"app.{key}", value])


def _parse_org(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org_id = None
        request.platform_staff = False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        with transaction.atomic():
            with connection.cursor() as cur:
                _set(cur, "user_id", str(user.id))
                org_id = _parse_org(request.META.get(ORG_HEADER))
                if org_id is not None:
                    # Runs under RLS: with only app.user_id set, the user can see
                    # nothing but their own memberships, so this cannot be spoofed.
                    from apps.org.selectors import is_active_member

                    if is_active_member(user_id=user.id, org_id=org_id):
                        _set(cur, "org_id", str(org_id))
                        request.org_id = org_id
                if user.is_staff and request.path.startswith(CONSOLE_PREFIX):
                    _set(cur, "platform_staff", "on")
                    request.platform_staff = True
            return self.get_response(request)


KEYS = ("user_id", "org_id", "platform_staff")


@contextmanager
def tenant_context(*, org_id: UUID | None = None, user_id: UUID | None = None, staff: bool = False):
    """For Celery tasks, scripts and narrow elevated writes: run a block with the RLS keys
    a request would have.

        with tenant_context(org_id=org.id):
            Assignment.objects.filter(...)

    Nesting is safe: set_config(..., true) lasts until the end of the WHOLE transaction,
    not the inner block, so the previous values are put back on exit. Without this, a
    nested tenant_context(staff=True) would leave staff mode on for the rest of the request.
    (If the block raises, the savepoint rollback restores them by itself.)
    """
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_setting('app.user_id', true), current_setting('app.org_id', true),"
                " current_setting('app.platform_staff', true)"
            )
            previous = dict(zip(KEYS, cur.fetchone(), strict=True))
            if user_id is not None:
                _set(cur, "user_id", str(user_id))
            if org_id is not None:
                _set(cur, "org_id", str(org_id))
            if staff:
                _set(cur, "platform_staff", "on")
        yield
        with connection.cursor() as cur:
            for key in KEYS:
                _set(cur, key, previous[key] or "")
