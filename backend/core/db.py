"""Database helpers: schema-qualified table names, replica alias, migrations router."""

from uuid import UUID

from django.conf import settings
from django.db import connection


def table(schema: str, name: str) -> str:
    """Return a db_table value that places the table in a Postgres schema.

    Django has no native schema support (ticket #6148), so we use the quoting
    trick: 'catalog"."courses' renders as "catalog"."courses" in SQL.
    """
    return f'{schema}"."{name}'


class OwnerMigrationsRouter:
    """App traffic uses `default` (pooled, lms_app). Schema changes only ever
    run on `owner` (direct, lms_owner): `python manage.py migrate --database owner`.
    """

    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "owner"  # never default (lms_app) and never replica


def replica() -> str:
    """Alias for read-only, lag-tolerant queries (catalog pages, reports):
        Course.objects.using(replica()).filter(...)
    Falls back to `default` until DATABASE_URL_REPLICA is configured.
    Never use it right after a write the user expects to see (replication lag).
    """
    return "replica" if "replica" in settings.DATABASES else "default"


def new_id() -> UUID:
    """A fresh uuidv7 from Postgres, for rows whose id must be known before insert
    (e.g. to set the RLS context, or to build an ltree path)."""
    with connection.cursor() as cur:
        cur.execute("SELECT uuidv7()")
        return cur.fetchone()[0]
