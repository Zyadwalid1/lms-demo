"""Money events, published through the transactional outbox (apps.platform.outbox):
the event commits together with the payment or refund, so a crash between commit and
enqueue can never lose an instructor's earnings. Subscribers: payouts."""

from apps.platform import outbox

ORDER_PAID = "order.paid"  # {"order_id"}
ITEM_REFUNDED = "order.item_refunded"  # {"item_id"}


def notify_order_paid(order_id) -> None:
    outbox.publish(ORDER_PAID, {"order_id": str(order_id)})


def notify_item_refunded(item_id) -> None:
    outbox.publish(ITEM_REFUNDED, {"item_id": str(item_id)})
