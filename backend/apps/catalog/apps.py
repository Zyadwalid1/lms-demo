from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    label = "catalog"
    verbose_name = "Catalog"

    def ready(self) -> None:
        from apps.platform import outbox

        from .media import apply_bunny_status

        outbox.subscribe("bunny.video")(apply_bunny_status)
