"""Test runner for Neon.

1. Tests connect the app alias (lms_app) to the DIRECT host instead of the pooler.
   PgBouncer keeps its own server connections to the test database open after the
   tests finish, which blocks DROP DATABASE. Same role, same RLS, just no pooler.
2. Before creating and before dropping the test database, any leftover sessions on
   it are closed, so a run interrupted earlier never blocks the next one.
3. Tests never depend on local services being up: Redis is replaced by an in-memory
   cache, sessions use the database and Celery tasks run inline, whatever .env says.
   (Tests that need Redis behaviour use fakeredis explicitly.)
"""

import logging

from django.db import connections
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

logger = logging.getLogger(__name__)
MIGRATION_ALIAS = "owner"


def _direct_host(host: str | None) -> str | None:
    return host.replace("-pooler.", ".") if host else host


def _close_other_sessions(dbname: str) -> None:
    try:
        with connections[MIGRATION_ALIAS]._nodb_cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                [dbname],
            )
    except Exception as exc:  # noqa: BLE001 - best effort; Django reports a real failure itself
        logger.warning("Could not close sessions on %s: %s", dbname, exc)


ISOLATED_SETTINGS = {
    "REDIS_URL": "",
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    "SESSION_ENGINE": "django.contrib.sessions.backends.db",
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_BROKER_URL": "memory://",
}


class NeonTestRunner(DiscoverRunner):
    # expected noise in tests (refused requests, eager task results, dev timing warnings);
    # query counts are asserted by core/tests/test_query_budgets.py instead
    QUIET = {"django.request": logging.ERROR, "lms.perf": logging.ERROR, "celery.app.trace": logging.WARNING,
             "kombu.connection": logging.ERROR, "core.mail": logging.ERROR}  # fmt: skip

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        for name, level in self.QUIET.items():
            logging.getLogger(name).setLevel(level)
        self._isolation = override_settings(**ISOLATED_SETTINGS)
        self._isolation.enable()

    def teardown_test_environment(self, **kwargs):
        self._isolation.disable()
        super().teardown_test_environment(**kwargs)

    def setup_databases(self, **kwargs):
        for alias in ("default", "replica"):
            if alias in connections.settings:
                settings_dict = connections[alias].settings_dict
                settings_dict["HOST"] = _direct_host(settings_dict.get("HOST"))
        _close_other_sessions(connections[MIGRATION_ALIAS].creation._get_test_db_name())
        return super().setup_databases(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        test_name = connections[MIGRATION_ALIAS].settings_dict["NAME"]
        for conn in connections.all():
            conn.close()
        _close_other_sessions(test_name)
        return super().teardown_databases(old_config, **kwargs)
