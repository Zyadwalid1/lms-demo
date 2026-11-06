"""HTTP endpoints for payouts. Thin: validate -> call services/selectors -> return."""

from ninja import Router

router = Router(tags=["payouts"])
