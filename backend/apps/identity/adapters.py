"""allauth adapters: how a Google / Microsoft sign-in fills in our user."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        name = (
            data.get("name") or " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        ).strip()
        if name and not getattr(user, "full_name", ""):
            user.full_name = name[:200]
        return user
