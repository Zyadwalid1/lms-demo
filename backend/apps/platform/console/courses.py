"""Console > Courses (mockup 45): every course, bulk actions, categories."""

from django.utils import timezone
from ninja import Field, Schema

from apps.catalog import services as catalog
from apps.catalog.models import Course

from ..services import audit_request
from .common import ConsoleOkOut, router, staff


class ConsoleUnpublishIn(Schema):
    notes: str = Field("", max_length=1000)


@router.post("/courses/{course_id}/unpublish", response=ConsoleOkOut)
def unpublish(request, course_id: str, body: ConsoleUnpublishIn):
    """Take a course off the marketplace (existing learners keep access)."""
    staff(request)
    with catalog.authoring():
        Course.objects.filter(pk=course_id).update(status="unlisted", updated_at=timezone.now())
    audit_request(request, "course.unpublish", "course", course_id, {"notes": body.notes[:500]})
    return {"ok": True}
