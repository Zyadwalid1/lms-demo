"""Transactional outbox.

    outbox.publish("order.paid", {"order_id": str(order.id)})   # inside the business transaction
    @outbox.subscribe("order.paid")                              # in an app's ready()
    def on_paid(payload): ...

The event row commits or rolls back WITH the change it describes, so "the order is
paid but the instructor was never credited" cannot happen. After commit a dispatch
is requested at once (fast path); a beat job every 30 s catches anything left behind
(worker crash, Redis down). Handlers must be idempotent: an event can run twice.
Failures retry with exponential backoff (1 min, 2, 4 ... capped at 1 h).
"""

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from core.tenancy import tenant_context

log = logging.getLogger(__name__)
_handlers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)


def subscribe(topic: str):
    def register(fn):
        if fn not in _handlers[topic]:
            _handlers[topic].append(fn)
        return fn

    return register


def publish(topic: str, payload: dict) -> None:
    """Plain INSERT (no RETURNING): any request may write an event, only jobs read them."""
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO platform.outbox_events (id, created_at, updated_at, topic, payload, available_at,"
            " attempts, last_error) VALUES (uuidv7(), now(), now(), %s, %s::jsonb, now(), 0, '')",
            [topic, json.dumps(payload, cls=DjangoJSONEncoder)],
        )

    def kick():
        from .tasks import dispatch_outbox_task

        dispatch_outbox_task.delay()

    transaction.on_commit(kick)


def dispatch(limit: int = 100) -> int:
    """Run due events. SKIP LOCKED lets several workers share the queue safely."""
    done = 0
    with tenant_context(staff=True), connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, topic, payload, attempts FROM platform.outbox_events
             WHERE processed_at IS NULL AND available_at <= now()
             ORDER BY available_at LIMIT %s FOR UPDATE SKIP LOCKED
            """,
            [limit],
        )
        for event_id, topic, payload, attempts in cur.fetchall():
            data = payload if isinstance(payload, dict) else json.loads(payload)
            try:
                with transaction.atomic():  # one event's failure never undoes another's work
                    for handler in _handlers.get(topic, []):
                        handler(data)
                cur.execute(
                    "UPDATE platform.outbox_events SET processed_at = now(), updated_at = now(), last_error = ''"
                    " WHERE id = %s",
                    [event_id],
                )
                done += 1
            except Exception as exc:  # noqa: BLE001 - recorded and retried, never lost
                log.exception("outbox %s (%s) failed", event_id, topic)
                delay = min(timedelta(minutes=2**attempts), timedelta(hours=1))
                cur.execute(
                    "UPDATE platform.outbox_events SET attempts = attempts + 1, available_at = %s,"
                    " last_error = %s, updated_at = now() WHERE id = %s",
                    [timezone.now() + delay, str(exc)[:2000], event_id],
                )
    return done


def prune(days: int = 7) -> int:
    with tenant_context(staff=True), connection.cursor() as cur:
        cur.execute(
            "DELETE FROM platform.outbox_events WHERE processed_at < now() - make_interval(days => %s)",
            [days],
        )
        return cur.rowcount
