"""Engagement RLS, owner inheritance and counter triggers (see models.py for the map)."""

from django.db import migrations

from core import rls
from core.rls import ORG, STAFF, USER

S = "engagement"


def policies(table: str, *rules: tuple[str, str, str]) -> tuple[str, str]:
    """rules: (name, command, 'USING (...)' and/or 'WITH CHECK (...)')."""
    q = f'"{S}"."{table}"'
    rls._ident(table)
    fwd = f"ALTER TABLE {q} ENABLE ROW LEVEL SECURITY;\nALTER TABLE {q} FORCE ROW LEVEL SECURITY;\n"
    rev = ""
    for name, cmd, clause in rules:
        fwd += f"CREATE POLICY {name} ON {q} FOR {cmd} {clause};\n"
        rev += f"DROP POLICY IF EXISTS {name} ON {q};\n"
    return fwd, rev + f"ALTER TABLE {q} NO FORCE ROW LEVEL SECURITY;\nALTER TABLE {q} DISABLE ROW LEVEL SECURITY;"


VISIBLE = f"(owner_org_id IS NULL OR owner_org_id = {ORG} OR {STAFF})"
AUTHOR = f"((user_id = {USER} AND (owner_org_id IS NULL OR owner_org_id = {ORG})) OR {STAFF})"


def scoped_own_write(table: str):
    return policies(
        table,
        ("scoped_read", "SELECT", f"USING {VISIBLE}"),
        ("author_insert", "INSERT", f"WITH CHECK {AUTHOR}"),
        ("author_update", "UPDATE", f"USING {AUTHOR} WITH CHECK {AUTHOR}"),
        ("author_delete", "DELETE", f"USING {AUTHOR}"),
    )


OWN = f"(user_id = {USER} OR {STAFF})"
POLICIES = [
    policies(
        "reviews",
        ("public_read", "SELECT", "USING (true)"),
        ("author_insert", "INSERT", f"WITH CHECK {OWN}"),
        ("author_update", "UPDATE", f"USING {OWN} WITH CHECK {OWN}"),
        ("author_delete", "DELETE", f"USING {OWN}"),
    ),
    *(scoped_own_write(t) for t in ("questions", "answers", "question_votes", "announcements")),
    policies(
        "notifications",
        ("inbox_read", "SELECT", f"USING {OWN}"),
        ("inbox_update", "UPDATE", f"USING {OWN} WITH CHECK {OWN}"),
        ("inbox_delete", "DELETE", f"USING {OWN}"),
        ("jobs_insert", "INSERT", f"WITH CHECK ({STAFF})"),
    ),
    rls.personal(S, "notification_preferences"),
    rls.reference(S, "notification_templates"),
    rls.reference(S, "badges"),
    rls.personal_readonly(S, "user_badges"),
    policies(
        "tickets",
        ("requester_read", "SELECT", f"USING {OWN}"),
        ("requester_insert", "INSERT", f"WITH CHECK {OWN}"),
        ("staff_update", "UPDATE", f"USING ({STAFF}) WITH CHECK ({STAFF})"),
        ("staff_delete", "DELETE", f"USING ({STAFF})"),
    ),
    policies(
        "ticket_messages",
        ("thread_read", "SELECT", f"USING ((user_id = {USER} AND NOT is_internal) OR {STAFF})"),
        (
            "thread_insert",
            "INSERT",
            f"WITH CHECK ((user_id = {USER} AND author_id = {USER} AND NOT is_internal) OR {STAFF})",
        ),
        ("staff_update", "UPDATE", f"USING ({STAFF}) WITH CHECK ({STAFF})"),
        ("staff_delete", "DELETE", f"USING ({STAFF})"),
    ),
]

# Learners may mark notifications read (and jobs record the email copy); nothing else changes.
COLUMN_GRANTS = (
    'REVOKE UPDATE ON "engagement"."notifications" FROM lms_app;\n'
    'GRANT UPDATE (read_at, emailed_at, updated_at) ON "engagement"."notifications" TO lms_app;',
    'GRANT UPDATE ON "engagement"."notifications" TO lms_app;',
)

