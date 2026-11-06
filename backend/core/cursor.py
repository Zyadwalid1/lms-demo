"""Opaque cursors for keyset pagination on any sort ("seek method").

A cursor is the sort value(s) of the last row plus its id, base64-encoded JSON. The next
page is WHERE (sort, id) < (last_sort, last_id): constant cost on page 1 or page 1,000,
and stable while new rows arrive (no duplicates or gaps like OFFSET).
"""

import base64
import json

from core.errors import ServiceError


def encode(*values) -> str:
    raw = json.dumps([str(v) if v is not None else None for v in values], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode(cursor: str | None, size: int) -> list | None:
    if not cursor:
        return None
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError) as exc:
        raise ServiceError("bad_cursor", "Invalid page cursor.") from exc
    if not isinstance(values, list) or len(values) != size or len(cursor) > 512:
        raise ServiceError("bad_cursor", "Invalid page cursor.")
    return values
