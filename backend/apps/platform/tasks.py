"""Platform background jobs (Celery)."""

from celery import shared_task

from . import outbox


@shared_task(name="platform.dispatch_outbox")
def dispatch_outbox_task() -> int:
    total = 0
    while n := outbox.dispatch():
        total += n
        if n < 100:
            break
    return total


@shared_task(name="platform.prune_outbox")
def prune_outbox_task() -> int:
    return outbox.prune()
