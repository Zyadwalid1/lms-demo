"""Bunny Stream: create a video and hand the browser a short-lived TUS upload signature.

The browser uploads straight to Bunny (resumable TUS); the file never passes through
our servers and the library API key never reaches the browser. Only the signature
for ONE video, valid for 2 hours, does:
    AuthorizationSignature = SHA256(library_id + api_key + expiration_time + video_id)
https://docs.bunny.net/reference/tus-resumable-uploads
"""

import hashlib
import os
import time

import httpx

from core.errors import ServiceError

API = "https://video.bunnycdn.com"
TUS_ENDPOINT = f"{API}/tusupload"
UPLOAD_TTL_SEC = 2 * 60 * 60


def _key(library) -> str:
    key = os.getenv(library.api_key_env, "")
    if not key:
        raise ServiceError("video_unavailable", "Video uploads are not configured.", status=503)
    return key


def create_video(library, title: str) -> str:
    """Returns the new video's guid."""
    with httpx.Client(timeout=15) as client:
        r = client.post(
            f"{API}/library/{library.bunny_library_id}/videos",
            headers={"AccessKey": _key(library), "accept": "application/json"},
            json={"title": title[:200]},
        )
    if r.status_code >= 400:
        raise ServiceError("video_unavailable", "The video service did not accept the upload.", status=502)
    return r.json()["guid"]


def upload_session(library, guid: str) -> dict:
    expires = int(time.time()) + UPLOAD_TTL_SEC
    signature = hashlib.sha256(
        f"{library.bunny_library_id}{_key(library)}{expires}{guid}".encode()
    ).hexdigest()
    return {
        "endpoint": TUS_ENDPOINT,
        "headers": {
            "AuthorizationSignature": signature,
            "AuthorizationExpire": str(expires),
            "VideoId": guid,
            "LibraryId": str(library.bunny_library_id),
        },
        "expires_at": expires,
    }


def delete_video(library, guid: str) -> None:
    with httpx.Client(timeout=15) as client:
        client.delete(
            f"{API}/library/{library.bunny_library_id}/videos/{guid}", headers={"AccessKey": _key(library)}
        )
