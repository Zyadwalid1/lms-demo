"""Console > Approvals (mockup 25): the course review queue and decisions."""

from datetime import datetime
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Schema

from apps.catalog import services as catalog
from apps.catalog.models import CourseVersion
from apps.catalog.studio import _editor_tree
from apps.catalog.studio_schemas import StudioEditorSectionOut
from core import html
from core.errors import ServiceError

from ..services import audit_request
from .common import ConsoleStatusOut, router, staff


class ConsoleNotesIn(Schema):
    notes: str = Field("", max_length=1000)


class ConsoleReviewRowOut(Schema):
    version_id: UUID
    course_id: UUID
    title: str
    number: int
    submitted_by: str | None
    submitted_at: datetime | None
    change_summary: str
    first_release: bool


class ConsoleReviewCourseOut(Schema):
    id: UUID
    title: str
    subtitle: str
    description: str


class ConsoleReviewVersionOut(Schema):
    version_id: UUID
    course: ConsoleReviewCourseOut
    status: str
    checklist: list[str]
    sections: list[StudioEditorSectionOut]


@router.get("/review/courses", response=list[ConsoleReviewRowOut])
def review_queue(request):
    staff(request)
    rows = (
        CourseVersion.objects.filter(status="in_review")
        .select_related("course", "submitted_by")
        .order_by("submitted_at")
    )
    return [{"version_id": v.id, "course_id": v.course_id, "title": v.course.title, "number": v.number,
             "submitted_by": v.submitted_by.full_name if v.submitted_by else None, "submitted_at": v.submitted_at,
             "change_summary": v.change_summary, "first_release": v.course.live_version_id is None} for v in rows]  # fmt: skip


@router.get("/review/versions/{version_id}", response=ConsoleReviewVersionOut)
def review_version(request, version_id: str):
    staff(request)
    v = get_object_or_404(CourseVersion.objects.select_related("course"), pk=version_id)
    return {"version_id": v.id, "course": {"id": v.course_id, "title": v.course.title, "subtitle": v.course.subtitle,
                                           "description": v.course.description},
            "status": v.status, "checklist": catalog.publish_checklist(v), "sections": _editor_tree(v)}  # fmt: skip


@router.post("/review/versions/{version_id}/approve", response=ConsoleStatusOut)
def approve(request, version_id: str, body: ConsoleNotesIn):
    staff(request)
    v = catalog.approve(version=get_object_or_404(CourseVersion, pk=version_id), reviewer=request.user,
                        notes=html.plain(body.notes, 1000))  # fmt: skip
    audit_request(request, "course.approve", "course_version", v.id)
    return {"status": v.status}


@router.post("/review/versions/{version_id}/request-changes", response=ConsoleStatusOut)
def request_changes(request, version_id: str, body: ConsoleNotesIn):
    staff(request)
    if not body.notes.strip():
        raise ServiceError("notes_required", "Tell the instructor what to change.")
    v = catalog.request_changes(version=get_object_or_404(CourseVersion, pk=version_id), reviewer=request.user,
                                notes=html.plain(body.notes, 1000))  # fmt: skip
    audit_request(request, "course.request_changes", "course_version", v.id)
    return {"status": v.status}
