"""Webhook signature checks. Always verify against the RAW body bytes, before parsing."""

import hashlib
import hmac


def hmac_sha256_hex(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def signature_matches(secret: str, raw_body: bytes, received_hex: str) -> bool:
    if not secret or not received_hex:
        return False
    return hmac.compare_digest(hmac_sha256_hex(secret, raw_body), received_hex.strip().lower())


def bunny_signature_valid(request, readonly_api_key: str) -> bool:
    """Bunny Stream: HMAC-SHA256 of the raw body, keyed with the library's Read-Only API key.
    https://bunny.net/docs/stream/webhooks.md
    """
    if request.headers.get("X-BunnyStream-Signature-Version") != "v1":
        return False
    if request.headers.get("X-BunnyStream-Signature-Algorithm") != "hmac-sha256":
        return False
    return signature_matches(
        readonly_api_key, request.body, request.headers.get("X-BunnyStream-Signature", "")
    )
