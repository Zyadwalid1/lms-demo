"""Catalog background jobs (Celery)."""

from celery import shared_task

from core.tenancy import tenant_context

from . import resources


@shared_task(name="catalog.purge_unused_files")
def purge_unused_files_task() -> int:
    with tenant_context(staff=True):
        return resources.purge_unused()
