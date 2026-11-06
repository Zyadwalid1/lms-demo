"""Studio API: who may author, the course builder, sanitising, Bunny upload sessions,
versions and review, company courses, coupons, grading and revenue."""

import hashlib
import os
from unittest import mock

from django.utils import timezone

from apps.catalog import services as cat
from apps.catalog.models import Course, CourseVersion
from apps.identity.models import InstructorProfile, User
from apps.org import services as org_services
from apps.org.models import OrgMember
from core.tenancy import tenant_context
from core.tests import factories as f
from core.tests.base import SchemaTransactionTestCase

API = "/api/v1/studio"


class StudioApiTest(SchemaTransactionTestCase):
    def setUp(self):
        self.staff, self.teacher, self.sara, self.omar = f.users()
        f.money(self.staff)
        InstructorProfile.objects.create(user=self.teacher, status="approved", headline="Teacher")

    def as_(self, user):
        self.client.force_login(user)

    def call(self, method, path, data=None, **headers):
        fn = getattr(self.client, method)
        if method in ("get", "delete"):
            return fn(API + path, **headers)
        return fn(API + path, data=data or {}, content_type="application/json", **headers)

    def test_build_upload_review_and_publish(self):
        # an unapproved user cannot create marketplace courses
        self.as_(self.omar)
        self.assertEqual(self.call("post", "/courses", {"title": "Hacking 101"}).status_code, 403)
        self.assertEqual(
            self.call("post", "/instructor-profile", {"headline": "Security trainer"}).json()["status"],
            "pending",
        )

        self.as_(self.teacher)
        c = self.call("post", "/courses", {"title": "Clean Code <b>Now</b>"}).json()
        course = self.call("get", f"/courses/{c['id']}").json()
        self.assertEqual(course["title"], "Clean Code Now")  # tags stripped from plain fields
        v = course["working_version"]["id"]
        sec = self.call("post", f"/versions/{v}/sections", {"title": "Basics"}).json()["id"]
        art = self.call("post", f"/sections/{sec}/lectures", {"kind": "article", "title": "Read",
                         "body": '<p onclick="steal()">Hi<script>alert(1)</script><a href="javascript:x">l</a></p>'}).json()  # fmt: skip
        self.call(
            "patch",
            f"/courses/{c['id']}",
            {"description": '<img src="https://x.test/a.png" onerror="steal()">'},
        )

        # video: we create it at Bunny, the browser gets a signature for that one video only
        with tenant_context(user_id=self.staff.id, staff=True):
            from apps.catalog.models import VideoLibrary

            VideoLibrary.objects.create(name="L", environment="test", bunny_library_id=77, cdn_hostname="vz.t",
                                        is_default=True)  # fmt: skip
        with mock.patch.dict(os.environ, {"BUNNY_STREAM_API_KEY": "secret-key"}), \
             mock.patch("apps.catalog.bunny.create_video", return_value="11111111-2222-3333-4444-555555555555"):  # fmt: skip
            up = self.call(
                "post", "/media/videos", {"course_id": c["id"], "title": "Intro", "size_bytes": 1000}
            ).json()
        h = up["upload"]["headers"]
        expected = hashlib.sha256(
            f"77secret-key{h['AuthorizationExpire']}{h['VideoId']}".encode()
        ).hexdigest()
        self.assertEqual(h["AuthorizationSignature"], expected)
        self.assertNotIn("secret-key", str(up))  # the API key itself never leaves the server
        self.assertEqual(self.call("get", f"/media/{up['asset_id']}").json()["status"], "awaiting_upload")

        quiz_lecture = self.call(
            "post", f"/sections/{sec}/lectures", {"kind": "quiz", "title": "Check"}
        ).json()
        tree = self.call("get", f"/courses/{c['id']}").json()["working_version"]
        quiz_id = tree["sections"][0]["lectures"][1]["quiz"]["id"]
        self.call("post", f"/quizzes/{quiz_id}/questions", {"kind": "single_choice", "prompt": "Pick", "options": [
            {"body": "A", "is_correct": True}, {"body": "B"}]})  # fmt: skip
        r = self.call("put", f"/sections/{sec}/lectures/order", {"ids": [quiz_lecture["id"], art["id"]]})
        self.assertEqual(r.status_code, 200, r.content)
        tree = self.call("get", f"/courses/{c['id']}").json()
        lectures = tree["working_version"]["sections"][0]["lectures"]
        self.assertEqual([lec["kind"] for lec in lectures], ["quiz", "article"])
        body = lectures[1]["body"]
        for bad in ("onclick", "<script", "javascript:"):
            self.assertNotIn(bad, body)
        self.assertNotIn("onerror", tree["description"])
        self.assertTrue(
            lectures[0]["quiz"]["questions"][0]["options"][0]["is_correct"]
        )  # editors see answers
        self.assertEqual(tree["working_version"]["checklist"], [])

        # another instructor cannot see or touch it
        other = User.objects.create_user("ana@learnhub.example.com", "x")
        InstructorProfile.objects.create(user=other, status="approved")
        self.as_(other)
        self.assertEqual(self.call("get", f"/courses/{c['id']}").status_code, 404)
        self.assertEqual(self.call("delete", f"/lectures/{art['id']}").status_code, 404)

        # submit -> staff review -> live; the live version is then locked
        self.as_(self.teacher)
        tier = self.call("get", "/price-tiers").json()[4]["id"]
        self.call("put", f"/courses/{c['id']}/price", {"tier_id": tier})
        self.assertEqual(
            self.call("post", f"/versions/{v}/submit", {"change_summary": "v1"}).json()["status"], "in_review"
        )
        with tenant_context(user_id=self.staff.id, staff=True):
            cat.approve(version=CourseVersion.objects.get(pk=v), reviewer=self.staff)
        self.assertEqual(self.call("delete", f"/lectures/{art['id']}").status_code, 400)  # version_locked
        draft = self.call("post", f"/courses/{c['id']}/draft").json()
        self.assertNotEqual(draft["version_id"], v)
        self.assertEqual(Course.objects.get(pk=c["id"]).live_version_id.hex, v.replace("-", ""))

    def test_company_course_coupons_grading_and_revenue(self):
        hr = User.objects.create_user("hana@acme.example.com", "x")
        acme = org_services.create_organization(name="Acme", slug="acme", owner=hr)
        H = {"HTTP_X_ORG_ID": str(acme.id)}
        with tenant_context(org_id=acme.id, user_id=hr.id):
            OrgMember.objects.create(org=acme, user=self.omar, role="manager", joined_at=timezone.now())
        self.as_(hr)
        c = self.call("post", "/courses", {"title": "Acme Induction"}, **H).json()
        self.assertEqual(self.call("get", f"/courses/{c['id']}", **H).json()["ownership"], "organization")
        self.as_(self.omar)  # a manager is not a company author
        self.assertEqual(self.call("get", f"/courses/{c['id']}", **H).status_code, 403)

        # marketplace course with an assignment, bought by Sara
        course = f.course(staff=self.staff, owner=self.teacher, slug="py", title="Python")
        self.as_(self.teacher)
        self.assertEqual(self.call("post", f"/courses/{course.id}/coupons", {"code": "PY50", "percent_off": 50,
                                                                             "days": 7}).status_code, 200)  # fmt: skip
        self.assertEqual(self.call("post", f"/courses/{course.id}/coupons", {"code": "py50", "percent_off": 10,
                                                                             "days": 7}).status_code, 400)  # fmt: skip
        from apps.commerce import services as shop

        with mock.patch(
            "apps.commerce.gateway.create_checkout_session", return_value={"id": "cs_1", "url": "u"}
        ):
            with tenant_context(user_id=self.sara.id):
                order = shop.create_order(user=self.sara, course_ids=[course.id], currency="GBP")["order"]
        with tenant_context(user_id=self.staff.id, staff=True):
            shop.fulfil_order(
                order_id=order.id, payment_intent="pi_9", amount_minor=order.total_minor, currency="GBP"
            )
        self.assertGreater(self.call("get", "/revenue").json()["balance"]["pending"], 0)

        from apps.learning import services as learning
        from apps.learning.models import Enrollment

        with tenant_context(user_id=self.sara.id):
            e = Enrollment.objects.get(user=self.sara, course=course)
            a = course.live_version.lectures.get(kind="assignment").assignment
            learning.submit_assignment(enrollment=e, assignment=a, text_body="<p>done</p>")
        queue = self.call("get", "/grading").json()
        self.assertEqual(len(queue["submissions"]), 1)
        self.assertEqual(self.call("get", f"/courses/{course.id}/students").json()[0]["name"], "Sara Ahmed")
        other = User.objects.create_user("ana@learnhub.example.com", "x")
        self.as_(other)
        self.assertEqual(self.call("get", "/grading").json()["submissions"], [])  # nothing of Tom's
        self.assertEqual(self.call("post", f"/submissions/{queue['submissions'][0]['id']}/grade",
                                   {"score": 100}).status_code, 404)  # fmt: skip
        self.as_(self.teacher)
        r = self.call(
            "post", f"/submissions/{queue['submissions'][0]['id']}/grade", {"score": 80, "feedback": "Good"}
        )
        self.assertEqual(r.json(), {"status": "graded", "passed": True})


class ContentWriteLockTest(SchemaTransactionTestCase):
    def test_course_content_is_written_only_by_authoring_services(self):
        staff, teacher, sara, _ = f.users()
        f.money(staff)
        course = f.course(staff=staff, owner=teacher, slug="locked", title="Locked")
        from django.db import connection

        for who in (sara, teacher):  # even the course's own instructor, outside the services
            with tenant_context(user_id=who.id), connection.cursor() as cur:
                cur.execute("UPDATE catalog.courses SET title = 'pwned' WHERE id = %s", [course.id])
                self.assertEqual(cur.rowcount, 0)
                cur.execute(
                    "UPDATE catalog.lectures SET title = 'pwned' WHERE version_id = %s",
                    [course.live_version_id],
                )
                self.assertEqual(cur.rowcount, 0)
        with tenant_context(user_id=teacher.id):
            cat.update_course(course=Course.objects.get(pk=course.pk), subtitle="Through the service")
            self.assertEqual(Course.objects.get(pk=course.pk).subtitle, "Through the service")
            with connection.cursor() as cur:  # and the lock is closed again afterwards
                cur.execute("SELECT COALESCE(current_setting('app.author', true), '')")
                self.assertEqual(cur.fetchone()[0], "")
