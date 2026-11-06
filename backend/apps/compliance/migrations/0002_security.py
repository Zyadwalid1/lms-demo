"""Compliance: company-only RLS on every table, and composite FKs so every link stays
inside one company. The FKs to learning also guarantee that only THIS company's
enrolments and certificates can ever count (a personal one has org_id NULL and
cannot match (org_id, id))."""

from django.db import migrations

from core import rls

S = "compliance"
TABLES = ("requirements", "requirement_targets", "member_status", "completion_records", "exemptions", "reminders")


def fk(table, cols, ref_schema, ref_table, name, on_delete="RESTRICT"):
    return rls.composite_fk(S, table, ("org_id", cols), ref_schema, ref_table, ("org_id", "id"), name, on_delete)


COMPOSITE_FKS = [
    fk("requirement_targets", "requirement_id", S, "requirements", "fk_rt_req_same_org", "CASCADE"),
    fk("requirement_targets", "unit_id", "org", "org_units", "fk_rt_unit_same_org", "CASCADE"),
    fk("requirement_targets", "job_role_id", "org", "job_roles", "fk_rt_role_same_org", "CASCADE"),
    fk("member_status", "requirement_id", S, "requirements", "fk_ms_req_same_org", "CASCADE"),
    fk("member_status", "member_id", "org", "org_members", "fk_ms_member_same_org", "CASCADE"),
    fk("completion_records", "requirement_id", S, "requirements", "fk_cr_req_same_org"),
    fk("completion_records", "member_id", "org", "org_members", "fk_cr_member_same_org"),
    fk("completion_records", "enrollment_id", "learning", "enrollments", "fk_cr_enrol_same_org"),
    fk("completion_records", "certificate_id", "learning", "certificates", "fk_cr_cert_same_org"),
    fk("exemptions", "requirement_id", S, "requirements", "fk_ex_req_same_org", "CASCADE"),
    fk("exemptions", "member_id", "org", "org_members", "fk_ex_member_same_org", "CASCADE"),
    fk("reminders", "member_status_id", S, "member_status", "fk_rem_status_same_org", "CASCADE"),
]


class Migration(migrations.Migration):
    dependencies = [("compliance", "0001_initial")]

    operations = [
        migrations.RunSQL(fwd, rev)
        for fwd, rev in (*(rls.company_only(S, t) for t in TABLES), *COMPOSITE_FKS)
    ]
