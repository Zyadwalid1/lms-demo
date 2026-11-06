"""Learning: RLS, enrolment inheritance triggers, partitioned progress log,
public certificate verification."""

from django.db import migrations

from core import rls

S = "learning"

INHERIT_FUNCTION = """
CREATE OR REPLACE FUNCTION learning.inherit_enrollment() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE parent_org uuid; parent_user uuid;
BEGIN
  -- TG_ARGV[0] = parent table, TG_ARGV[1] = this row's FK column to it
  EXECUTE format('SELECT org_id, user_id FROM %s WHERE id = $1', TG_ARGV[0])
    INTO parent_org, parent_user USING (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
  IF parent_user IS NULL THEN
    RAISE EXCEPTION 'parent row not found or not visible: %', TG_ARGV[0];
  END IF;
  NEW.org_id := parent_org;
  NEW.user_id := parent_user;
  RETURN NEW;
END $$;
"""

# child -> (parent, fk): org_id and user_id always copied from the enrolment
INHERIT = [
    ("lecture_progress", "learning.enrollments", "enrollment_id"),
    ("quiz_attempts", "learning.enrollments", "enrollment_id"),
    ("submissions", "learning.enrollments", "enrollment_id"),
    ("notes", "learning.enrollments", "enrollment_id"),
    ("certificates", "learning.enrollments", "enrollment_id"),
    ("submission_files", "learning.submissions", "submission_id"),
]


def trigger(table, parent, fk):
    q = f'"{S}"."{table}"'
    name = f"trg_{table}_enrollment"
    return (
        f"CREATE TRIGGER {name} BEFORE INSERT OR UPDATE OF {fk}, org_id, user_id ON {q} "
        f"FOR EACH ROW EXECUTE FUNCTION learning.inherit_enrollment('{parent}', '{fk}');",
        f"DROP TRIGGER IF EXISTS {name} ON {q};",
    )


PROGRESS_EVENTS = """
CREATE TABLE learning.progress_events (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_at timestamptz NOT NULL DEFAULT now(),
    enrollment_id uuid NOT NULL,
    org_id uuid,
    user_id uuid NOT NULL,
    course_id uuid NOT NULL,
    lecture_key uuid NOT NULL,
    seconds integer NOT NULL CHECK (seconds BETWEEN 0 AND 3600),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX bx_progress_events_time ON learning.progress_events USING brin (created_at);
CREATE INDEX ix_progress_events_enrol ON learning.progress_events (enrollment_id, created_at);
CREATE INDEX ix_progress_events_course ON learning.progress_events (course_id, created_at);

-- Monthly partitions: pg_partman where available (Neon); otherwise create the
-- current month + 3 ahead and a default partition, so inserts never fail.
DO $$
DECLARE m date;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
    PERFORM partman.create_parent(
      p_parent_table => 'learning.progress_events', p_control => 'created_at',
      p_interval => '1 month', p_premake => 4);
  ELSE
    FOR i IN 0..3 LOOP
      m := (date_trunc('month', now()) + make_interval(months => i))::date;
      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS learning.%I PARTITION OF learning.progress_events FOR VALUES FROM (%L) TO (%L)',
        'progress_events_p' || to_char(m, 'YYYYMM'), m, (m + interval '1 month')::date);
    END LOOP;
    CREATE TABLE IF NOT EXISTS learning.progress_events_default PARTITION OF learning.progress_events DEFAULT;
  END IF;
END $$;
"""

VERIFY_FUNCTION = """
-- Public certificate verification (screen 23): anyone with the code sees ONLY these
-- fields. Runs as the owner so it can read past RLS, and exposes nothing else.
CREATE OR REPLACE FUNCTION learning.verify_certificate(p_code text)
RETURNS TABLE (verification_code text, recipient_name text, course_title text,
               cpd_hours numeric, issued_at timestamptz, is_revoked boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = learning, pg_temp AS $$
  SELECT c.verification_code, c.recipient_name, c.course_title, c.cpd_hours, c.issued_at,
         c.revoked_at IS NOT NULL
  FROM learning.certificates c
  WHERE c.verification_code = upper(trim(p_code))
  LIMIT 1
$$;
REVOKE ALL ON FUNCTION learning.verify_certificate(text) FROM PUBLIC;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lms_app') THEN
    GRANT EXECUTE ON FUNCTION learning.verify_certificate(text) TO lms_app;
  END IF;
END $$;
"""

MIXED = [
    "enrollments", "lecture_progress", "progress_events", "quiz_attempts", "submissions",
    "submission_files", "notes", "certificates",
]


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0001_initial"),
        ("catalog", "0002_security_and_search"),
        ("org", "0002_security"),
        ("core", "0002_secure_partitions"),
    ]

    operations = [
        migrations.RunSQL(PROGRESS_EVENTS, "DROP TABLE IF EXISTS learning.progress_events CASCADE;"),
        migrations.RunSQL(INHERIT_FUNCTION, "DROP FUNCTION IF EXISTS learning.inherit_enrollment();"),
        *(migrations.RunSQL(*trigger(t, p, fk)) for t, p, fk in INHERIT),
        *(migrations.RunSQL(*rls.mixed(S, t)) for t in MIXED),
        migrations.RunSQL(VERIFY_FUNCTION, "DROP FUNCTION IF EXISTS learning.verify_certificate(text);"),
        migrations.RunSQL("SELECT platform.secure_partitions();", migrations.RunSQL.noop),
    ]
