"""Platform RLS and the partitioned, append-only audit log."""

from django.db import migrations

from core import rls
from core.rls import ORG, STAFF, USER

S = "platform"

ENTITLEMENTS = (
    'ALTER TABLE "platform"."entitlements" ENABLE ROW LEVEL SECURITY;\n'
    'ALTER TABLE "platform"."entitlements" FORCE ROW LEVEL SECURITY;\n'
    f'CREATE POLICY holder_read ON "platform"."entitlements" FOR SELECT'
    f" USING (org_id = {ORG} OR user_id = {USER} OR {STAFF});\n"
    f'CREATE POLICY staff_write ON "platform"."entitlements" FOR ALL USING ({STAFF}) WITH CHECK ({STAFF});',
    'DROP POLICY IF EXISTS holder_read ON "platform"."entitlements";\n'
    'DROP POLICY IF EXISTS staff_write ON "platform"."entitlements";\n'
    'ALTER TABLE "platform"."entitlements" NO FORCE ROW LEVEL SECURITY;\n'
    'ALTER TABLE "platform"."entitlements" DISABLE ROW LEVEL SECURITY;',
)

# Any request may add an event (plain INSERT, no RETURNING); only jobs read and update them.
OUTBOX = (
    'ALTER TABLE "platform"."outbox_events" ENABLE ROW LEVEL SECURITY;\n'
    'ALTER TABLE "platform"."outbox_events" FORCE ROW LEVEL SECURITY;\n'
    'CREATE POLICY anyone_insert ON "platform"."outbox_events" FOR INSERT WITH CHECK (true);\n'
    f'CREATE POLICY jobs_all ON "platform"."outbox_events" FOR ALL USING ({STAFF}) WITH CHECK ({STAFF});',
    'DROP POLICY IF EXISTS anyone_insert ON "platform"."outbox_events";\n'
    'DROP POLICY IF EXISTS jobs_all ON "platform"."outbox_events";\n'
    'ALTER TABLE "platform"."outbox_events" NO FORCE ROW LEVEL SECURITY;\n'
    'ALTER TABLE "platform"."outbox_events" DISABLE ROW LEVEL SECURITY;',
)

AUDIT = f"""
CREATE TABLE platform.audit_logs (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_at timestamptz NOT NULL DEFAULT now(),
    actor_id uuid,
    org_id uuid,
    action varchar(80) NOT NULL,
    target_type varchar(60) NOT NULL,
    target_id varchar(64) NOT NULL,
    ip inet,
    request_id varchar(64) NOT NULL DEFAULT '',
    data jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX bx_audit_time ON platform.audit_logs USING brin (created_at);
CREATE INDEX ix_audit_org ON platform.audit_logs (org_id, created_at DESC) WHERE org_id IS NOT NULL;
CREATE INDEX ix_audit_target ON platform.audit_logs (target_type, target_id, created_at DESC);
CREATE INDEX ix_audit_actor ON platform.audit_logs (actor_id, created_at DESC);

DO $$
DECLARE m date;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
    PERFORM partman.create_parent(
      p_parent_table => 'platform.audit_logs', p_control => 'created_at',
      p_interval => '1 month', p_premake => 4);
  ELSE
    FOR i IN 0..3 LOOP
      m := (date_trunc('month', now()) + make_interval(months => i))::date;
      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS platform.%I PARTITION OF platform.audit_logs FOR VALUES FROM (%L) TO (%L)',
        'audit_logs_p' || to_char(m, 'YYYYMM'), m, (m + interval '1 month')::date);
    END LOOP;
    CREATE TABLE IF NOT EXISTS platform.audit_logs_default PARTITION OF platform.audit_logs DEFAULT;
  END IF;
END $$;

ALTER TABLE platform.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.audit_logs FORCE ROW LEVEL SECURITY;
-- Company admins read their company's trail; staff read everything.
CREATE POLICY audit_read ON platform.audit_logs FOR SELECT USING (org_id = {ORG} OR {STAFF});
-- Anyone may append, but only as themselves and inside their own company.
CREATE POLICY audit_append ON platform.audit_logs FOR INSERT WITH CHECK (
  ((actor_id IS NULL AND org_id IS NULL) OR actor_id = {USER} OR {STAFF})
  AND (org_id IS NULL OR org_id = {ORG} OR {STAFF}));
-- No UPDATE / DELETE policy, and no privilege either: the trail cannot be rewritten.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lms_app') THEN
    REVOKE UPDATE, DELETE, TRUNCATE ON platform.audit_logs FROM lms_app;
  END IF;
END $$;
SELECT platform.secure_partitions();
"""


class Migration(migrations.Migration):
    dependencies = [("platform", "0001_initial")]

    operations = [
        migrations.RunSQL(*rls.reference(S, "settings")),
        migrations.RunSQL(*ENTITLEMENTS),
        migrations.RunSQL(*OUTBOX),
        migrations.RunSQL(*rls.staff_only(S, "webhook_events")),
        migrations.RunSQL(AUDIT, "DROP TABLE IF EXISTS platform.audit_logs CASCADE;"),
    ]
