"""The compliance status engine: set-based SQL, one company at a time.

Every function runs inside an RLS context for ONE company (tenant_context(org_id=...)
or a request with app.org_id set) and filters by that org_id explicitly as well, so the
planner uses the (org_id, ...) indexes and RLS is a second wall, not the only one.

A run for a 10,000-person company is a handful of statements, never a loop per person:

    sync_assignments     who must do what: insert/delete member_status rows from targets,
                         count earlier company completions, enrol newly assigned people
    record_completions   course completion -> immutable completion_records row
    recompute            derive status / due_at / expiry for every affected row; rows
                         whose values did not change are not rewritten (no bloat)
    open_renewals        expiring or expired -> supersede the old enrolment, open a new one
    plan_reminders       insert due reminders; the unique key makes re-runs harmless

Writers take a per-company advisory lock first, so the nightly job and an event-driven
refresh of the same company queue behind each other instead of deadlocking.

`now` is a parameter everywhere so behaviour over months can be tested exactly.
"""

from datetime import datetime
from uuid import UUID

from django.db import connection
from django.utils import timezone

Ids = list[UUID] | None


def _ids(values) -> list[UUID] | None:
    return None if values is None else list(values)


def lock_org(org_id: UUID) -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('compliance:' || %s::text, 0))", [org_id])


def allow_long_statements(seconds: int = 120) -> None:
    """Background jobs only: lift lms_app's 15 s request timeout for this transaction."""
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('statement_timeout', %s, true)", [f"{int(seconds)}s"])


# Who a target selects. include_subunits uses the GiST-indexed ltree path.
_TARGETED = """
SELECT DISTINCT t.requirement_id, m.id AS member_id
  FROM compliance.requirement_targets t
  JOIN compliance.requirements q ON q.id = t.requirement_id AND q.archived_at IS NULL
  JOIN org.org_members m ON m.org_id = t.org_id AND m.removed_at IS NULL
  LEFT JOIN org.org_units tu ON tu.id = t.unit_id
 WHERE t.org_id = %(org)s
   AND (%(reqs)s::uuid[] IS NULL OR t.requirement_id = ANY(%(reqs)s::uuid[]))
   AND (%(members)s::uuid[] IS NULL OR m.id = ANY(%(members)s::uuid[]))
   AND (t.unit_id IS NULL OR EXISTS (
         SELECT 1 FROM org.member_units mu JOIN org.org_units u ON u.id = mu.unit_id
          WHERE mu.member_id = m.id AND u.archived_at IS NULL
            AND (u.id = t.unit_id OR (t.include_subunits AND u.path <@ tu.path))))
   AND (t.job_role_id IS NULL OR EXISTS (
         SELECT 1 FROM org.member_job_roles mj
          WHERE mj.member_id = m.id AND mj.job_role_id = t.job_role_id))
"""


