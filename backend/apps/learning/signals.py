"""Signals other apps listen to (compliance), so learning never imports them.

course_completed(enrollment_id, org_id, user_id, course_id)
    Sent AFTER COMMIT when an enrolment is completed and its certificate issued.
    Only company enrolments (org_id set) are announced: personal learning is never
    visible to, or counted by, a company (decision 2).
"""

from django.db import transaction
from django.dispatch import Signal

course_completed = Signal()


def notify_course_completed(enrollment) -> None:
    if enrollment.org_id is None:
        return
    payload = {
        "enrollment_id": enrollment.id,
        "org_id": enrollment.org_id,
        "user_id": enrollment.user_id,
        "course_id": enrollment.course_id,
    }
    transaction.on_commit(lambda: course_completed.send(sender=None, **payload))
