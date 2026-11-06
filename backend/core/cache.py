"""Cache helpers with namespace versioning.

Instead of hunting down every key when a course changes, bump the namespace:
    get_or_set(("course", slug), build, timeout=300)
    bump("course", slug)   # every cached entry for that course is now stale
"""

from collections.abc import Callable, Hashable
from typing import Any

from django.core.cache import cache


def _version_key(namespace: str, scope: Hashable) -> str:
    return f"v:{namespace}:{scope}"


def _version(namespace: str, scope: Hashable) -> int:
    return cache.get_or_set(_version_key(namespace, scope), 1, timeout=None)


def key(namespace: str, scope: Hashable, *parts: Hashable) -> str:
    suffix = ":".join(str(p) for p in parts)
    return f"{namespace}:{scope}:v{_version(namespace, scope)}:{suffix}"


def get_or_set(
    namespace: str, scope: Hashable, build: Callable[[], Any], *parts: Hashable, timeout: int = 300
):
    return cache.get_or_set(key(namespace, scope, *parts), build, timeout=timeout)


def bump(namespace: str, scope: Hashable) -> None:
    vk = _version_key(namespace, scope)
    try:
        cache.incr(vk)
    except ValueError:
        cache.set(vk, 2, timeout=None)
