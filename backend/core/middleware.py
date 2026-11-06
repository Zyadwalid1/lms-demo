"""Request ID and (dev only) query-budget middleware."""

import logging
import time
import uuid
from contextvars import ContextVar

from django.conf import settings
from django.db import connections

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("lms.perf")


class RequestIDMiddleware:
    """Accepts X-Request-ID from the load balancer or creates one; echoes it back and
    puts it on every log line, so one request can be traced across app and workers."""

    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = (request.META.get(self.header) or uuid.uuid4().hex)[:64]
        token = request_id_var.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = rid
        return response


class QueryBudgetMiddleware:
    """DEV ONLY. Warns when a request runs too many queries (usually an N+1) or is slow.
    Thresholds: settings.QUERY_BUDGET (count) and settings.SLOW_REQUEST_MS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        counter = {"n": 0}

        def count(execute, sql, params, many, context):
            counter["n"] += 1
            return execute(sql, params, many, context)

        started = time.perf_counter()
        with connections["default"].execute_wrapper(count):
            response = self.get_response(request)
        ms = (time.perf_counter() - started) * 1000

        response["X-DB-Queries"] = str(counter["n"])
        reasons = [r for r, hit in (("queries", counter["n"] > settings.QUERY_BUDGET),
                                    ("slow", ms > settings.SLOW_REQUEST_MS)) if hit]  # fmt: skip
        if reasons:
            logger.warning(
                "%s: %s %s queries=%s time=%.0fms",
                "+".join(reasons),
                request.method,
                request.path,
                counter["n"],
                ms,
            )
        return response
