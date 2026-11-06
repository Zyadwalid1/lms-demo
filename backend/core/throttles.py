"""API rate limits. Counters live in the cache (Redis in production, so limits are
shared across all app servers). Behind a load balancer set NINJA_NUM_PROXIES so the
real client IP is used, not the proxy's.
"""

from ninja.throttling import AnonRateThrottle, AuthRateThrottle

# Applied to every endpoint unless an endpoint overrides `throttle=`.
DEFAULT_THROTTLES = [
    AnonRateThrottle("120/m"),
    AuthRateThrottle("1200/m"),
]

# Brute-force protection for credential endpoints.
LOGIN_THROTTLES = [AnonRateThrottle("10/m")]