COUNTERS = """
CREATE OR REPLACE FUNCTION engagement.refresh_counters() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE target uuid;
BEGIN
  IF TG_TABLE_NAME = 'reviews' THEN
    target := COALESCE(NEW.course_id, OLD.course_id);
    UPDATE catalog.courses c SET
      rating_count = s.n, rating_avg = COALESCE(s.avg, 0)
      FROM (SELECT count(*) AS n, round(avg(rating)::numeric, 2) AS avg
              FROM engagement.reviews WHERE course_id = target AND status = 'published') s
     WHERE c.id = target;
  ELSIF TG_TABLE_NAME = 'answers' THEN
    target := COALESCE(NEW.question_id, OLD.question_id);
    UPDATE engagement.questions q SET
      answer_count = (SELECT count(*) FROM engagement.answers a WHERE a.question_id = target AND a.hidden_at IS NULL),
      has_instructor_answer = EXISTS (SELECT 1 FROM engagement.answers a
                                       WHERE a.question_id = target AND a.is_instructor AND a.hidden_at IS NULL)
     WHERE q.id = target;
  ELSIF TG_TABLE_NAME = 'question_votes' THEN
    target := COALESCE(NEW.question_id, OLD.question_id);
    UPDATE engagement.questions q
       SET vote_count = (SELECT count(*) FROM engagement.question_votes v WHERE v.question_id = target)
     WHERE q.id = target;
  END IF;
  RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION engagement.refresh_counters() FROM PUBLIC;
CREATE TRIGGER trg_reviews_counters AFTER INSERT OR UPDATE OF rating, status OR DELETE ON engagement.reviews
  FOR EACH ROW EXECUTE FUNCTION engagement.refresh_counters();
CREATE TRIGGER trg_answers_counters AFTER INSERT OR UPDATE OF hidden_at, is_instructor OR DELETE ON engagement.answers
  FOR EACH ROW EXECUTE FUNCTION engagement.refresh_counters();
CREATE TRIGGER trg_votes_counters AFTER INSERT OR DELETE ON engagement.question_votes
  FOR EACH ROW EXECUTE FUNCTION engagement.refresh_counters();

-- A message updates its ticket: the requester's reply reopens it, a staff reply waits for them.
CREATE OR REPLACE FUNCTION engagement.touch_ticket() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NEW.is_internal THEN RETURN NULL; END IF;
  UPDATE engagement.tickets t SET
    last_message_at = NEW.created_at,
    updated_at = now(),
    status = CASE WHEN NEW.author_id = t.user_id THEN
                    CASE WHEN t.status = 'closed' THEN 'closed' ELSE 'open' END
                  ELSE CASE WHEN t.status IN ('open', 'waiting') THEN 'waiting' ELSE t.status END END
   WHERE t.id = NEW.ticket_id;
  RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION engagement.touch_ticket() FROM PUBLIC;
CREATE TRIGGER trg_ticket_messages_touch AFTER INSERT ON engagement.ticket_messages
  FOR EACH ROW EXECUTE FUNCTION engagement.touch_ticket();
"""
COUNTERS_REVERSE = """
DROP TRIGGER IF EXISTS trg_ticket_messages_touch ON engagement.ticket_messages;
DROP TRIGGER IF EXISTS trg_votes_counters ON engagement.question_votes;
DROP TRIGGER IF EXISTS trg_answers_counters ON engagement.answers;
DROP TRIGGER IF EXISTS trg_reviews_counters ON engagement.reviews;
DROP FUNCTION IF EXISTS engagement.touch_ticket();
DROP FUNCTION IF EXISTS engagement.refresh_counters();
"""

INHERIT = [
    rls.inherit_owner(S, "questions", "catalog.courses", "course_id"),
    rls.inherit_owner(S, "announcements", "catalog.courses", "course_id"),
    rls.inherit_owner(S, "answers", "engagement.questions", "question_id"),
    rls.inherit_owner(S, "question_votes", "engagement.questions", "question_id"),
    rls.inherit_parent(S, "ticket_messages", "engagement.tickets", "ticket_id"),
]


class Migration(migrations.Migration):
    dependencies = [("engagement", "0001_initial"), ("catalog", "0003_inherit_requires_visible_parent")]

    operations = [
        *(migrations.RunSQL(f, r) for f, r in POLICIES),
        migrations.RunSQL(*COLUMN_GRANTS),
        migrations.RunSQL(COUNTERS, COUNTERS_REVERSE),
        *(migrations.RunSQL(f, r) for f, r in INHERIT),
    ]
