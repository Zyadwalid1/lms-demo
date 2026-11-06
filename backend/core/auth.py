"""API authentication. Session cookies for the React app (same site, CSRF on)."""

from ninja.security import django_auth

session_auth = django_auth
