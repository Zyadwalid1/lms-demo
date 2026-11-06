"""M1 marketplace API: catalogue totals and filters, cart badge count, Personal Plan
access on the course page, and typed responses for everything the frontend uses."""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from apps.commerce import services as shop
from apps.commerce.models import Plan, PlanPrice, Subscription
from apps.identity.models import InstructorProfile
from core.tenancy import tenant_context
from core.tests import factories as f
from core.tests.base import SchemaTransactionTestCase


class MarketplaceApiTest(SchemaTransactionTestCase):
    def setUp(self):
        self.staff, self.teacher, self.sara, self.omar = f.users()
        cat = f.money(self.staff)
        InstructorProfile.objects.create(user=self.teacher, status="approved")
        self.py = f.course(staff=self.staff, owner=self.teacher, slug="py", title="Python", category=cat)
        self.js = f.course(staff=self.staff, owner=self.teacher, slug="js", title="JavaScript", category=cat)
        self.free = f.course(staff=self.staff, owner=self.teacher, slug="git", title="Git Basics", free=True)

    def test_catalogue_total_and_filters(self):
        with tenant_context(user_id=self.staff.id, staff=True):
            type(self.py).objects.filter(pk=self.py.pk).update(rating_avg=4.6)
        first = self.client.get("/api/v1/catalog/courses?limit=2").json()
        self.assertEqual((first["total"], len(first["items"])), (3, 2))
        more = self.client.get(f"/api/v1/catalog/courses?limit=2&cursor={first['next_cursor']}").json()
        self.assertIsNone(more["total"])  # counted once, on the first page
        self.assertEqual(len(more["items"]), 1)
        self.assertEqual(
            [c["slug"] for c in self.client.get("/api/v1/catalog/courses?rating=4.5").json()["items"]], ["py"]
        )
        self.assertEqual(
            [c["slug"] for c in self.client.get("/api/v1/catalog/courses?price=free").json()["items"]],
            ["git"],
        )
        self.assertEqual(self.client.get("/api/v1/catalog/courses?rating=9").status_code, 422)
        found = self.client.get("/api/v1/catalog/courses?q=python").json()
        self.assertEqual((found["total"], found["items"][0]["slug"]), (1, "py"))

    def test_cart_count_wishlist_and_plan_access(self):
        self.client.force_login(self.sara)
        self.assertEqual(self.client.get("/api/v1/commerce/cart/count").json(), {"count": 0})
        self.client.post(f"/api/v1/commerce/wishlist/{self.js.id}/toggle")
        self.assertEqual(
            [c["slug"] for c in self.client.get("/api/v1/commerce/wishlist").json()["items"]], ["js"]
        )
        for c in (self.py, self.js):
            self.assertEqual(self.client.post("/api/v1/commerce/cart", data={"course_id": str(c.id)},
                                              content_type="application/json").json(), {"ok": True})  # fmt: skip
        self.assertEqual(self.client.get("/api/v1/commerce/cart/count").json(), {"count": 2})
        self.assertEqual(
            self.client.get("/api/v1/commerce/wishlist").json()["items"], []
        )  # moved to the cart
        cart = self.client.get("/api/v1/commerce/cart?currency=USD").json()
        self.assertEqual((cart["currency"], len(cart["lines"])), ("USD", 2))
        self.assertEqual(self.client.delete(f"/api/v1/commerce/cart/{self.js.id}").json(), {"ok": True})

        viewer = lambda: self.client.get("/api/v1/catalog/courses/py").json()["viewer"]  # noqa: E731
        self.assertFalse(viewer()["plan_access"])
        with tenant_context(user_id=self.staff.id, staff=True):
            type(self.py).objects.filter(pk=self.py.pk).update(in_subscription=True)
            plan = Plan.objects.create(
                code="personal", name="Personal", audience="personal", interval="month"
            )
            PlanPrice.objects.create(
                plan=plan, currency_id="GBP", amount_minor=1999, stripe_price_id="price_x"
            )
            Subscription.objects.create(user=self.sara, plan=plan, currency_id="GBP", status="active", seats=1,
                                        current_period_end=timezone.now() + timedelta(days=20))  # fmt: skip
        self.assertTrue(viewer()["plan_access"])
        e = self.client.post("/api/v1/commerce/plan/enroll", data={"course_id": str(self.py.id)},
                             content_type="application/json")  # fmt: skip
        self.assertEqual(e.status_code, 200, e.content)
        v = viewer()
        self.assertEqual((v["plan_access"], v["enrollment_id"] is not None), (False, True))
        subs = self.client.get("/api/v1/commerce/subscriptions").json()
        self.assertEqual((subs[0]["plan"], subs[0]["status"]), ("Personal", "active"))

    def test_free_course_checkout_needs_no_payment(self):
        self.client.force_login(self.omar)
        with mock.patch("apps.commerce.gateway.create_checkout_session") as stripe:
            r = self.client.post("/api/v1/commerce/checkout", data={"course_ids": [str(self.free.id)], "currency": "GBP"},
                                 content_type="application/json").json()  # fmt: skip
        stripe.assert_not_called()
        self.assertEqual((r["checkout_url"], r["status"]), (None, "paid"))
        self.assertIsNotNone(self.client.get("/api/v1/catalog/courses/git").json()["viewer"]["enrollment_id"])
        with tenant_context(user_id=self.omar.id):
            self.assertEqual(
                shop.price_cart(user=self.omar, course_ids=[self.py.id], currency="GBP")["total"] > 0, True
            )
