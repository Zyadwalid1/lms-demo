"""HARNESS ONLY: the instructor marks the learner's latest submission (M4 builds the real screen)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from django.db import transaction  # noqa: E402

from apps.learning import services  # noqa: E402
from apps.learning.models import Submission  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

email, slug = sys.argv[1], sys.argv[2]
with tenant_context(staff=True), transaction.atomic():
    s = Submission.objects.filter(enrollment__user__email=email, enrollment__course__slug=slug).latest("submitted_at")
    grader = s.enrollment.course.instructor_links.first().user
    services.grade_submission(submission=s, score=85, grader=grader, feedback="Clear design and sensible names. Well done.")
print("graded")
