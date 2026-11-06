"""Notification wording for courses assigned by a company (plain SQL, idempotent)."""

from django.db import migrations

SQL = """
INSERT INTO engagement.notification_templates (id, created_at, updated_at, code, title, body, email_enabled, is_active)
VALUES (uuidv7(), now(), now(), 'course_assigned', 'New training: {course}',
        '{company} has assigned you this course.', true, true)
ON CONFLICT (code) DO NOTHING;
"""


class Migration(migrations.Migration):
    dependencies = [("engagement", "0003_templates_and_badges")]

    operations = [migrations.RunSQL(SQL, "DELETE FROM engagement.notification_templates WHERE code = 'course_assigned';")]
