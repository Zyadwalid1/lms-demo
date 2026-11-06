"""Lecture files (slides, worksheets, data sets) in private Azure Blob storage.

    1. start_upload   checks name/type/size, creates an 'awaiting_upload' asset and
                      returns a 15-minute, write-only link for that one blob
    2. (browser PUTs the file straight to Azure; the app never streams it)
    3. attach         reads the blob's real size and type from Azure, refuses anything
                      that does not match, then adds it to the lecture
    4. download_url   1-hour, read-only link that always downloads (never renders)

A file can be shared by several course versions (a new draft copies the rows, not the
file), so deleting a resource never deletes the blob directly: `purge_unused` removes
files that no lecture uses any more, once a day.
"""

import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, Max, OuterRef
from django.utils import timezone
from django.utils.text import slugify

from core import html, storage
from core.errors import ServiceError

from .models import Lecture, LectureResource, MediaAsset
from .services import _editable, authored, authoring

# extension -> (content type the upload must use, asset kind). No HTML/SVG/scripts.
ALLOWED = {
    ".pdf": ("application/pdf", "document"),
    ".doc": ("application/msword", "document"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
    ".xls": ("application/vnd.ms-excel", "document"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "document"),
    ".ppt": ("application/vnd.ms-powerpoint", "document"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "document"),
    ".odt": ("application/vnd.oasis.opendocument.text", "document"),
    ".ods": ("application/vnd.oasis.opendocument.spreadsheet", "document"),
    ".odp": ("application/vnd.oasis.opendocument.presentation", "document"),
    ".txt": ("text/plain", "document"),
    ".csv": ("text/csv", "document"),
    ".rtf": ("application/rtf", "document"),
    ".zip": ("application/zip", "archive"),
    ".png": ("image/png", "image"),
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".webp": ("image/webp", "image"),
    ".mp3": ("audio/mpeg", "audio"),
    ".m4a": ("audio/mp4", "audio"),
}
FILE_KINDS = ("document", "archive", "image", "audio")


def _safe_name(filename: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(os.path.basename(filename or "").strip())
    ext = ext.lower()
    if ext not in ALLOWED:
        allowed = ", ".join(sorted(e.lstrip(".") for e in ALLOWED))
        raise ServiceError("file_type", f"This file type is not allowed. Allowed: {allowed}.")
    return f"{slugify(stem)[:80] or 'file'}{ext}", ext


def _ensure_storage() -> None:
    if not storage.configured():
        raise ServiceError("files_unavailable", "File uploads are not configured.", status=503)


def start_upload(*, lecture: Lecture, user, filename: str, size_bytes: int) -> dict:
    _editable(lecture.version)
    _ensure_storage()
    if size_bytes <= 0 or size_bytes > settings.RESOURCE_MAX_BYTES:
        raise ServiceError(
            "file_size", f"Files can be up to {settings.RESOURCE_MAX_BYTES // (1024 * 1024)} MB."
        )
    if lecture.resources.count() >= settings.RESOURCES_PER_LECTURE:
        raise ServiceError(
            "too_many_files", f"A lecture can have up to {settings.RESOURCES_PER_LECTURE} files."
        )
    name, ext = _safe_name(filename)
    content_type, kind = ALLOWED[ext]
    key = f"courses/{lecture.version.course_id}/{uuid.uuid4().hex}/{name}"
    with transaction.atomic(), authoring():
        asset = MediaAsset.objects.create(
            kind=kind, status=MediaAsset.Status.AWAITING_UPLOAD, uploaded_by=user,
            owner_org_id=lecture.owner_org_id, storage_key=key, mime_type=content_type,
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


def attach(*, lecture: Lecture, user, asset_id, title: str = "") -> LectureResource:
    _editable(lecture.version)
    asset = MediaAsset.objects.filter(
        pk=asset_id,
        uploaded_by=user,
        kind__in=FILE_KINDS,
        storage_key__startswith=f"courses/{lecture.version.course_id}/",
    ).first()
    if asset is None:
        raise ServiceError("not_found", "Upload not found.", status=404)
    if asset.status == MediaAsset.Status.AWAITING_UPLOAD:
        # ask Azure what really arrived (the browser's word is not enough)
        found = storage.properties(asset.storage_key)
        if found is None:
            raise ServiceError("not_uploaded", "The file has not finished uploading.")
        content_type = found["content_type"].split(";")[0].strip().lower()
        ok = 0 < found["size"] <= settings.RESOURCE_MAX_BYTES and content_type == asset.mime_type
        with transaction.atomic(), authoring():
            MediaAsset.objects.filter(pk=asset.pk, status=MediaAsset.Status.AWAITING_UPLOAD).update(
                status=MediaAsset.Status.READY if ok else MediaAsset.Status.FAILED,
                size_bytes=found["size"], updated_at=timezone.now(),
            )  # fmt: skip
        if not ok:
            storage.delete(asset.storage_key)
            raise ServiceError("file_rejected", "The uploaded file did not match its type or size limit.")
    with transaction.atomic(), authoring():
        asset = MediaAsset.objects.select_for_update().get(pk=asset.pk)
        if asset.status != MediaAsset.Status.READY:
            raise ServiceError("file_rejected", "This upload cannot be used.")
        position = (lecture.resources.aggregate(m=Max("position"))["m"] or 0) + 1
        name = html.plain(title, 200).strip() or os.path.splitext(asset.original_filename)[0][:200] or "File"
        return LectureResource.objects.create(lecture=lecture, asset=asset, title=name, position=position)


@authored
def rename(*, resource: LectureResource, title: str) -> LectureResource:
    _editable(resource.lecture.version)
    resource.title = html.plain(title, 200).strip() or resource.title
    resource.save(update_fields=["title", "updated_at"])
    return resource


@authored
def remove(*, resource: LectureResource) -> None:
    """Drops it from this draft only; the file itself goes once nothing uses it."""
    _editable(resource.lecture.version)
    resource.delete()


def download_url(resource: LectureResource) -> str:
    _ensure_storage()
    a = resource.asset
    filename = os.path.basename(a.storage_key)  # slugified, safe in a header
    return storage.download_url(a.storage_key, filename)


def payload(resource: LectureResource) -> dict:
    a = resource.asset
    return {"id": resource.id, "title": resource.title, "position": resource.position, "kind": a.kind,
            "filename": os.path.basename(a.storage_key), "size_bytes": a.size_bytes, "mime_type": a.mime_type}  # fmt: skip


def purge_unused(*, older_than: timedelta = timedelta(days=1)) -> int:
    """Delete stored files that no lecture uses (abandoned uploads, deleted resources)."""
    used = LectureResource.objects.filter(asset_id=OuterRef("pk"))
    stale = (
        # course files only: learners' hand-ins (submissions/...) have their own clean-up
        MediaAsset.objects.filter(
            kind__in=FILE_KINDS,
            storage_key__startswith="courses/",
            created_at__lt=timezone.now() - older_than,
        )
        .exclude(storage_key="")
        .exclude(Exists(used))
    )
    removed = 0
    for asset_id, key in stale.order_by("created_at").values_list("id", "storage_key")[:500]:
        with transaction.atomic(), authoring():
            # lock, then re-check: a new draft may have started using it meanwhile
            locked = MediaAsset.objects.select_for_update().filter(pk=asset_id).first()
            if locked is None or LectureResource.objects.filter(asset_id=asset_id).exists():
                continue
            locked.delete()
            transaction.on_commit(lambda key=key: storage.delete(key) if storage.configured() else None)
            removed += 1
    return removed
