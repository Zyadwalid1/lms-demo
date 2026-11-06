"""Behavioural Row-Level Security tests, run as the real app role (lms_app).

Seeds two companies as the owner role, then connects as lms_app (NOBYPASSRLS, like
production) and checks that every boundary holds at the database level, independent
of any application code. Skipped where the lms_app role cannot log in.
"""

import os
import unittest

import dj_database_url
import psycopg
from django.db import connections

from apps.identity.models import User
from apps.org import services
from apps.org.models import MemberUnit, OrgMember, OrgUnit
from core.tenancy import tenant_context
from core.tests.base import SchemaTransactionTestCase

OWNER = "owner"  # reads in tests bypass RLS on purpose; the app role is tested via self.q()


def _app_conninfo(dbname: str) -> dict | None:
    url = os.getenv("DATABASE_URL", "")
    cfg = dj_database_url.parse(url) if url else {}
    if cfg.get("USER") != "lms_app":
        return None
    return {
        "host": cfg["HOST"],
        "port": cfg.get("PORT") or 5432,
        "user": cfg["USER"],
        "password": cfg["PASSWORD"],
        "dbname": dbname,
        **(cfg.get("OPTIONS") or {}),
    }


class RlsIsolationTest(SchemaTransactionTestCase):
    def setUp(self):
        info = _app_conninfo(connections["owner"].settings_dict["NAME"])
        if info is None:
            raise unittest.SkipTest("DATABASE_URL is not the lms_app role")
        info.pop("options", None)
        self.app = psycopg.connect(**info, autocommit=True)
        # Seed as the owner (bypasses RLS, like a migration or admin script)
        self.sara = User.objects.create_user("sara@acme-demo.com", "x")
        self.bob = User.objects.create_user("bob@beta-demo.com", "x")
        self.acme = services.create_organization(name="Acme", slug="acme", owner=self.sara)
        self.beta = services.create_organization(name="Beta", slug="beta", owner=self.bob)
        self.acme_root = OrgUnit.objects.using(OWNER).get(org=self.acme, parent__isnull=True)
        self.beta_root = OrgUnit.objects.using(OWNER).get(org=self.beta, parent__isnull=True)
        # Writes go through the app connection (lms_app) with the context a request would have
        with tenant_context(org_id=self.acme.id, user_id=self.sara.id):
            self.soho = services.create_unit(parent=self.acme_root, kind="site", name="Soho")
        with tenant_context(org_id=self.beta.id, user_id=self.bob.id):
            services.create_unit(parent=self.beta_root, kind="site", name="Leeds")

    def tearDown(self):
        if getattr(self, "app", None):
            self.app.close()

    def q(self, sql, *, user=None, org=None, staff=False, params=()):
        """Run one statement as lms_app inside a transaction with the given RLS keys."""
        with self.app.transaction(), self.app.cursor() as cur:
            for key, val in (("user_id", user), ("org_id", org), ("platform_staff", "on" if staff else None)):
                if val is not None:
                    cur.execute("SELECT set_config(%s, %s, true)", [f"app.{key}", str(val)])
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None

    def count(self, table, **ctx):
        return self.q(f"SELECT count(*) FROM {table}", **ctx)[0][0]  # noqa: S608 - fixed test table names

    def test_no_context_sees_nothing(self):
        for t in ("org.organizations", "org.org_members", "org.org_units", "org.member_units"):
            self.assertEqual(self.count(t), 0, t)

    def test_user_only_sees_own_membership_and_company(self):
        self.assertEqual(self.count("org.org_members", user=self.sara.id), 1)
        names = self.q("SELECT name FROM org.organizations", user=self.sara.id)
        self.assertEqual(names, [("Acme",)])
        self.assertEqual(self.count("org.org_units", user=self.sara.id), 0)  # no company selected

    def test_company_context_is_isolated(self):
        units = {r[0] for r in self.q("SELECT name FROM org.org_units", user=self.sara.id, org=self.acme.id)}
        self.assertEqual(units, {"Acme", "Soho"})
        self.assertNotIn("Leeds", units)

    def test_cannot_write_into_another_company(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.q(
                "INSERT INTO org.org_units (org_id, kind, name, path, depth, sort_order, updated_at)"
                " VALUES (%s, 'site', 'Hack', 'x', 1, 0, now())",
                user=self.sara.id,
                org=self.acme.id,
                params=[self.beta.id],
            )

    def test_cannot_add_membership_without_company_context(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.q(
                "INSERT INTO org.org_members (org_id, user_id, role, job_title, employee_ref, joined_at, updated_at)"
                " VALUES (%s, %s, 'owner', '', '', now(), now())",
                user=self.sara.id,
                params=[self.beta.id, self.sara.id],
            )

    def test_composite_fk_blocks_cross_company_links(self):
        sara_member = OrgMember.objects.using(OWNER).get(org=self.acme, user=self.sara)
        leeds = OrgUnit.objects.using(OWNER).get(org=self.beta, name="Leeds")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            MemberUnit.objects.using(OWNER).create(org=self.acme, member=sara_member, unit=leeds)

    def test_staff_key_sees_all_companies(self):
        self.assertEqual(self.count("org.organizations", user=self.sara.id, staff=True), 2)

    def test_transaction_local_keys_do_not_leak(self):
        self.q("SELECT 1", user=self.sara.id, org=self.acme.id)
        # Next transaction on the same connection: keys reverted to '' -> must not error, must see nothing
        self.assertEqual(self.count("org.org_units"), 0)

    def test_membership_check_cannot_be_spoofed(self):
        rows = self.q(
            "SELECT count(*) FROM org.org_members WHERE org_id = %s AND user_id = %s AND removed_at IS NULL",
            user=self.sara.id,
            params=[self.beta.id, self.sara.id],
        )
        self.assertEqual(rows[0][0], 0)


class UnitTreeTest(SchemaTransactionTestCase):
    def test_move_unit_rewrites_subtree_paths(self):
        owner = User.objects.create_user("o@acme-demo.com", "x")
        org = services.create_organization(name="Acme", slug="acme2", owner=owner)
        root = OrgUnit.objects.using(OWNER).get(org=org, parent__isnull=True)
        ctx = {"org_id": org.id, "user_id": owner.id}
        with tenant_context(**ctx):
            london = services.create_unit(parent=root, kind="region", name="London")
            north = services.create_unit(parent=root, kind="region", name="North")
            soho = services.create_unit(parent=london, kind="site", name="Soho")
            kitchen = services.create_unit(parent=soho, kind="department", name="Kitchen")
        with tenant_context(**ctx):
            services.move_unit(unit=soho, new_parent=north)
        soho.refresh_from_db(using=OWNER)
        kitchen.refresh_from_db(using=OWNER)
        north.refresh_from_db(using=OWNER)
        self.assertEqual(soho.parent_id, north.id)
        self.assertTrue(soho.path.startswith(north.path + "."))
        self.assertTrue(kitchen.path.startswith(soho.path + "."))
        self.assertEqual((soho.depth, kitchen.depth), (2, 3))
        under_north = set(
            OrgUnit.objects.using(OWNER).filter(path__descendant_of=north.path).values_list("name", flat=True)
        )
        self.assertEqual(under_north, {"North", "Soho", "Kitchen"})

        from core.errors import ServiceError

        with self.assertRaises(ServiceError), tenant_context(**ctx):
            services.move_unit(unit=north, new_parent=kitchen)  # cycle


class TenantMiddlewareTest(SchemaTransactionTestCase):
    """Through the real middleware: the X-Org-Id header is honoured only for members."""

    def setUp(self):
        self.sara = User.objects.create_user("sara@acme-demo.com", "x")
        self.bob = User.objects.create_user("bob@beta-demo.com", "x")
        self.acme = services.create_organization(name="Acme", slug="acme", owner=self.sara)
        self.beta = services.create_organization(name="Beta", slug="beta", owner=self.bob)

    def test_header_honoured_only_for_members(self):
        from django.test import RequestFactory

        from core.tenancy import TenantMiddleware

        seen = {}

        def view(request):
            from django.http import HttpResponse

            with connections["default"].cursor() as cur:
                cur.execute("SELECT count(*) FROM org.org_units")
                seen[str(request.org_id)] = cur.fetchone()[0]
            return HttpResponse("ok")

        middleware = TenantMiddleware(view)
        for org in (self.acme, self.beta):
            request = RequestFactory().get("/api/v1/identity/me", HTTP_X_ORG_ID=str(org.id))
            request.user = self.sara
            middleware(request)
        self.assertEqual(seen, {str(self.acme.id): 1, "None": 0})  # Beta header ignored, sees nothing
