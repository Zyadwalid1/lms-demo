"""Console > Settings (mockup 18): typed platform settings from apps.platform.registry."""

from datetime import datetime
from typing import Any

from ninja import Field, Schema

from core.errors import ServiceError

from .. import services
from ..models import Setting
from ..services import audit_request
from .common import ConsoleOkOut, router, staff


class ConsoleSettingIn(Schema):
    value: dict | list | str | int | float | bool
    description: str = Field("", max_length=300)
    is_public: bool | None = None


class ConsoleSettingRowOut(Schema):
    key: str
    value: Any
    description: str
    is_public: bool
    updated_at: datetime


@router.get("/settings", response=list[ConsoleSettingRowOut])
def settings_list(request):
    staff(request)
    return list(
        Setting.objects.order_by("key").values("key", "value", "description", "is_public", "updated_at")
    )


@router.put("/settings/{key}", response=ConsoleOkOut)
def set_setting(request, key: str, body: ConsoleSettingIn):
    staff(request)
    if not key.replace(".", "").replace("_", "").isalnum() or len(key) > 100:
        raise ServiceError("bad_key", "Keys use letters, digits, dots and underscores.")
    services.set_setting(key=key, value=body.value, by=request.user, description=body.description,
                         is_public=body.is_public)  # fmt: skip
    audit_request(request, "setting.update", "setting", key, {"value": body.value})
    return {"ok": True}
