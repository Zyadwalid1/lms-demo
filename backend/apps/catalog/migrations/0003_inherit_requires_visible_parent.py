"""Child rows must have a parent the writer can see. Before this, a parent hidden by RLS
gave owner_org_id NULL (= public). Now the insert is refused (insufficient_privilege)."""

from django.db import migrations

from core import rls


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_security_and_search")]

    operations = [migrations.RunSQL(rls.INHERIT_OWNER_FUNCTION, migrations.RunSQL.noop)]
