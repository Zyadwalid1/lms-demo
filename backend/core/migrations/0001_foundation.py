"""Foundation: schemas, extensions, grants. Mirrors db/0001_foundation.sql and is safe
to re-run (IF NOT EXISTS everywhere), so it is a no-op on Neon branches that already
have it and builds everything on fresh test databases and CI preview branches.

Roles (lms_owner, lms_app, lms_readonly) are created outside Django; grants are
skipped for roles that do not exist (e.g. a developer's local database).
"""

from django.db import migrations

SCHEMAS = [
    "identity", "org", "catalog", "learning", "compliance",
    "commerce", "payouts", "engagement", "analytics", "platform",
]
SCHEMA_LIST = ", ".join(SCHEMAS)

FORWARD = (
    "\n".join(f"CREATE SCHEMA IF NOT EXISTS {s};" for s in SCHEMAS)
    + """
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS ltree;
-- Optional extensions: present on Neon; skipped with a notice where unavailable or
-- not permitted (a developer's local Postgres), so the migration never fails on them.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_stat_statements') THEN
    BEGIN
      CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'pg_stat_statements skipped: %', SQLERRM;
    END;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_partman') THEN
    BEGIN
      CREATE SCHEMA IF NOT EXISTS partman;
      CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE NOTICE 'pg_partman skipped: %', SQLERRM;
    END;
  END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- On a brand-new database Django creates its bookkeeping table before this migration
-- creates the identity schema, so it lands in public: move it (public stays empty).
DO $$
BEGIN
  IF to_regclass('public.django_migrations') IS NOT NULL
     AND to_regclass('identity.django_migrations') IS NULL THEN
    ALTER TABLE public.django_migrations SET SCHEMA identity;
  END IF;
END $$;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['lms_app', 'lms_readonly'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %s TO %I', '"""
    + SCHEMA_LIST
    + """', r);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lms_app') THEN
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA """
    + SCHEMA_LIST
    + """ GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA """
    + SCHEMA_LIST
    + """ GRANT USAGE, SELECT ON SEQUENCES TO lms_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA """
    + SCHEMA_LIST
    + """ GRANT EXECUTE ON FUNCTIONS TO lms_app';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lms_readonly') THEN
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA """
    + SCHEMA_LIST
    + """ GRANT SELECT ON TABLES TO lms_readonly';
  END IF;
END $$;
"""
)


class Migration(migrations.Migration):
    initial = True
    dependencies: list = []
    operations = [migrations.RunSQL(FORWARD, reverse_sql=migrations.RunSQL.noop)]
