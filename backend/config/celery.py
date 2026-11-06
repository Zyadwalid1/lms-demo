"""Celery app: background jobs (progress flush, reminders, webhook processing, emails).

Run a worker:  celery -A config worker -l info
Run the scheduler:  celery -A config beat -l info
Workers scale separately from the web servers.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("lms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # finds apps/<domain>/tasks.py
