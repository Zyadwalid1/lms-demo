"""platform.secure_partitions(): RLS policies on a partitioned table do NOT apply
when a partition is queried directly. This removes every direct privilege on
partitions of domain tables, so all access goes through the parent, where RLS
applies. Runs in migrations that add partitioned tables and daily (Celery beat),
because pg_partman creates future partitions on its own schedule.

SECURITY DEFINER: only the table owner may REVOKE, and the daily job runs as lms_app.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION platform.secure_partitions() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE r record; n integer := 0; role_name text;
BEGIN
  FOR r IN
    SELECT c.oid::regclass AS child
    FROM pg_inherits i
    JOIN pg_class p ON p.oid = i.inhparent AND p.relkind = 'p'
    JOIN pg_namespace pn ON pn.oid = p.relnamespace
    JOIN pg_class c ON c.oid = i.inhrelid
    WHERE pn.nspname IN ('identity','org','catalog','learning','compliance','commerce',
                         'payouts','engagement','analytics','platform')
  LOOP
    EXECUTE format('REVOKE ALL ON %s FROM PUBLIC', r.child);
    FOREACH role_name IN ARRAY ARRAY['lms_app', 'lms_readonly'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
        EXECUTE format('REVOKE ALL ON %s FROM %I', r.child, role_name);
      END IF;
    END LOOP;
    n := n + 1;
  END LOOP;
  RETURN n;
END $$;
REVOKE ALL ON FUNCTION platform.secure_partitions() FROM PUBLIC;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lms_app') THEN
    GRANT EXECUTE ON FUNCTION platform.secure_partitions() TO lms_app;
  END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0001_foundation")]
    operations = [migrations.RunSQL(FORWARD, "DROP FUNCTION IF EXISTS platform.secure_partitions();")]
