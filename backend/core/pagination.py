"""Keyset pagination. Never OFFSET: cost stays flat on page 1 and page 1,000.

uuidv7 ids are time-ordered, so ordering by -id gives newest first.
"""

from typing import Any

from ninja import Schema
from ninja.pagination import PaginationBase


class KeysetPagination(PaginationBase):
    class Input(Schema):
        cursor: str | None = None
        limit: int = 20

    class Output(Schema):
        items: list[Any]
        next_cursor: str | None = None

    items_attribute = "items"
    max_limit = 100

    def paginate_queryset(self, queryset, pagination: Input, **params):
        limit = max(1, min(pagination.limit, self.max_limit))
        qs = queryset.order_by("-id")
        if pagination.cursor:
            qs = qs.filter(id__lt=pagination.cursor)
        rows = list(qs[: limit + 1])
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": rows,
            "next_cursor": str(rows[-1].id) if has_more and rows else None,
        }
