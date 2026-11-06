"""Payouts RLS: revenue shares are reference data; accounts, payouts and earnings are
readable by their instructor and writable only by staff and platform jobs.
Default shares (admin-editable): 37% marketplace, 97% instructor coupon, 25% plan pool."""

from django.db import migrations

from core import rls

S = "payouts"


def rates(apps, schema_editor):
    RevenueShare = apps.get_model("payouts", "RevenueShare")
    db = schema_editor.connection.alias
    for channel, bps in (("marketplace", 3700), ("instructor_coupon", 9700), ("subscription_pool", 2500)):
        RevenueShare.objects.using(db).get_or_create(channel=channel, defaults={"instructor_bps": bps})


class Migration(migrations.Migration):
    dependencies = [("payouts", "0001_initial")]

    operations = [
        *(
            migrations.RunSQL(fwd, rev)
            for fwd, rev in (
                rls.reference(S, "revenue_shares"),
                *(rls.personal_readonly(S, t) for t in ("payout_accounts", "payouts", "earnings")),
            )
        ),
        migrations.RunPython(rates, migrations.RunPython.noop),
    ]
