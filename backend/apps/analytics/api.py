"""HTTP endpoints for analytics. Thin: validate -> call services/selectors -> return."""

from ninja import Router

router = Router(tags=["analytics"])
