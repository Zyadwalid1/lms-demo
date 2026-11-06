"""Course content becomes write-protected at the database level: rows are written only
while a catalog authoring service runs (app.author) or by platform staff. Reads are
unchanged. Plain SQL policies (see core.rls.scoped_content_authored)."""

from django.db import migrations

from core import rls

SCOPED = [
    "courses", "course_versions", "sections", "lectures", "lecture_resources", "media_assets",
    "quizzes", "quiz_questions", "quiz_options", "assignments", "certificate_templates",
    "learning_paths", "learning_path_items",
]  # fmt: skip


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_inherit_requires_visible_parent")]

    operations = [migrations.RunSQL(*rls.scoped_content_authored("catalog", t)) for t in SCOPED]
