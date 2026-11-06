"""Platform: running the system.

Postgres schema: platform.

    settings         reference: platform-wide settings and feature flags (staff write)
    entitlements     what a company or person may use (Team plan seats, content protection),
                     written only from verified payments or by staff
    outbox_events    the transactional outbox: an event is saved IN THE SAME TRANSACTION as
                     the change it describes, then dispatched. Nothing is lost if a worker
                     or Redis dies between commit and enqueue (payments -> payouts rely on it)
    webhook_events   every inbound provider webhook (Bunny), stored once, then processed
    audit_logs       append-only, partitioned by month (SQL in migration 0002): who did what,
                     when, from where. No UPDATE or DELETE is possible for the app role
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.db import table
from core.models import BaseModel

SCHEMA = "platform"
User = settings.AUTH_USER_MODEL


class Setting(BaseModel):
    key = models.CharField(max_length=100, unique=True)  # "signup.enabled", "flags.ai_assistant"
    value = models.JSONField()
    description = models.CharField(max_length=300, blank=True)
    is_public = models.BooleanField(default=False)  # may be sent to the browser
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = table(SCHEMA, "settings")

    def __str__(self) -> str:
        return self.key


class Entitlement(BaseModel):
    class Source(models.TextChoices):
        SUBSCRIPTION = "subscription", "Team or personal plan"
        ADDON = "addon", "Add-on subscription"
        GRANT = "grant", "Granted by staff"

    org = models.ForeignKey(
        "org.Organization", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    feature = models.CharField(max_length=60)  # "business", "personal_plan", "content_protection"
    source = models.CharField(max_length=12, choices=Source.choices)
    source_ref = models.UUIDField(null=True, blank=True)  # subscription / addon subscription id
    seats = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)  # NULL = until revoked
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = table(SCHEMA, "entitlements")
        constraints = [
            models.CheckConstraint(
                condition=(Q(org__isnull=False) & Q(user__isnull=True))
                | (Q(org__isnull=True) & Q(user__isnull=False)),
                name="ck_entitlement_one_owner",
            ),
            models.UniqueConstraint(
                fields=["feature", "source", "source_ref"],
                condition=Q(source_ref__isnull=False),
                name="uq_entitlement_source",
            ),
        ]
        indexes = [
            models.Index(fields=["org", "feature"], name="ix_ent_org", condition=Q(org__isnull=False)),
            models.Index(fields=["user", "feature"], name="ix_ent_user", condition=Q(user__isnull=False)),
        ]


class OutboxEvent(BaseModel):
    topic = models.CharField(max_length=80)  # "order.paid"
    payload = models.JSONField()
    available_at = models.DateTimeField()  # retry backoff moves this forward
    attempts = models.PositiveSmallIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = table(SCHEMA, "outbox_events")
        indexes = [
            models.Index(
                fields=["available_at"], name="ix_outbox_due", condition=Q(processed_at__isnull=True)
            ),
            models.Index(
                fields=["processed_at"], name="ix_outbox_done", condition=Q(processed_at__isnull=False)
            ),
        ]


class WebhookEvent(BaseModel):
    provider = models.CharField(max_length=20)  # "bunny"
    dedupe_key = models.CharField(max_length=200)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        db_table = table(SCHEMA, "webhook_events")
        constraints = [models.UniqueConstraint(fields=["provider", "dedupe_key"], name="uq_webhook_once")]


class AuditLog(models.Model):
    """Read model for the partitioned audit table (created by SQL; Django never alters it)."""

    id = models.BigIntegerField(primary_key=True)
    created_at = models.DateTimeField()
    actor_id = models.UUIDField(null=True)
    org_id = models.UUIDField(null=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=60)
    target_id = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True)
    request_id = models.CharField(max_length=64)
    data = models.JSONField()

    class Meta:
        managed = False
        db_table = table(SCHEMA, "audit_logs")

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"
