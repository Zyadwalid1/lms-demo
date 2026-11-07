"""Console > Audit log: every staff and company action, newest first (keyset)."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import connection
from ninja import Schema

from core import cursor as keyset

from .common import clamp, router, staff


class ConsoleAuditRowOut(Schema):
    id: int
    created_at: datetime
    actor_id: UUID | None
    actor_email: str | None
    org_id: UUID | None
    action: str
    target_type: str
    target_id: str
    ip: str | None
    request_id: str
    data: dict[str, Any]


class ConsoleAuditPageOut(Schema):
    items: list[ConsoleAuditRowOut]
    next_cursor: str | None


@router.get("/audit", response=ConsoleAuditPageOut)
def audit(request, org_id: str | None = None, actor_id: str | None = None, action: str | None = None,
          cursor: str | None = None, limit: int = 100):  # fmt: skip
    staff(request)
    limit = clamp(limit, 500)
    sql = ["SELECT a.id, a.created_at, a.actor_id, u.email, a.org_id, a.action, a.target_type, a.target_id, a.ip,",
           "a.request_id, a.data FROM platform.audit_logs a LEFT JOIN identity.users u ON u.id = a.actor_id WHERE true"]  # fmt: skip
    params: list = []
    for column, value in (("a.org_id", org_id), ("a.actor_id", actor_id)):
        if value:
            sql.append(f"AND {column} = %s")
            params.append(value)
    if action:
        sql.append("AND a.action LIKE %s")
        params.append(action.replace("%", "") + "%")
    after = keyset.decode(cursor, 2)
    if after:
        sql.append("AND (a.created_at, a.id) < (%s::timestamptz, %s::bigint)")
        params += after
    sql.append("ORDER BY a.created_at DESC, a.id DESC LIMIT %s")
    params.append(limit + 1)
    with connection.cursor() as cur:
        cur.execute(" ".join(sql), params)
        rows = cur.fetchall()
    page = rows[:limit]
    items = [{"id": r[0], "created_at": r[1], "actor_id": r[2], "actor_email": r[3], "org_id": r[4], "action": r[5],
              "target_type": r[6], "target_id": r[7], "ip": str(r[8]) if r[8] else None, "request_id": r[9],
              "data": r[10] if isinstance(r[10], dict) else json.loads(r[10] or "{}")} for r in page]  # fmt: skip
    return {
        "items": items,
        "next_cursor": keyset.encode(page[-1][1].isoformat(), page[-1][0]) if len(rows) > limit else None,
    }
