"""Tell learners when an instructor has marked their assignment or quiz (adds one row)."""

from django.db import migrations

SQL = """
INSERT INTO engagement.notification_templates (id, created_at, updated_at, code, title, body, email_enabled, is_active)
VALUES (uuidv7(), now(), now(), 'work_marked', 'Your work has been marked',
        '"{title}" in {course} has a score and feedback.', true, true)
ON CONFLICT (code) DO NOTHING;
"""


class Migration(migrations.Migration):
    dependencies = [("engagement", "0004_course_assigned_template")]

    operations = [migrations.RunSQL(SQL, "DELETE FROM engagement.notification_templates WHERE code = 'work_marked';")]
