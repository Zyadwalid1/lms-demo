"""Every ISO currency (ECB ones active, the rest waiting for an admin rate) and the
GBP price tiers. Idempotent: re-running never duplicates or overwrites admin edits."""

from django.db import migrations


def load(apps, schema_editor):
    from apps.commerce.currencies import ECB, ISO_4217, STRIPE_UNSUPPORTED, THREE_DECIMAL, TIERS_GBP, ZERO_DECIMAL

    Currency = apps.get_model("commerce", "Currency")
    PriceTier = apps.get_model("commerce", "PriceTier")
    db = schema_editor.connection.alias  # the owner connection running the migration
    have = set(Currency.objects.using(db).values_list("code", flat=True))
    Currency.objects.using(db).bulk_create(
        [
            Currency(
                code=code,
                name=name,
                exponent=0 if code in ZERO_DECIMAL else 3 if code in THREE_DECIMAL else 2,
                stripe_supported=code not in STRIPE_UNSUPPORTED,
                rate_source="ecb" if code in ECB else "manual",
                is_active=code == "GBP" or (code in ECB and code not in STRIPE_UNSUPPORTED),
            )
            for code, name in ISO_4217.items()
            if code not in have
        ]
    )
    for i, pence in enumerate(TIERS_GBP, start=1):
        PriceTier.objects.using(db).get_or_create(name=f"Tier {i}", defaults={"gbp_minor": pence, "sort_order": i})


class Migration(migrations.Migration):
    dependencies = [("commerce", "0002_security")]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
