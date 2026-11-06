"""orjson renderer: several times faster than the stdlib json encoder on large lists,
and serializes UUID / datetime natively."""

from decimal import Decimal

import orjson
from ninja.renderers import BaseRenderer


def _default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Type is not JSON serializable: {type(obj).__name__}")


class ORJSONRenderer(BaseRenderer):
    media_type = "application/json"

    def render(self, request, data, *, response_status):
        return orjson.dumps(data, default=_default, option=orjson.OPT_NON_STR_KEYS)
