"""Catalog: Row-Level Security, owner inheritance triggers, search indexes."""

from django.db import migrations

from core import rls

S = "catalog"

# Every table that can hold company-private content
SCOPED = [
    "courses", "course_versions", "sections", "lectures", "lecture_resources", "media_assets",
    "quizzes", "quiz_questions", "quiz_options", "assignments", "certificate_templates",
    "learning_paths", "learning_path_items",
]

# child table -> (parent table, FK column): owner_org_id is copied from the parent
INHERIT = [
    ("course_versions", "catalog.courses", "course_id"),
    ("sections", "catalog.course_versions", "version_id"),
    ("lectures", "catalog.course_versions", "version_id"),
    ("lecture_resources", "catalog.lectures", "lecture_id"),
    ("quizzes", "catalog.lectures", "lecture_id"),
    ("quiz_questions", "catalog.quizzes", "quiz_id"),
    ("quiz_options", "catalog.quiz_questions", "question_id"),
    ("assignments", "catalog.lectures", "lecture_id"),
    ("learning_path_items", "catalog.learning_paths", "path_id"),
]

SEARCH_FORWARD = """
ALTER TABLE catalog.courses ADD COLUMN search tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(subtitle, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'C')
) STORED;
CREATE INDEX gx_courses_search ON catalog.courses USING gin (search);
CREATE INDEX gx_courses_title_trgm ON catalog.courses USING gin (title gin_trgm_ops);
"""
SEARCH_REVERSE = """
DROP INDEX IF EXISTS catalog.gx_courses_title_trgm;
DROP INDEX IF EXISTS catalog.gx_courses_search;
ALTER TABLE catalog.courses DROP COLUMN IF EXISTS search;
"""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial"), ("org", "0002_security")]

    operations = [
        migrations.RunSQL(rls.INHERIT_OWNER_FUNCTION, "DROP FUNCTION IF EXISTS catalog.inherit_owner_org();"),
        *(migrations.RunSQL(*rls.inherit_owner(S, child, parent, fk)) for child, parent, fk in INHERIT),
        *(migrations.RunSQL(*rls.scoped_content(S, t)) for t in SCOPED),
        migrations.RunSQL(SEARCH_FORWARD, SEARCH_REVERSE),
    ]
