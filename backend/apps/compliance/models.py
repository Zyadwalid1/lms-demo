"""Compliance: required training for companies (decision 4).

Postgres schema: compliance. Every table is COMPANY-ONLY (core.rls.company_only) and
every link inside it is a composite FK (org_id, x_id), so one company's rule can never
point at another company's people, units, roles, enrolments or certificates.

    Requirement          "Fire Safety, renew every 12 months, due 30 days after assignment"
    RequirementTarget    who it applies to: a unit (optionally with its sub-units), a job
                         role, both (people in that unit WITH that role), or neither (everyone)
    MemberStatus         one precomputed row per person x requirement: the HR matrix reads
                         only this table. Recomputed by events and nightly (00:05 UTC)
    CompletionRecord     immutable evidence: a company certificate, a manual entry (external
                         training) or an import. Status is derived from the latest record
    Exemption            "not required for this person", optionally until a date
    Reminder             one row per reminder sent; the unique key makes sending idempotent

All times are UTC (decision 13): due_at is a timestamptz.
Personal certificates never count automatically: records can only cite this company's
enrolments and certificates (enforced by composite FK in migration 0002).
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.db import table
from core.models import TenantModel

SCHEMA = "compliance"
User = settings.AUTH_USER_MODEL


def default_reminder_days() -> list[int]:
    return [14, 3]


class Requirement(TenantModel):
    course = models.ForeignKey("catalog.Course", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    renewal_months = models.PositiveSmallIntegerField(null=True, blank=True)  # NULL = once is enough
    due_days = models.PositiveSmallIntegerField(default=30)  # deadline after someone is assigned
    expiring_soon_days = models.PositiveSmallIntegerField(default=30)
    reminder_days = ArrayField(models.PositiveSmallIntegerField(), default=default_reminder_days, size=8)
    overdue_every_days = models.PositiveSmallIntegerField(default=7)  # 0 = no overdue reminders
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "requirements")
        constraints = [
            models.UniqueConstraint(fields=["org", "id"], name="uq_req_org_id"),
            models.UniqueConstraint(
                "org", Lower("name"), condition=Q(archived_at__isnull=True), name="uq_req_name"
            ),
            models.CheckConstraint(
                condition=Q(renewal_months__isnull=True) | Q(renewal_months__gte=1), name="ck_req_renewal"
            ),
        ]
        indexes = [models.Index(fields=["org", "course"], name="ix_req_org_course")]

    def __str__(self) -> str:
        return self.name


class RequirementTarget(TenantModel):
    """unit and job_role both NULL = everyone in the company."""

    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="targets")
    unit = models.ForeignKey("org.OrgUnit", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    job_role = models.ForeignKey(
        "org.JobRole", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    include_subunits = models.BooleanField(default=True)

    class Meta:
        db_table = table(SCHEMA, "requirement_targets")
        constraints = [
            models.UniqueConstraint(
                fields=["requirement", "unit", "job_role"], nulls_distinct=False, name="uq_req_target"
            )
        ]
        indexes = [
            models.Index(fields=["org", "unit"], name="ix_req_target_unit"),
            models.Index(fields=["org", "job_role"], name="ix_req_target_role"),
        ]


class MemberStatus(TenantModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLIANT = "compliant", "Compliant"
        EXPIRING_SOON = "expiring_soon", "Expiring soon"
        EXPIRED = "expired", "Expired"
        OVERDUE = "overdue", "Overdue"
        EXEMPT = "exempt", "Exempt"

    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="statuses")
    member = models.ForeignKey("org.OrgMember", on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_STARTED)
    assigned_at = models.DateTimeField()
    initial_due_at = models.DateTimeField()  # assigned_at + due_days: first-time deadline
    due_override_at = models.DateTimeField(null=True, blank=True)  # HR extended this person's deadline
    due_at = models.DateTimeField(null=True, blank=True)  # effective deadline (NULL = nothing due)
    record = models.ForeignKey(
        "CompletionRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)  # of the record above
    expires_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField()

    class Meta:
        db_table = table(SCHEMA, "member_status")
        constraints = [
            models.UniqueConstraint(fields=["org", "id"], name="uq_status_org_id"),
            models.UniqueConstraint(fields=["requirement", "member"], name="uq_status_req_member"),
        ]
        indexes = [
            models.Index(fields=["org", "status", "due_at"], name="ix_status_org_status_due"),
            models.Index(fields=["org", "requirement", "status"], name="ix_status_org_req"),
            models.Index(fields=["org", "member"], name="ix_status_org_member"),
        ]


class CompletionRecord(TenantModel):
    class Source(models.TextChoices):
        COURSE = "course", "Completed the course"
        MANUAL = "manual", "Recorded by an admin"
        IMPORT = "import", "Imported"

    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="records")
    member = models.ForeignKey("org.OrgMember", on_delete=models.CASCADE, related_name="+")
    source = models.CharField(max_length=8, choices=Source.choices)
    completed_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)  # completed_at + renewal_months
    enrollment = models.ForeignKey(
        "learning.Enrollment", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    certificate = models.ForeignKey(
        "learning.Certificate", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    evidence_asset = models.ForeignKey(
        "catalog.MediaAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)  # never deleted: audits need history
    void_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = table(SCHEMA, "completion_records")
        constraints = [
            models.UniqueConstraint(fields=["requirement", "enrollment"], name="uq_record_req_enrollment"),
            models.CheckConstraint(
                condition=~Q(source="course") | Q(enrollment__isnull=False), name="ck_record_course_has_enrol"
            ),
        ]
        indexes = [
            models.Index(
                fields=["org", "requirement", "member", "-completed_at"],
                name="ix_record_latest",
                condition=Q(voided_at__isnull=True),
            ),
        ]


class Exemption(TenantModel):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="exemptions")
    member = models.ForeignKey("org.OrgMember", on_delete=models.CASCADE, related_name="+")
    reason = models.CharField(max_length=300)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)  # NULL = until revoked
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table(SCHEMA, "exemptions")
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="ck_exempt_dates",
            )
        ]
        indexes = [
            models.Index(
                fields=["org", "requirement", "member"],
                name="ix_exempt_active",
                condition=Q(revoked_at__isnull=True),
            )
        ]


class Reminder(TenantModel):
    class Kind(models.TextChoices):
        DUE_SOON = "due_soon", "Due soon"
        OVERDUE = "overdue", "Overdue"
        EXPIRING_SOON = "expiring_soon", "Expiring soon"
        EXPIRED = "expired", "Expired"
        MANUAL = "manual", "Sent by an admin"

    member_status = models.ForeignKey(MemberStatus, on_delete=models.CASCADE, related_name="reminders")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    due_at = models.DateTimeField()  # the deadline this reminder was about (cycle key)
    # due_soon/expiring: days-before threshold; overdue/expired: repeat number;
    # manual: UTC day number (so an admin can nudge someone at most once a day)
    step = models.IntegerField()
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "reminders")
        constraints = [
            models.UniqueConstraint(
                fields=["member_status", "kind", "due_at", "step"], name="uq_reminder_once"
            )
        ]
        indexes = [
            models.Index(
                fields=["org", "created_at"], name="ix_reminder_unsent", condition=Q(sent_at__isnull=True)
            )
        ]
