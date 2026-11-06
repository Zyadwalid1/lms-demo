"""Files a learner hands in with an assignment, in the same private Azure container as
lecture files and with the same checks (apps/catalog/resources.py):

    1. start_upload   the learner may submit files to this assignment; name, type and size
                      are checked; a 15-minute, write-only link for one blob comes back
    2. (browser PUTs the file straight to Azure)
    3. claim          at submission: each upload must be the learner's own, for this
                      enrolment, and Azure must confirm what really arrived

Blobs live under submissions/<enrolment id>/ so they can never be confused with course
content. Uploads never handed in are removed after a day (purge_abandoned).
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.catalog.models import Assignment, MediaAsset
from apps.catalog.resources import ALLOWED, FILE_KINDS, _ensure_storage, _safe_name
from apps.catalog.services import authoring
from core import html, storage
from core.errors import ServiceError

from .models import Enrollment, SubmissionFile

MAX_FILES = 5


def _prefix(enrollment: Enrollment) -> str:
    return f"submissions/{enrollment.id}/"


def start_upload(
    *, enrollment: Enrollment, assignment: Assignment, user, filename: str, size_bytes: int
) -> dict:
    from .services import _check_access

    _check_access(enrollment)
    if "file" not in assignment.submission_types:
        raise ServiceError("type_not_allowed", "This assignment does not take files.")
    _ensure_storage()
    if size_bytes <= 0 or size_bytes > settings.RESOURCE_MAX_BYTES:
        raise ServiceError(
            "file_size", f"Files can be up to {settings.RESOURCE_MAX_BYTES // (1024 * 1024)} MB."
        )
    name, ext = _safe_name(filename)
    content_type, kind = ALLOWED[ext]
    key = f"{_prefix(enrollment)}{uuid.uuid4().hex}/{name}"
    with transaction.atomic(), authoring():
        asset = MediaAsset.objects.create(
            kind=kind, status=MediaAsset.Status.AWAITING_UPLOAD, uploaded_by=user,
            owner_org_id=enrollment.course.owner_org_id, storage_key=key, mime_type=content_type,
            original_filename=html.plain(filename, 255), size_bytes=size_bytes,
        )  # fmt: skip
    return {
        "asset_id": asset.id,
        "upload_url": storage.upload_url(key),
        "method": "PUT",
        "headers": {"x-ms-blob-type": "BlockBlob", "Content-Type": content_type},
        "expires_in": 15 * 60,
        "max_bytes": settings.RESOURCE_MAX_BYTES,
    }


def claim(*, enrollment: Enrollment, user, asset_ids) -> list[MediaAsset]:
    """The uploads named in a submission, verified. Called inside submit_assignment's
    transaction, so a refused file leaves nothing behind."""
    ids = list(dict.fromkeys(str(a) for a in asset_ids))
    if len(ids) > MAX_FILES:
        raise ServiceError("too_many_files", f"Hand in up to {MAX_FILES} files.")
    assets = list(
        MediaAsset.objects.filter(
            pk__in=ids, uploaded_by=user, kind__in=FILE_KINDS, storage_key__startswith=_prefix(enrollment)
        ).exclude(Exists(SubmissionFile.objects.filter(asset_id=OuterRef("pk"))))
    )
    if len(assets) != len(ids):
        raise ServiceError("not_found", "One of the files was not found. Upload it again.", status=404)
    for asset in assets:
        if asset.status == MediaAsset.Status.AWAITING_UPLOAD:
            found = storage.properties(asset.storage_key)  # what Azure really holds
            if found is None:
                raise ServiceError("not_uploaded", f"{asset.original_filename} has not finished uploading.")
            content_type = found["content_type"].split(";")[0].strip().lower()
            if not (0 < found["size"] <= settings.RESOURCE_MAX_BYTES and content_type == asset.mime_type):
                raise ServiceError(
                    "file_rejected", f"{asset.original_filename} did not match its type or size."
                )
            with authoring():
                MediaAsset.objects.filter(pk=asset.pk).update(
                    status=MediaAsset.Status.READY, size_bytes=found["size"], updated_at=timezone.now()
                )
        elif asset.status != MediaAsset.Status.READY:
            raise ServiceError("file_rejected", f"{asset.original_filename} cannot be used.")
    return assets


def purge_abandoned(*, older_than: timedelta = timedelta(days=1)) -> int:
    """Uploads started but never handed in."""
    handed_in = SubmissionFile.objects.filter(asset_id=OuterRef("pk"))
    stale = MediaAsset.objects.filter(
        storage_key__startswith="submissions/", created_at__lt=timezone.now() - older_than
    ).exclude(Exists(handed_in))
    removed = 0
    for asset_id, key in stale.order_by("created_at").values_list("id", "storage_key")[:500]:
        with transaction.atomic(), authoring():
            locked = MediaAsset.objects.select_for_update().filter(pk=asset_id).first()
            if locked is None or SubmissionFile.objects.filter(asset_id=asset_id).exists():
                continue
            locked.delete()
            transaction.on_commit(lambda key=key: storage.delete(key) if storage.configured() else None)
            removed += 1
    return removed
