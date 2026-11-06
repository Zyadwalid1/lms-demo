"""Commerce RLS:
    reference   currencies, rates, tiers, promotions, plans, add-ons: read by all, staff write
    personal    cart and wishlist: only their owner
    mixed       orders and everything hanging off them, subscriptions, invoices
    staff_only  raw Stripe events
Child rows copy org_id + user_id from their parent by trigger, so an order item can
never belong to a different person or company than its order."""

from django.db import migrations

from core import rls

S = "commerce"
REFERENCE = (
    "currencies", "fx_rates", "price_tiers", "price_tier_amounts", "promotions",
    "plans", "plan_prices", "addons", "addon_prices",
)  # fmt: skip
PERSONAL = ("cart_items", "wishlist_items")
MIXED = (
    "orders", "order_items", "payments", "refunds", "coupon_redemptions",
    "subscriptions", "addon_subscriptions", "invoices",
)  # fmt: skip
INHERIT = [
    ("order_items", "commerce.orders", "order_id"),
    ("payments", "commerce.orders", "order_id"),
    ("coupon_redemptions", "commerce.orders", "order_id"),
    ("refunds", "commerce.order_items", "item_id"),
]


class Migration(migrations.Migration):
    dependencies = [("commerce", "0001_initial"), ("learning", "0003_renewals_and_org_keys")]

    operations = [
        migrations.RunSQL(fwd, rev)
        for fwd, rev in (
            *(rls.reference(S, t) for t in REFERENCE),
            *(rls.personal(S, t) for t in PERSONAL),
            *(rls.mixed(S, t) for t in MIXED),
            rls.staff_only(S, "stripe_events"),
            *(rls.inherit_parent(S, t, parent, fk) for t, parent, fk in INHERIT),
            rls.composite_fk(
                S, "invoices", ("org_id", "subscription_id"), S, "subscriptions", ("org_id", "id"), "fk_inv_sub_same_org"
            ),
        )
    ]
