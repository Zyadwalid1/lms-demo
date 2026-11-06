"""Nested RLS contexts must not leak: a short elevated block inside a request leaves
the request exactly as it was."""

from django.db import connection

from core.tenancy import tenant_context
from core.tests.base import SchemaTransactionTestCase

U = "0195c0de-0000-7000-8000-000000000001"
ORG = "0195c0de-0000-7000-8000-000000000002"


def keys():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT current_setting('app.user_id', true), current_setting('app.org_id', true),"
            " current_setting('app.platform_staff', true)"
        )
        return tuple(v or "" for v in cur.fetchone())


class NestedContextTest(SchemaTransactionTestCase):
    def test_inner_staff_block_is_undone(self):
        with tenant_context(user_id=U, org_id=ORG):
            with tenant_context(staff=True):
                self.assertEqual(keys(), (U, ORG, "on"))
            self.assertEqual(keys(), (U, ORG, ""))  # staff switched off again

    def test_failed_inner_block_is_undone_by_rollback(self):
        with tenant_context(user_id=U):
            try:
                with tenant_context(staff=True, org_id=ORG):
                    raise ValueError
            except ValueError:
                pass
            self.assertEqual(keys(), (U, "", ""))
