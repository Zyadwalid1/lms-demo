"""HARNESS ONLY: a brand-new verified learner for one E2E run."""
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from allauth.account.models import EmailAddress  # noqa: E402

from apps.identity.models import User  # noqa: E402

email = f"e2e.buyer.{int(time.time())}@learnhub.example.com"
u = User.objects.create_user(email, sys.argv[1], full_name="Eve Buyer")
EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
print(email)
