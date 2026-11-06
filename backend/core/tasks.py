"""Platform maintenance jobs (Celery)."""

from celery import shared_task
from django.db import connection


@shared_task(name="core.secure_partitions")
def secure_partitions() -> int:
    """Daily, after pg_partman creates new partitions: keep them unreachable directly."""
    with connection.cursor() as cur:
        cur.execute("SELECT platform.secure_partitions()")
        return cur.fetchone()[0]