def sync_assignments(org_id: UUID, *, requirement_ids: Ids = None, member_ids: Ids = None, now=None) -> dict:
    """Make member_status match the targets. Returns {"added": [...], "removed": n}."""
    now = now or timezone.now()
    p = {"org": org_id, "reqs": _ids(requirement_ids), "members": _ids(member_ids), "now": now}
    with connection.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO compliance.member_status
                   (id, created_at, updated_at, org_id, requirement_id, member_id, status,
                    assigned_at, initial_due_at, evaluated_at)
            SELECT uuidv7(), %(now)s, %(now)s, %(org)s, tg.requirement_id, tg.member_id, 'not_started',
                   %(now)s, %(now)s + make_interval(days => q.due_days), %(now)s
              FROM ({_TARGETED}) tg
              JOIN compliance.requirements q ON q.id = tg.requirement_id
            ON CONFLICT (requirement_id, member_id) DO NOTHING
            RETURNING id
            """,  # noqa: S608 - fixed SQL fragment, values are parameters
            p,
        )
        added = [r[0] for r in cur.fetchall()]
        cur.execute(
            f"""
            WITH gone AS (
                SELECT s.id FROM compliance.member_status s
                 WHERE s.org_id = %(org)s
                   AND (%(reqs)s::uuid[] IS NULL OR s.requirement_id = ANY(%(reqs)s::uuid[]))
                   AND (%(members)s::uuid[] IS NULL OR s.member_id = ANY(%(members)s::uuid[]))
                   AND NOT EXISTS (SELECT 1 FROM ({_TARGETED}) tg
                                    WHERE tg.requirement_id = s.requirement_id AND tg.member_id = s.member_id)
            ), reminders AS (
                DELETE FROM compliance.reminders r USING gone WHERE r.member_status_id = gone.id
            )
            DELETE FROM compliance.member_status s USING gone WHERE s.id = gone.id
            """,  # noqa: S608
            p,
        )
        removed = cur.rowcount
    if added:
        record_completions(org_id, status_ids=added)  # earlier company completions count
        _enrol(org_id, added, now)
    return {"added": added, "removed": removed}


def _enrol(org_id: UUID, status_ids: list[UUID], now: datetime) -> None:
    """A company enrolment for each newly assigned person who has no current one."""
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO learning.enrollments
                   (id, created_at, updated_at, org_id, user_id, course_id, source, source_ref,
                    status, enrolled_at, progress_pct)
            SELECT DISTINCT ON (m.user_id, q.course_id)
                   uuidv7(), %(now)s, %(now)s, s.org_id, m.user_id, q.course_id, 'organization', q.id,
                   'active', %(now)s, 0
              FROM compliance.member_status s
              JOIN compliance.requirements q ON q.id = s.requirement_id
              JOIN org.org_members m ON m.id = s.member_id
              JOIN catalog.courses c ON c.id = q.course_id AND c.live_version_id IS NOT NULL
             WHERE s.org_id = %(org)s AND s.id = ANY(%(ids)s::uuid[])
            ON CONFLICT DO NOTHING
            """,
            {"org": org_id, "ids": status_ids, "now": now},
        )


def record_completions(
    org_id: UUID, *, status_ids: Ids = None, enrollment_id: UUID | None = None
) -> list[UUID]:
    """Turn company course completions into completion records. Returns affected member ids.

    Only enrolments and certificates of THIS company qualify (e.org_id = s.org_id, and a
    composite FK repeats the rule), so personal learning never counts automatically.
    A new record clears any deadline extension from the previous cycle.
    """
    with connection.cursor() as cur:
        cur.execute(
            """
            WITH ins AS (
                INSERT INTO compliance.completion_records
                       (id, created_at, updated_at, org_id, requirement_id, member_id, source,
                        completed_at, expires_at, enrollment_id, certificate_id, note, void_reason)
                SELECT uuidv7(), now(), now(), s.org_id, s.requirement_id, s.member_id, 'course',
                       e.completed_at,
                       CASE WHEN q.renewal_months IS NULL THEN NULL
                            ELSE e.completed_at + make_interval(months => q.renewal_months) END,
                       e.id, c.id, '', ''
                  FROM compliance.member_status s
                  JOIN compliance.requirements q ON q.id = s.requirement_id
                  JOIN org.org_members m ON m.id = s.member_id
                  JOIN learning.enrollments e
                    ON e.org_id = s.org_id AND e.user_id = m.user_id AND e.course_id = q.course_id
                   AND e.completed_at IS NOT NULL
                  JOIN learning.certificates c ON c.enrollment_id = e.id AND c.revoked_at IS NULL
                 WHERE s.org_id = %(org)s
                   AND (%(ids)s::uuid[] IS NULL OR s.id = ANY(%(ids)s::uuid[]))
                   AND (%(enrol)s::uuid IS NULL OR e.id = %(enrol)s::uuid)
                ON CONFLICT (requirement_id, enrollment_id) DO NOTHING
                RETURNING requirement_id, member_id
            )
            UPDATE compliance.member_status s SET due_override_at = NULL
              FROM ins WHERE s.requirement_id = ins.requirement_id AND s.member_id = ins.member_id
            RETURNING s.member_id
            """,
            {"org": org_id, "ids": _ids(status_ids), "enrol": enrollment_id},
        )
        return list({r[0] for r in cur.fetchall()})


