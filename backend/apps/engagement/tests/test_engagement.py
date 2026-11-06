"""Engagement: reviews and course ratings, Q&A counters and privacy, announcements
fan-out, notification inbox limits, badges, and support tickets with internal notes."""

from django.core import mail
from django.db import DatabaseError, ProgrammingError, connection, transaction
from django.utils import timezone

from apps.catalog import services as cat
from apps.catalog.models import Course
from apps.engagement import notify, services
from apps.engagement.models import (
    Notification,
    NotificationPreference,
    Question,
    Ticket,
    TicketMessage,
    UserBadge,
)
from apps.identity.models import User
from apps.learning import services as learning
from apps.org import services as org_services
from apps.org.models import OrgMember
from core.errors import ServiceError
from core.tenancy import tenant_context
from core.tests.base import SchemaTransactionTestCase


class EngagementBase(SchemaTransactionTestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff@learnhub-demo.com", "x", is_staff=True)
        self.tom = User.objects.create_user("tom@teach.com", "x", full_name="Tom Teacher")
        self.sara = User.objects.create_user("sara@demo.com", "x", full_name="Sara")
        self.omar = User.objects.create_user("omar@demo.com", "x")
        self.hr = User.objects.create_user("hr@acme-demo.com", "x")
        self.STAFF = {"user_id": self.staff.id, "staff": True}
        self.course = self.make_course(self.tom, "django", ownership="instructor")
        self.acme = org_services.create_organization(name="Acme", slug="acme", owner=self.hr)
        with tenant_context(org_id=self.acme.id, user_id=self.hr.id):
            OrgMember.objects.create(org=self.acme, user=self.sara, joined_at=timezone.now())
            self.private = self.make_course(self.hr, "induction", ownership="organization", org=self.acme.id)
        for u in (self.sara, self.omar):
            with tenant_context(user_id=u.id):
                learning.enrol(user=u, course=self.course, source="purchase")

    def make_course(self, owner, slug, ownership, org=None):
        with tenant_context(user_id=owner.id, org_id=org):
            c = cat.create_course(
                title=slug.title(), slug=slug, ownership=ownership, created_by=owner, owner_org_id=org
            )
            sec = cat.add_section(version=c.versions.get(), title="s")
            cat.add_lecture(section=sec, kind="article", title="r", body="<p>x</p>")
            cat.submit(version=c.versions.get(), by=owner)
        if ownership == "instructor":
            with tenant_context(**self.STAFF):
                cat.approve(version=c.versions.get(), reviewer=self.staff)
        with tenant_context(user_id=owner.id, org_id=org):
            return Course.objects.get(pk=c.pk)

    def inbox(self, user):
        with tenant_context(user_id=user.id):
            return list(Notification.objects.filter(user=user).values_list("kind", flat=True))


class ReviewsTest(EngagementBase):
    def test_ratings_follow_reviews_and_only_learners_review(self):
        with tenant_context(user_id=self.sara.id):
            services.write_review(user=self.sara, course_id=self.course.id, rating=5, body="Great")
        with tenant_context(user_id=self.omar.id):
            services.write_review(user=self.omar, course_id=self.course.id, rating=4)
            services.write_review(
                user=self.omar, course_id=self.course.id, rating=2
            )  # edit, not a second review
        self.course.refresh_from_db()
        self.assertEqual((self.course.rating_count, str(self.course.rating_avg)), (2, "3.50"))
        outsider = User.objects.create_user("x@demo.com", "x")
        with tenant_context(user_id=outsider.id), self.assertRaises(ServiceError):
            services.write_review(user=outsider, course_id=self.course.id, rating=1)

        with tenant_context(user_id=self.tom.id):
            review = services.reply_to_review(
                review=self.course.reviews.get(user=self.sara), instructor=self.tom, body="Thanks!"
            )
            self.assertEqual(review.instructor_reply, "Thanks!")
        self.assertIn("review_reply", self.inbox(self.sara))
        with tenant_context(user_id=self.omar.id):  # cannot reply to someone else's course
            with self.assertRaises(ServiceError):
                services.reply_to_review(review=review, instructor=self.omar, body="spam")
            # and cannot edit Sara's review directly in the database either
            with connection.cursor() as cur:
                cur.execute("UPDATE engagement.reviews SET rating = 1 WHERE user_id = %s", [self.sara.id])
                self.assertEqual(cur.rowcount, 0)
        with tenant_context(**self.STAFF):
            services.moderate_review(review=review, hide=True)
        self.course.refresh_from_db()
        self.assertEqual(self.course.rating_count, 1)


class QATest(EngagementBase):
    def test_counters_notifications_and_votes(self):
        mail.outbox.clear()
        with tenant_context(user_id=self.sara.id):
            q = services.ask(user=self.sara, course_id=self.course.id, title="Why migrations?", body="...")
        self.assertIn("question_posted", self.inbox(self.tom))
        self.assertEqual(len(mail.outbox), 1)  # the instructor gets the email copy
        with tenant_context(user_id=self.omar.id):
            services.answer(user=self.omar, question=q, body="Because schema.")
            self.assertTrue(services.toggle_vote(user=self.omar, question=q))
        with tenant_context(user_id=self.tom.id):
            services.answer(user=self.tom, question=q, body="Official answer")
        with tenant_context(user_id=self.sara.id):
            q = Question.objects.get(pk=q.pk)
            self.assertEqual((q.answer_count, q.vote_count, q.has_instructor_answer), (2, 1, True))
            with self.assertRaises(ServiceError):
                services.toggle_vote(user=self.sara, question=q)  # own question
        self.assertEqual(self.inbox(self.sara).count("answer_posted"), 2)

    def test_company_course_qa_stays_inside_the_company(self):
        with tenant_context(org_id=self.acme.id, user_id=self.sara.id):
            learning.enrol(user=self.sara, course=self.private, source="organization", org_id=self.acme.id)
            q = services.ask(user=self.sara, course_id=self.private.id, title="Where is HR?", body="...")
            self.assertEqual(Question.objects.get(pk=q.pk).owner_org_id, self.acme.id)
        with tenant_context(user_id=self.omar.id):
            self.assertFalse(Question.objects.filter(pk=q.pk).exists())
            with self.assertRaises(ServiceError):  # the course itself is invisible
                services.ask(user=self.omar, course_id=self.private.id, title="x", body="y")
            # forcing it straight into the database is refused too (no silent "public" copy)
            with self.assertRaises(ProgrammingError), transaction.atomic(), connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO engagement.questions (id, created_at, updated_at, user_id, course_id, title, body,"
                    " answer_count, vote_count, has_instructor_answer) VALUES"
                    " (uuidv7(), now(), now(), %s, %s, 't', 'b', 0, 0, false)",
                    [self.omar.id, self.private.id],
                )


class NotificationsTest(EngagementBase):
    def test_announcement_fans_out_and_inbox_is_locked_down(self):
        with tenant_context(user_id=self.omar.id):
            NotificationPreference.objects.create(user=self.omar, kind="announcement", email=False)
        mail.outbox.clear()
        with tenant_context(user_id=self.tom.id):
            services.announce(user=self.tom, course_id=self.course.id, title="New section", body="Enjoy")
        self.assertEqual(self.inbox(self.sara), ["announcement"])
        self.assertEqual(self.inbox(self.omar), ["announcement"])
        self.assertEqual([m.to for m in mail.outbox], [["sara@demo.com"]])  # Omar opted out of email
        with tenant_context(user_id=self.sara.id):
            self.assertEqual(Notification.objects.count(), 1)  # only her own
            self.assertEqual(notify.mark_read(user=self.sara), 1)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute("UPDATE engagement.notifications SET title = 'phish', url = '//evil.test'")
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO engagement.notifications (id, created_at, updated_at, user_id, kind, title, body, url,"
                    " dedupe_key) VALUES (uuidv7(), now(), now(), %s, 'x', 'x', '', '', '')",
                    [self.omar.id],
                )

    def test_templates_are_plain_substitution(self):
        self.assertEqual(
            notify.render("Hi {name}{missing} {name.__class__}", {"name": "Sara"}), "Hi Sara {name.__class__}"
        )
        self.assertEqual(notify._safe_url("//evil.test/x"), "")


class BadgesAndSupportTest(EngagementBase):
    def test_badges_awarded_once(self):
        with tenant_context(user_id=self.sara.id):
            services.write_review(user=self.sara, course_id=self.course.id, rating=5)
        services.award_badges(self.sara.id)  # running again awards nothing new
        with tenant_context(user_id=self.sara.id):
            self.assertEqual(UserBadge.objects.filter(user=self.sara).count(), 1)
        self.assertEqual(self.inbox(self.sara).count("badge_awarded"), 1)

    def test_ticket_thread_hides_internal_notes(self):
        with tenant_context(user_id=self.sara.id):
            t = services.open_ticket(
                user=self.sara, subject="Refund", category="payment", body="Please refund"
            )
        with tenant_context(**self.STAFF):
            services.reply(ticket=t, author=self.staff, body="Customer seems fine", internal=True)
            services.reply(ticket=t, author=self.staff, body="Refund done")
            self.assertEqual(Ticket.objects.get(pk=t.pk).status, "waiting")
        with tenant_context(user_id=self.sara.id):
            bodies = list(TicketMessage.objects.filter(ticket=t).values_list("body", flat=True))
            self.assertEqual(bodies, ["Please refund", "Refund done"])  # the internal note is invisible
            with self.assertRaises(ServiceError):
                services.reply(ticket=t, author=self.sara, body="sneaky", internal=True)
            services.reply(ticket=t, author=self.sara, body="Thanks")
            self.assertEqual(Ticket.objects.get(pk=t.pk).status, "open")
            services.set_ticket_status(ticket=t, status="closed", by=self.sara)
            with self.assertRaises(ServiceError):
                services.set_ticket_status(ticket=t, status="open", by=self.sara)
        with tenant_context(user_id=self.omar.id):
            self.assertFalse(Ticket.objects.filter(pk=t.pk).exists())
        self.assertIn("ticket_reply", self.inbox(self.sara))
