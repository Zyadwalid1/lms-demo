"""Optimised READ queries (org). All run under RLS."""

from uuid import UUID

from .models import OrgMember, OrgUnit


def is_active_member(*, user_id, org_id: UUID) -> bool:
    """Called by TenantMiddleware with only app.user_id set: RLS lets a user see
    nothing but their own memberships, so this cannot be spoofed by the header."""
    return OrgMember.objects.filter(org_id=org_id, user_id=user_id, removed_at__isnull=True).exists()


def member_role(*, user_id, org_id: UUID) -> str | None:
    return (
        OrgMember.objects.filter(org_id=org_id, user_id=user_id, removed_at__isnull=True)
        .values_list("role", flat=True)
        .first()
    )


def subtree(unit: OrgUnit):
    """The unit and every unit below it (one GiST-indexed query)."""
    return OrgUnit.objects.filter(org_id=unit.org_id, path__descendant_of=unit.path, archived_at__isnull=True)


def managed_unit_paths(*, member_id) -> list[str]:
    """ltree paths a manager covers; used to scope matrices and reports."""
    return list(OrgUnit.objects.filter(manager_links__member_id=member_id).values_list("path", flat=True))
