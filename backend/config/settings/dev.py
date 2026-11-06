from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = True

# Warn on N+1 queries and slow requests while developing (adds X-DB-Queries header).
MIDDLEWARE = [*MIDDLEWARE[:-1], "core.middleware.QueryBudgetMiddleware", MIDDLEWARE[-1]]

# Dev can run without built static files.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
