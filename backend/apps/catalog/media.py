"""Bunny Stream status -> MediaAsset (via the platform outbox, after the webhook was verified).

Bunny status codes: 0 queued, 1 processing, 2 encoding, 3 finished, 4 resolution finished
(first quality playable), 5 failed, 6 upload started, 7 upload finished, 8 upload failed,
9 captions generated, 10 title/description generated.
https://docs.bunny.net/docs/stream-webhook
"""

import hashlib
import os
import time

from django.utils import timezone

from core.tenancy import tenant_context

from .models import MediaAsset

S = MediaAsset.Status
STATUS = {0: S.PROCESSING, 1: S.PROCESSING, 2: S.PROCESSING, 3: S.READY, 4: S.PLAYABLE, 5: S.FAILED,
          6: S.AWAITING_UPLOAD, 7: S.PROCESSING, 8: S.FAILED}  # fmt: skip
RANK = {S.AWAITING_UPLOAD: 0, S.PROCESSING: 1, S.PLAYABLE: 2, S.READY: 3, S.FAILED: 3}


def apply_bunny_status(payload: dict) -> None:
    """Idempotent and order-safe: webhooks can arrive late or twice, so status only moves
    forward (a late 'encoding' never downgrades a ready video). 9/10 are informational."""
    new = STATUS.get(int(payload["status"]))
    with tenant_context(staff=True):
        asset = MediaAsset.objects.select_for_update().filter(bunny_video_guid=payload["video_guid"]).first()
        if asset is None:
            return  # not ours (another environment sharing the library)
        fields = {"bunny_status": int(payload["status"]), "updated_at": timezone.now()}
        if new and (RANK[new] > RANK[asset.status] or new == S.FAILED and asset.status != S.READY):
            fields["status"] = new
            if new == S.READY:
                fields["encode_progress"] = 100
        MediaAsset.objects.filter(pk=asset.pk).update(**fields)
    from apps.platform.services import mark_webhook_processed

    mark_webhook_processed(payload.get("provider", "bunny"), payload.get("dedupe_key", ""))


# ---------------------------------------------------------------- playback
PLAYBACK_TTL_SEC = 2 * 60 * 60


def playback(asset: MediaAsset | None) -> dict | None:
    """A signed Bunny embed URL, valid for 2 hours. The token key stays on the server:
    token = SHA256_hex(token_key + video_guid + expires). https://docs.bunny.net/docs/stream-embed-token-authentication
    Demo assets without a real Bunny video return a placeholder so the player can say so."""
    if asset is None:
        return None
    if not asset.bunny_video_guid or asset.library is None:
        return {"kind": "placeholder", "url": None, "expires_at": None, "duration_sec": asset.duration_sec}
    expires = int(time.time()) + PLAYBACK_TTL_SEC
    key = os.getenv(asset.library.token_key_env, "")
    guid = str(asset.bunny_video_guid)
    url = f"https://iframe.mediadelivery.net/embed/{asset.library.bunny_library_id}/{guid}"
    if key:
        token = hashlib.sha256(f"{key}{guid}{expires}".encode()).hexdigest()
        url += f"?token={token}&expires={expires}"
    return {"kind": "bunny", "url": url, "expires_at": expires, "duration_sec": asset.duration_sec}
