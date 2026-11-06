"""`python manage.py migrate` always runs on the `owner` connection.

Our router allows schema changes only on `owner` (lms_owner, direct host). Django's own
migrate defaults to `default` (lms_app): there it skips every operation the router
refuses but STILL records the migration as applied, leaving tables that never existed
marked as done. This override makes the plain command do the right thing.
"""

from django.core.management.commands.migrate import Command as DjangoMigrate
from django.db import DEFAULT_DB_ALIAS


class Command(DjangoMigrate):
    def handle(self, *args, **options):
        if options.get("database") in (None, DEFAULT_DB_ALIAS):
            options["database"] = "owner"
            self.stdout.write(self.style.NOTICE("Running migrations on the 'owner' connection (lms_owner)."))
        if options["database"] != "owner":
            self.stderr.write(self.style.ERROR("Migrations only run on 'owner'. Nothing done."))
            return
        return super().handle(*args, **options)
