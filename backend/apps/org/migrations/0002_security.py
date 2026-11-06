"""Row-Level Security and cross-company integrity for the org schema."""

from django.db import migrations

from core import rls

S = "org"

POLICIES = [
    rls.organizations(S, "organizations"),
    rls.membership(S, "org_members"),
    *(
        rls.company_only(S, t)
        for t in ("org_units", "member_units", "unit_managers", "job_roles", "member_job_roles", "invites", "branding")
    ),
]

COMPOSITE_FKS = [
    rls.composite_fk(S, "org_units", ("org_id", "parent_id"), S, "org_units", ("org_id", "id"), "fk_units_parent_same_org"),
    rls.composite_fk(S, "member_units", ("org_id", "member_id"), S, "org_members", ("org_id", "id"), "fk_mu_member_same_org", "CASCADE"),
    rls.composite_fk(S, "member_units", ("org_id", "unit_id"), S, "org_units", ("org_id", "id"), "fk_mu_unit_same_org"),
    rls.composite_fk(S, "unit_managers", ("org_id", "unit_id"), S, "org_units", ("org_id", "id"), "fk_um_unit_same_org", "CASCADE"),
    rls.composite_fk(S, "unit_managers", ("org_id", "member_id"), S, "org_members", ("org_id", "id"), "fk_um_member_same_org", "CASCADE"),
    rls.composite_fk(S, "member_job_roles", ("org_id", "member_id"), S, "org_members", ("org_id", "id"), "fk_mjr_member_same_org", "CASCADE"),
    rls.composite_fk(S, "member_job_roles", ("org_id", "job_role_id"), S, "job_roles", ("org_id", "id"), "fk_mjr_role_same_org"),
    rls.composite_fk(S, "invites", ("org_id", "unit_id"), S, "org_units", ("org_id", "id"), "fk_inv_unit_same_org"),
    rls.composite_fk(S, "invites", ("org_id", "job_role_id"), S, "job_roles", ("org_id", "id"), "fk_inv_role_same_org"),
]


class Migration(migrations.Migration):
    dependencies = [("org", "0001_initial")]

    operations = [migrations.RunSQL(fwd, rev) for fwd, rev in (*POLICIES, *COMPOSITE_FKS)]
