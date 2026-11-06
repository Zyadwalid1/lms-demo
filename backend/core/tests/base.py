"""Test base classes.

Django's built-in flush between TransactionTestCase tests discovers tables by their
unqualified names, so it misses our schema-qualified tables ("org"."org_units") and
leaves data behind. This base truncates every domain schema instead.
"""

from django.db import connections
from django.test import TransactionTestCase

TRUNCATE_SCHEMAS = [
    "identity",
    "org",
    "catalog",
    "learning",
    "compliance",
    "commerce",
    "payouts",
    "engagement",
    "platform",
]
# Reference data loaded by migrations survives between tests
KEEP = {
    "django_migrations",
    "django_content_type",
    "auth_permission",
    "currencies",
    "price_tiers",
    "revenue_shares",
    "notification_templates",
    "badges",
}


class SchemaTransactionTestCase(TransactionTestCase):
    """For tests that need committed data (e.g. a second connection as lms_app)."""

    databases = {"default", "owner"}

    def _fixture_teardown(self):
        with connections["owner"].cursor() as cur:
            cur.execute(
                """
                SELECT format('%%I.%%I', schemaname, tablename) FROM pg_tables
                WHERE schemaname = ANY(%s) AND NOT (tablename = ANY(%s))
                """,
                [TRUNCATE_SCHEMAS, list(KEEP)],
            )
            tables = [r[0] for r in cur.fetchall()]
            if tables:
                cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