def recompute(org_id: UUID, *, requirement_ids: Ids = None, member_ids: Ids = None, now=None) -> int:
    """Derive status for the selected rows. Returns how many rows changed."""
    now = now or timezone.now()
    with connection.cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (r.requirement_id, r.member_id)
                       r.requirement_id, r.member_id, r.id, r.completed_at, r.expires_at
                  FROM compliance.completion_records r
                 WHERE r.org_id = %(org)s AND r.voided_at IS NULL AND r.completed_at <= %(now)s
                   AND (%(reqs)s::uuid[] IS NULL OR r.requirement_id = ANY(%(reqs)s::uuid[]))
                   AND (%(members)s::uuid[] IS NULL OR r.member_id = ANY(%(members)s::uuid[]))
                 ORDER BY r.requirement_id, r.member_id, r.completed_at DESC, r.id DESC
            ), calc AS (
                SELECT s.id, l.id AS record_id, l.completed_at, l.expires_at,
                       CASE WHEN l.id IS NULL THEN COALESCE(s.due_override_at, s.initial_due_at)
                            WHEN l.expires_at IS NULL THEN NULL
                            ELSE COALESCE(s.due_override_at, l.expires_at) END AS due_at,
                       CASE
                         WHEN EXISTS (
                              SELECT 1 FROM compliance.exemptions x
                               WHERE x.org_id = s.org_id AND x.requirement_id = s.requirement_id
                                 AND x.member_id = s.member_id AND x.revoked_at IS NULL
                                 AND x.starts_at <= %(now)s AND (x.ends_at IS NULL OR x.ends_at > %(now)s))
                              THEN 'exempt'
                         WHEN l.id IS NOT NULL AND l.expires_at IS NULL THEN 'compliant'
                         WHEN l.expires_at > %(now)s + make_interval(days => q.expiring_soon_days)
                              THEN 'compliant'
                         WHEN l.expires_at > %(now)s THEN 'expiring_soon'
                         WHEN l.id IS NOT NULL THEN 'expired'
                         WHEN COALESCE(s.due_override_at, s.initial_due_at) <= %(now)s THEN 'overdue'
                         WHEN EXISTS (
                              SELECT 1 FROM learning.enrollments e JOIN org.org_members m ON m.id = s.member_id
                               WHERE e.org_id = s.org_id AND e.user_id = m.user_id AND e.course_id = q.course_id
                                 AND e.status = 'active' AND e.progress_pct > 0)
                              THEN 'in_progress'
                         ELSE 'not_started'
                       END AS status
                  FROM compliance.member_status s
                  JOIN compliance.requirements q ON q.id = s.requirement_id
                  LEFT JOIN latest l ON l.requirement_id = s.requirement_id AND l.member_id = s.member_id
                 WHERE s.org_id = %(org)s
                   AND (%(reqs)s::uuid[] IS NULL OR s.requirement_id = ANY(%(reqs)s::uuid[]))
                   AND (%(members)s::uuid[] IS NULL OR s.member_id = ANY(%(members)s::uuid[]))
            )
            UPDATE compliance.member_status s
               SET status = c.status, due_at = c.due_at, record_id = c.record_id,
                   completed_at = c.completed_at, expires_at = c.expires_at,
                   evaluated_at = %(now)s, updated_at = %(now)s
              FROM calc c
             WHERE s.id = c.id
               AND (s.status, s.due_at, s.record_id, s.expires_at)
                   IS DISTINCT FROM (c.status, c.due_at, c.record_id, c.expires_at)
            """,
            {"org": org_id, "reqs": _ids(requirement_ids), "members": _ids(member_ids), "now": now},
        )
        return cur.rowcount


def open_renewals(org_id: UUID, *, member_ids: Ids = None, now=None) -> int:
    """Expiring soon or expired: the completed enrolment becomes 'superseded' (kept as
    evidence, certificate untouched) and a fresh enrolment opens for the retake."""
    now = now or timezone.now()
    with connection.cursor() as cur:
        cur.execute(
            """
            WITH due AS (
                SELECT DISTINCT e.id, q.id AS requirement_id
                  FROM compliance.member_status s
                  JOIN compliance.requirements q ON q.id = s.requirement_id AND q.archived_at IS NULL
                  JOIN org.org_members m ON m.id = s.member_id AND m.removed_at IS NULL
                  JOIN learning.enrollments e
                    ON e.org_id = s.org_id AND e.user_id = m.user_id AND e.course_id = q.course_id
                   AND e.status = 'completed'
                 WHERE s.org_id = %(org)s AND s.status IN ('expiring_soon', 'expired')
                   AND (%(members)s::uuid[] IS NULL OR s.member_id = ANY(%(members)s::uuid[]))
            )
            UPDATE learning.enrollments e SET status = 'superseded', updated_at = %(now)s
              FROM (SELECT DISTINCT ON (id) id, requirement_id FROM due) d
             WHERE e.id = d.id
            RETURNING e.org_id, e.user_id, e.course_id, d.requirement_id
            """,
            {"org": org_id, "members": _ids(member_ids), "now": now},
        )
        renewed = cur.fetchall()
        if renewed:
            cur.executemany(
                """
                INSERT INTO learning.enrollments
                       (id, created_at, updated_at, org_id, user_id, course_id, source, source_ref,
                        status, enrolled_at, progress_pct)
                VALUES (uuidv7(), %s, %s, %s, %s, %s, 'organization', %s, 'active', %s, 0)
                ON CONFLICT DO NOTHING
                """,
                [(now, now, o, u, c, r, now) for o, u, c, r in renewed],
            )
        return len(renewed)


def plan_reminders(org_id: UUID, *, now=None) -> list[UUID]:
    """Insert the reminders that are due now; returns the new ids to deliver.

    due_soon / expiring_soon: the smallest threshold in reminder_days (e.g. 14, 3) that
    the deadline is now within, so a missed day never produces two emails at once.
    overdue / expired: repeat every overdue_every_days (step 0, 1, 2 ...).
    """
    now = now or timezone.now()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO compliance.reminders
                   (id, created_at, updated_at, org_id, member_status_id, kind, due_at, step, error)
            SELECT uuidv7(), %(now)s, %(now)s, s.org_id, s.id, k.kind, s.due_at, k.step, ''
              FROM compliance.member_status s
              JOIN compliance.requirements q ON q.id = s.requirement_id AND q.archived_at IS NULL
              JOIN org.org_members m ON m.id = s.member_id AND m.removed_at IS NULL
             CROSS JOIN LATERAL (
                   SELECT CASE WHEN s.status = 'expiring_soon' THEN 'expiring_soon' ELSE 'due_soon' END AS kind,
                          (SELECT min(d)::int FROM unnest(q.reminder_days) d
                            WHERE d >= ceil(extract(epoch FROM s.due_at - %(now)s) / 86400)) AS step
                    WHERE s.status IN ('not_started', 'in_progress', 'expiring_soon') AND s.due_at > %(now)s
                   UNION ALL
                   SELECT s.status,
                          floor(extract(epoch FROM %(now)s - s.due_at) / 86400 / q.overdue_every_days)::int
                    WHERE s.status IN ('overdue', 'expired') AND q.overdue_every_days > 0
                      AND s.due_at <= %(now)s
             ) k
             WHERE s.org_id = %(org)s AND s.due_at IS NOT NULL AND k.step IS NOT NULL
            ON CONFLICT (member_status_id, kind, due_at, step) DO NOTHING
            RETURNING id
            """,
            {"org": org_id, "now": now},
        )
        return [r[0] for r in cur.fetchall()]


def refresh_org(
    org_id: UUID, *, member_ids: Ids = None, requirement_ids: Ids = None, now=None, reminders: bool = True
) -> dict:
    """The whole pipeline for one company (or some of its people / requirements).
    Event-driven refreshes pass reminders=False: the nightly run sends them."""
    now = now or timezone.now()
    lock_org(org_id)
    sync = sync_assignments(org_id, requirement_ids=requirement_ids, member_ids=member_ids, now=now)
    changed = recompute(org_id, requirement_ids=requirement_ids, member_ids=member_ids, now=now)
    renewed = open_renewals(org_id, member_ids=member_ids, now=now)
    planned = plan_reminders(org_id, now=now) if reminders else []
    return {
        "added": len(sync["added"]),
        "removed": sync["removed"],
        "changed": changed,
        "renewed": renewed,
        "reminders": planned,
    }
