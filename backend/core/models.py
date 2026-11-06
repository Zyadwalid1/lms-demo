"""Abstract base models shared by every domain app.

Which base to use (Architecture decision 2):
    BaseModel            global tables (no RLS): catalog, plans, settings
    TenantModel          company-only tables: org_id NOT NULL  -> core.rls.company_only
    MixedTenantModel     company OR personal rows, always a user -> core.rls.mixed

Every concrete Tenant/Mixed model must add its RLS policy in its migration; the
structure test in core/tests/test_rls.py fails the build otherwise.
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Now


class UUIDv7(models.Func):
    """Postgres 18 built-in uuidv7(): time-ordered ids, smaller and faster indexes."""

    function = "uuidv7"
    template = "%(function)s()"
    output_field = models.UUIDField()


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, db_default=UUIDv7(), editable=False)
    created_at = models.DateTimeField(db_default=Now(), editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-id"]  # uuidv7 sorts by creation time


class TenantModel(BaseModel):
    """Rows owned by one company. Lead composite indexes with `org`."""

    org = models.ForeignKey("org.Organization", on_delete=models.PROTECT, related_name="+", db_index=False)

    class Meta:
        abstract = True


class MixedTenantModel(BaseModel):
    """Rows owned by a user, either inside a company (org set) or personal (org NULL).
    A company never sees a member's personal rows (decision 2)."""

    org = models.ForeignKey(
        "org.Organization", on_delete=models.PROTECT, related_name="+", db_index=False, null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", db_index=False
    )

    class Meta:
        abstract = True
