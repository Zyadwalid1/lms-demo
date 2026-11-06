"""HTTP endpoints for platform. Thin: validate -> call services/selectors -> return."""

import json

from django.conf import settings
from ninja import Router

from core.errors import ServiceError
from core.webhooks import bunny_signature_valid

from . import services

router = Router(tags=["platform"])


@router.get("/settings", auth=None)
def public_settings(request):
    """Settings marked public (feature flags the React app needs)."""
    return services.public_settings()


@router.post("/webhooks/bunny", auth=None, throttle=[], include_in_schema=False)
def bunny_webhook(request):
    """Bunny Stream video status. Signed with the library's Read-Only API key."""
    if not bunny_signature_valid(request, settings.BUNNY_STREAM["READONLY_KEY"]):
        raise ServiceError("bad_signature", "Invalid webhook signature.", status=401)
    try:
        body = json.loads(request.body)
        guid, status = str(body["VideoGuid"]), int(body["Status"])
        library = int(body["VideoLibraryId"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ServiceError("bad_payload", "Unexpected webhook body.") from exc
    new = services.receive_webhook(
        provider="bunny", dedupe_key=f"{guid}:{status}", topic="bunny.video",
        payload={"video_guid": guid, "status": status, "library_id": library},
    )  # fmt: skip
    return {"received": True, "duplicate": not new}
