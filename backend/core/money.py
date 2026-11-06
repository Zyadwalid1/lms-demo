"""Which currency to show prices in, for this request."""

from apps.commerce.models import Currency

BASE = "GBP"


def request_currency(request, wanted: str | None = None) -> dict:
    """?currency=  ->  the user's preference  ->  GBP. Only active currencies are used."""
    user = getattr(request, "user", None)
    candidates = [
        wanted,
        getattr(user, "preferred_currency", None) if user and user.is_authenticated else None,
        BASE,
    ]
    for code in candidates:
        if not code:
            continue
        row = (
            Currency.objects.filter(code=code.upper()[:3], is_active=True).values("code", "exponent").first()
        )
        if row:
            return row
    return {"code": BASE, "exponent": 2}
