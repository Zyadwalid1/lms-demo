from django.apps import AppConfig


class PayoutsConfig(AppConfig):
    name = "apps.payouts"
    label = "payouts"
    verbose_name = "Payouts"

    def ready(self) -> None:
        from apps.commerce.signals import ITEM_REFUNDED, ORDER_PAID
        from apps.platform import outbox

        from . import services

        outbox.subscribe(ORDER_PAID)(lambda p: services.record_sale(p["order_id"]))
        outbox.subscribe(ITEM_REFUNDED)(lambda p: services.record_refund(p["item_id"]))
