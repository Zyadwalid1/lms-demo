"""Files handed in with an assignment: checked uploads under the learner's own enrolment,
verified with storage at submission, never reusable by anyone else, and abandoned
uploads purged (without touching course files or handed-in work)."""

from datetime import timedelta

from django.utils import timezone

from apps.catalog.models import Assignment, MediaAsset
from apps.learning import uploads
from core.tenancy import tenant_context

from .test_api_learner import ApiBase
from .test_resources import PDF, FakeBlobs


class SubmissionFilesTest(ApiBase):
    def setUp(self):
        super().setUp()
        self.fake = FakeBlobs()
        for p in self.fake.patches():
            p.start()
            self.addCleanup(p.stop)
        self.buy(self.sara, self.django)
        self.enrol = self.get("/learning/my/courses").json()["items"][0]["enrollment_id"]
        player = self.get(f"/learning/enrollments/{self.enrol}").json()
        self.key = player["sections"][0]["lectures"][3]["key"]  # the assignment
        with tenant_context(staff=True):
            Assignment.objects.filter(lecture__lecture_key=self.key).update(submission_types=["text", "file"])

    def start(self, name="essay.pdf", size=2048):
        return self.post(f"/learning/enrollments/{self.enrol}/assignments/{self.key}/uploads",
                         {"filename": name, "size_bytes": size})  # fmt: skip

    def submit(self, **body):
        return self.post(f"/learning/enrollments/{self.enrol}/assignments/{self.key}/submissions", body)

    def test_upload_then_hand_in(self):
        self.assertEqual(self.start("run.exe").status_code, 400)  # type allow-list
        up = self.start().json()
        self.assertIn(f"submissions/{self.enrol}/", up["upload_url"])
        self.assertEqual(up["headers"]["Content-Type"], PDF)

        # nothing arrived in storage yet
        self.assertEqual(self.submit(asset_ids=[up["asset_id"]]).status_code, 400)
        key = up["upload_url"].split("https://blob.test/")[1].split("?")[0]
        self.fake.blobs[key] = {"size": 2048, "content_type": PDF}

        self.login(self.omar)  # someone else's upload cannot be handed in, even by id
        self.assertEqual(self.submit(asset_ids=[up["asset_id"]]).status_code, 404)

        self.login(self.sara)
        sub = self.submit(text="See attached", asset_ids=[up["asset_id"]]).json()
        self.assertEqual((sub["files"][0]["filename"], sub["text"]), ("essay.pdf", "See attached"))
        lecture = self.get(f"/learning/enrollments/{self.enrol}/lectures/{self.key}").json()
        self.assertEqual(lecture["assignment"]["submissions"][0]["files"][0]["size_bytes"], 2048)

    def test_text_only_assignment_refuses_files(self):
        with tenant_context(staff=True):
            Assignment.objects.filter(lecture__lecture_key=self.key).update(submission_types=["text"])
        self.assertEqual(self.start().status_code, 400)

    def test_purge_keeps_handed_in_and_course_files(self):
        kept = self.start().json()
        key = kept["upload_url"].split("https://blob.test/")[1].split("?")[0]
        self.fake.blobs[key] = {"size": 2048, "content_type": PDF}
        self.submit(asset_ids=[kept["asset_id"]])
        abandoned = self.start("draft.pdf").json()
        with tenant_context(staff=True):
            MediaAsset.objects.filter(storage_key__startswith="submissions/").update(
                created_at=timezone.now() - timedelta(days=2)
            )
            self.assertEqual(uploads.purge_abandoned(), 1)
            left = set(
                MediaAsset.objects.filter(storage_key__startswith="submissions/").values_list("id", flat=True)
            )
        self.assertEqual({str(i) for i in left}, {kept["asset_id"]})
        self.assertNotIn(abandoned["asset_id"], {str(i) for i in left})
