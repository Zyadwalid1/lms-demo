"""Lecture files: checked uploads, enrolled-only downloads, and files shared between
course versions are only purged once nothing uses them."""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from apps.catalog import resources
from apps.catalog import services as cat
from apps.catalog.models import CourseVersion, Lecture, LectureResource, MediaAsset
from apps.identity.models import InstructorProfile
from apps.learning import services as learning
from core.tenancy import tenant_context
from core.tests import factories as f
from core.tests.base import SchemaTransactionTestCase

PDF = "application/pdf"


class FakeBlobs:
    """Stands in for Azure: records links handed out and what was 'uploaded'."""

    def __init__(self):
        self.blobs, self.deleted = {}, []

    def patches(self):
        return [
            mock.patch("core.storage.configured", return_value=True),
            mock.patch("core.storage.upload_url", side_effect=lambda key: f"https://blob.test/{key}?sp=cw"),
            mock.patch(
                "core.storage.download_url",
                side_effect=lambda key, name=None: f"https://blob.test/{key}?sp=r",
            ),
            mock.patch("core.storage.properties", side_effect=lambda key: self.blobs.get(key)),
            mock.patch("core.storage.delete", side_effect=self.deleted.append),
        ]


class LectureFilesTest(SchemaTransactionTestCase):
    def setUp(self):
        self.staff, self.teacher, self.sara, self.omar = f.users()
        f.money(self.staff)
        InstructorProfile.objects.create(user=self.teacher, status="approved")
        self.course = f.course(staff=self.staff, owner=self.teacher, slug="py", title="Python", free=True)
        self.fake = FakeBlobs()
        for p in self.fake.patches():
            p.start()
            self.addCleanup(p.stop)

    def studio(self, method, path, data=None):
        fn = getattr(self.client, method)
        url = "/api/v1/studio" + path
        return (
            fn(url)
            if method in ("get", "delete")
            else fn(url, data=data or {}, content_type="application/json")
        )

    def test_upload_attach_download_and_purge(self):
        self.client.force_login(self.teacher)
        draft = self.studio("post", f"/courses/{self.course.id}/draft").json()["version_id"]
        with tenant_context(user_id=self.teacher.id):
            lec = Lecture.objects.get(version_id=draft, kind="article")

        # type, size and HTML are refused before any link is issued
        for name, size in (("evil.html", 10), ("x.svg", 10), ("big.pdf", 200 * 1024 * 1024)):
            r = self.studio(
                "post", f"/lectures/{lec.id}/resources/uploads", {"filename": name, "size_bytes": size}
            )
            self.assertEqual(r.status_code, 400, name)
        up = self.studio("post", f"/lectures/{lec.id}/resources/uploads",
                         {"filename": "Week 1 Slides (final).PDF", "size_bytes": 2048}).json()  # fmt: skip
        self.assertEqual(up["headers"]["Content-Type"], PDF)
        key = up["upload_url"].split("https://blob.test/")[1].split("?")[0]
        self.assertTrue(
            key.startswith(f"courses/{self.course.id}/") and key.endswith("/week-1-slides-final.pdf")
        )

        # nothing uploaded yet / wrong type uploaded
        body = {"asset_id": up["asset_id"], "title": "Slides"}
        self.assertEqual(self.studio("post", f"/lectures/{lec.id}/resources", body).status_code, 400)
        self.fake.blobs[key] = {"size": 2048, "content_type": "text/html"}
        self.assertEqual(self.studio("post", f"/lectures/{lec.id}/resources", body).status_code, 400)
        self.assertIn(key, self.fake.deleted)  # a mismatching upload is removed

        up = self.studio(
            "post", f"/lectures/{lec.id}/resources/uploads", {"filename": "notes.pdf", "size_bytes": 10}
        ).json()
        key = up["upload_url"].split("https://blob.test/")[1].split("?")[0]
        self.fake.blobs[key] = {"size": 900, "content_type": PDF}
        res = self.studio(
            "post", f"/lectures/{lec.id}/resources", {"asset_id": up["asset_id"], "title": "Notes"}
        ).json()
        self.assertEqual((res["title"], res["size_bytes"], res["filename"]), ("Notes", 900, "notes.pdf"))
        tree = self.studio("get", f"/courses/{self.course.id}").json()
        self.assertEqual(
            [
                r["title"]
                for s in tree["working_version"]["sections"]
                for lec_ in s["lectures"]
                for r in lec_["resources"]
            ],
            ["Notes"],
        )

        # another instructor cannot use or see it
        self.client.force_login(self.omar)
        self.assertEqual(self.studio("get", f"/resources/{res['id']}/download").status_code, 404)

        # publish the draft; then a new draft shares the same file
        self.client.force_login(self.teacher)
        self.studio("post", f"/versions/{draft}/submit")
        with tenant_context(user_id=self.staff.id, staff=True):
            cat.approve(version=CourseVersion.objects.get(pk=draft), reviewer=self.staff)
        draft2 = self.studio("post", f"/courses/{self.course.id}/draft").json()["version_id"]
        with tenant_context(user_id=self.teacher.id):
            copy = LectureResource.objects.get(lecture__version_id=draft2)
        self.assertEqual(self.studio("delete", f"/resources/{copy.id}").json(), {"ok": True})

        # learners: enrolled only, live version only
        with tenant_context(user_id=self.sara.id):
            e = learning.enrol(user=self.sara, course=self.course, source="free")
        self.client.force_login(self.sara)
        lecture = self.client.get(f"/api/v1/learning/enrollments/{e.id}/lectures/{lec.lecture_key}").json()
        self.assertEqual([r["title"] for r in lecture["resources"]], ["Notes"])
        dl = f"/api/v1/learning/enrollments/{e.id}/lectures/{lec.lecture_key}/resources/{res['id']}/download"
        self.assertTrue(self.client.get(dl).json()["url"].endswith("?sp=r"))
        bad = f"/api/v1/learning/enrollments/{e.id}/lectures/{lec.lecture_key}/resources/{copy.id}/download"
        self.assertEqual(self.client.get(bad).status_code, 404)  # the deleted draft copy
        self.client.force_login(self.omar)
        self.assertEqual(self.client.get(dl).status_code, 404)  # not his enrolment

        # purge: the live version still uses the file; the abandoned uploads go
        with tenant_context(user_id=self.staff.id, staff=True):
            MediaAsset.objects.filter(kind="document").update(created_at=timezone.now() - timedelta(days=2))
            self.fake.deleted.clear()
            removed = resources.purge_unused()
            self.assertTrue(MediaAsset.objects.filter(storage_key=key).exists())
        self.assertEqual(removed, 1)  # the rejected upload; the live file stays
        self.assertEqual(len(self.fake.deleted), 1)
        self.assertNotIn(key, self.fake.deleted)
