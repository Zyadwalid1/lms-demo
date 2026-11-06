from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.api import api

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", api.urls),  # docs at /api/docs, schema at /api/openapi.json
    # Sign-in API for React (login, signup, verify, reset, Google/Microsoft, 2FA):
    # /_allauth/browser/v1/...  documented at /_allauth/openapi.html in DEBUG
    path("_allauth/", include("allauth.headless.urls")),
]
