"""Fill the database with a believable, fully fictional demo.

    python manage.py seed_demo                       # password from DEMO_PASSWORD or generated
    python manage.py seed_demo --password "..."      # choose the shared demo password
    python manage.py seed_demo --reset --yes-delete-everything   # wipe ALL domain data first

Everything goes through the real services and RLS contexts (the same code paths the API
uses), so the data respects every rule: published courses pass the checklist, money
goes through orders and the payment webhook path, earnings through the outbox, and
compliance statuses are computed by the engine. Stripe is never called: the gateway is
replaced for the duration of the command. No email leaves: mail goes to memory.
"""

import logging
import os
import random
import secrets
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections
from django.test.utils import override_settings
from django.utils import timezone

from apps.catalog import services as cat
from apps.catalog.models import (
    Category,
    CertificateTemplate,
    Course,
    CourseTopic,
    Lecture,
    Topic,
    VideoLibrary,
)
from apps.commerce import pricing
from apps.commerce import services as shop
from apps.commerce.gateway import to_stripe_amount
from apps.commerce.models import (
    Addon,
    AddonPrice,
    CartItem,
    Coupon,
    CoursePrice,
    Currency,
    Order,
    Plan,
    PlanPrice,
    PriceTier,
    Subscription,
    WishlistItem,
)
from apps.compliance import engine
from apps.compliance import services as compliance
from apps.compliance.models import CompletionRecord, MemberStatus
from apps.engagement import services as social
from apps.identity.models import InstructorProfile, User
from apps.learning import services as learning
from apps.learning.models import Enrollment, LectureProgress
from apps.org import services as org_services
from apps.org.models import JobRole, MemberJobRole, MemberUnit, OrgMember, OrgUnit, UnitManager
from apps.payouts import services as payouts
from apps.payouts.models import Payout
from apps.platform import services as platform
from core.tenancy import tenant_context

from . import demo_content as C

DOMAIN = "learnhub.example.com"
# Approximate ECB reference rates (EUR -> X), used only if the live ECB feed is unreachable
FALLBACK_EUR = {"USD": "1.16", "GBP": "0.87", "JPY": "175", "INR": "97.5", "AUD": "1.77", "CAD": "1.61",
                "CHF": "0.93", "SEK": "11.0", "NOK": "11.7", "DKK": "7.46", "PLN": "4.25", "CZK": "24.5",
                "HUF": "395", "RON": "5.05", "TRY": "47", "BRL": "6.3", "MXN": "21.5", "ZAR": "20.5",
                "SGD": "1.50", "HKD": "9.05", "CNY": "8.3", "KRW": "1620", "IDR": "18900", "MYR": "4.9",
                "PHP": "66", "THB": "37.5", "ILS": "3.9", "NZD": "1.95", "ISK": "145"}  # fmt: skip
KEEP = ("currencies", "price_tiers", "revenue_shares", "notification_templates", "badges")
SCHEMAS = (
    "identity",
    "org",
    "catalog",
    "learning",
    "compliance",
    "commerce",
    "payouts",
    "engagement",
    "platform",
)


def fake_checkout(**kw):
    return {"id": f"cs_demo_{kw['metadata']['id']}", "url": ""}


class Command(BaseCommand):
    help = "Seed a fictional demo: companies, courses, learners, sales, compliance, reviews."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="", help="Shared password for every demo account")
        parser.add_argument("--reset", action="store_true", help="Delete ALL domain data first")
        parser.add_argument("--yes-delete-everything", action="store_true", dest="confirm")
        parser.add_argument("--seed", type=int, default=2026, help="Random seed (same seed, same data)")

    # ------------------------------------------------------------------ entry
    def handle(self, *args, **opts):
        if opts["reset"]:
            if not opts["confirm"]:
                raise CommandError(
                    "--reset deletes every user, company, course and order. Add --yes-delete-everything."
                )
            self._reset()
        elif platform.get_setting("demo.seeded"):
            raise CommandError(
                "Demo data already exists. Use --reset --yes-delete-everything to start again."
            )

        for noisy in ("celery.app.trace", "httpx", "apps.compliance", "apps.platform.outbox"):
            logging.getLogger(noisy).setLevel(logging.WARNING)  # one line per step, not per job
        self.password = opts["password"] or os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(12)
        self.rnd = random.Random(opts["seed"])  # noqa: S311 - reproducible fake data, not security
        self.now = timezone.now()
        with (
            override_settings(  # background jobs run inline; no email leaves
                CELERY_TASK_ALWAYS_EAGER=True,
                CELERY_TASK_EAGER_PROPAGATES=True,
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ),
            mock.patch("apps.commerce.gateway.create_checkout_session", side_effect=fake_checkout),
            mock.patch(
                "apps.commerce.gateway.transfer", side_effect=lambda **kw: f"tr_demo_{kw['idempotency_key']}"
            ),
        ):
            self.step("Reference data", self.reference)
            self.step("Instructors", self.instructors)
            self.step("Courses", self.courses)
            self.step("Companies", self.companies)
            self.step("Compliance history", self.compliance_history)
            self.step("Learners and purchases", self.learners)
            self.step("Subscriptions", self.subscriptions)
            self.step("Reviews, Q&A, announcements, tickets", self.social)
            self.step("History dates, payouts, counters", self.finish)
        self.summary()

    def step(self, title, fn):
        started = timezone.now()
        self.stdout.write(f"  {title} ...", ending="")
        self.stdout.flush()
        fn()
        self.stdout.write(self.style.SUCCESS(f" done ({(timezone.now() - started).total_seconds():.0f}s)"))

    def _reset(self):
        with connections["owner"].cursor() as cur:
            cur.execute(
                "SELECT format('%%I.%%I', schemaname, tablename) FROM pg_tables"
                " WHERE schemaname = ANY(%s) AND NOT (tablename = ANY(%s))"
                " AND tablename NOT LIKE 'django_%%' AND tablename <> 'auth_permission'",
                [list(SCHEMAS), list(KEEP)],
            )
            tables = [r[0] for r in cur.fetchall()]
            cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")  # noqa: S608 - catalog names
        self.stdout.write(self.style.WARNING(f"  Deleted all data in {len(tables)} tables."))

    # ------------------------------------------------------------------ helpers
    def user(self, local, name, *, domain=DOMAIN, staff=False):
        email = f"{local}@{domain}"
        u = User.objects.create_user(email, self.password, full_name=name, is_staff=staff)
        EmailAddress.objects.create(user=u, email=email, verified=True, primary=True)
        return u

    def staff_ctx(self):
        return tenant_context(user_id=self.admin.id, staff=True)

    def ago(self, days_from, days_to):
        return self.now - timedelta(
            days=self.rnd.uniform(days_from, days_to), minutes=self.rnd.randint(0, 600)
        )

    # ------------------------------------------------------------------ steps
    def reference(self):
        self.admin = self.user("admin", "LearnHub Admin", staff=True)
        self.academy = self.user("academy", "LearnHub Academy", staff=True)  # author of the platform library
        with self.staff_ctx():
            self.categories = {}
            for i, (slug, name, icon) in enumerate(C.CATEGORIES):
                self.categories[slug] = Category.objects.create(name=name, slug=slug, icon=icon, sort_order=i)
            self.topics = {
                t: Topic.objects.create(name=t, slug=t.lower().replace(" ", "-")) for t in C.TOPICS
            }
            self.library = VideoLibrary.objects.create(
                name="Demo videos", environment="demo", bunny_library_id=int(settings.BUNNY_STREAM["LIBRARY_ID"] or 0),
                cdn_hostname=settings.BUNNY_STREAM.get("CDN_HOST", "") or "vz-demo.b-cdn.net", is_default=True,
            )  # fmt: skip
            self.template = CertificateTemplate.objects.create(
                name="LearnHub certificate", is_default=True, created_by=self.admin,
                signatory_name="Dr Helen Ward", signatory_title="Head of Learning",
            )  # fmt: skip
            # exchange rates: live ECB if reachable, otherwise a recent snapshot
            try:
                pricing.fetch_ecb()
            except Exception:  # noqa: BLE001 - offline seeding is fine
                pricing.store_ecb_rates(self.now.date(), {k: Decimal(v) for k, v in FALLBACK_EUR.items()})
            Currency.objects.filter(code__in=["GBP", "USD", "EUR"]).update(is_active=True)
            pricing.refresh_tier_amounts()
            self.tiers = {i: PriceTier.objects.get(name=f"Tier {i}") for i in range(1, 19)}
            # plans and the content-protection add-on (Stripe price ids are placeholders)
            self.personal_plan = Plan.objects.create(code="personal-monthly", name="Personal Plan", audience="personal",
                                                     interval="month", trial_days=7)  # fmt: skip
            Plan.objects.create(
                code="personal-yearly", name="Personal Plan (yearly)", audience="personal", interval="year"
            )
            self.team_plan = Plan.objects.create(code="team-yearly", name="Team Plan", audience="team",
                                                 interval="year", min_seats=5)  # fmt: skip
            for plan, prices in (
                (self.personal_plan, (1999, 2299, 2399)),
                (self.team_plan, (36000, 42000, 43000)),
            ):
                for code, amount in zip(("GBP", "EUR", "USD"), prices, strict=True):
                    PlanPrice.objects.create(plan=plan, currency_id=code, amount_minor=amount,
                                             stripe_price_id=f"price_demo_{plan.code}_{code.lower()}")  # fmt: skip
            self.protection = Addon.objects.create(code="content_protection", name="Content protection",
                                                   description="DRM video, no downloads or screen capture.")  # fmt: skip
            AddonPrice.objects.create(addon=self.protection, currency_id="GBP", interval="month", amount_minor=4900,
                                      stripe_price_id="price_demo_protection_gbp")  # fmt: skip

    def instructors(self):
        self.teachers = {}
        for handle, name, bio in C.INSTRUCTORS:
            u = self.user(handle, name)
            InstructorProfile.objects.create(
                user=u, status="approved", headline=bio.split(".")[0], bio=bio, public_slug=handle.replace(".", "-"),
                approved_at=self.ago(300, 400), expertise=[],
            )  # fmt: skip
            payouts.set_payout_account(
                user=u, method="stripe", stripe_account_id=f"acct_demo_{handle.split('.')[0]}"
            )
            with self.staff_ctx():
                payouts.verify_account(account=u.payout_account)
            self.teachers[handle] = u

    def build(self, spec, *, author, ownership, org_id=None):
        """One course through the real authoring flow, published at the end."""
        ctx = {"user_id": author.id, "org_id": org_id}
        with tenant_context(**ctx):
            course = cat.create_course(
                title=spec["title"], slug=spec["slug"], ownership=ownership, created_by=author, owner_org_id=org_id,
                subtitle=spec["subtitle"], level=spec["level"], category=self.categories[spec["category"]],
                cpd_hours=spec["cpd"], is_free=spec["free"],
                description=f"<p>{spec['subtitle']}. Short video lessons, readings, a knowledge check"
                            f"{' and a practical assignment' if spec['assignment'] else ''}.</p>",
            )  # fmt: skip
            CourseTopic.objects.bulk_create(
                [CourseTopic(course=course, topic=self.topics[t]) for t in spec["topics"]]
            )
            version = course.versions.get()
            for s_i, (section_title, lectures) in enumerate(spec["sections"]):
                section = cat.add_section(version=version, title=section_title)
                for l_i, title in enumerate(lectures):
                    if title.startswith("Reading: "):
                        cat.add_lecture(section=section, kind="article", title=title[9:],
                                        body=f"<h2>{title[9:]}</h2><p>Key points, examples and links for this topic.</p>",
                                        duration_sec=300)  # fmt: skip
                    else:
                        seconds = self.rnd.randint(180, 840)
                        asset = cat.create_media(
                            kind="video", status="ready", library=self.library, uploaded_by=author,
                            owner_org_id=org_id, duration_sec=seconds, encode_progress=100,
                            original_filename=f"{spec['slug']}-{s_i + 1}-{l_i + 1}.mp4",
                        )  # fmt: skip
                        cat.add_lecture(section=section, kind="video", title=title, video=asset,
                                        duration_sec=seconds, is_preview=(s_i == 0 and l_i == 0))  # fmt: skip
            final = cat.add_section(version=version, title="Check your knowledge")
            quiz = cat.add_lecture(section=final, kind="quiz", title="Knowledge check").quiz
            for kind, prompt, options in C.Q[spec["quiz"]]:
                opts = [{"body": text, "is_correct": bool(ok), **({"blank_index": 0} if kind == "fill_blank" else {})}
                        for text, ok in options]  # fmt: skip
                cat.add_question(quiz=quiz, kind=kind, prompt=prompt, options=opts,
                                 explanation="See the lecture on this topic for a recap.")  # fmt: skip
            if spec["assignment"]:
                a = cat.add_lecture(section=final, kind="assignment", title="Practical assignment").assignment
                cat.update_assignment(assignment=a, instructions=C.ASSIGN, max_score=100, pass_score=60)
            cat.submit(version=version, by=author)
        if ownership == "instructor":
            with self.staff_ctx():
                cat.approve(version=version, reviewer=self.admin, notes="Meets the quality checklist.")
        with self.staff_ctx():
            Course.objects.filter(pk=course.pk).update(certificate_template=self.template)
            if org_id is None:
                CoursePrice.objects.create(course=course, is_free=spec["free"],
                                           tier=None if spec["free"] else self.tiers[spec["tier"]])  # fmt: skip
        with tenant_context(**ctx):
            return Course.objects.get(pk=course.pk)

    def courses(self):
        self.market = [
            self.build(s, author=self.teachers[s["owner"]], ownership="instructor") for s in C.MARKETPLACE
        ]
        self.lib = {s["slug"]: self.build(s, author=self.academy, ownership="platform") for s in C.LIBRARY}
        with self.staff_ctx():
            Coupon.objects.create(
                code="WELCOME20", percent_off=20, starts_at=self.ago(60, 61), created_by=self.admin
            )
            Coupon.objects.create(code="DANIEL-LAUNCH", course=self.market[1], percent_off=50, max_redemptions=100,
                                  starts_at=self.ago(90, 91), created_by=self.teachers["daniel.reeve"])  # fmt: skip

    def companies(self):
        self.orgs = []
        for spec in C.COMPANIES:
            hr = self.user(spec["hr"][0], spec["hr"][1], domain=spec["domain"])
            org = org_services.create_organization(name=spec["name"], slug=spec["slug"], owner=hr)
            info = {"spec": spec, "org": org, "hr": hr, "teams": {}, "members": []}
            with tenant_context(org_id=org.id, user_id=hr.id):
                root = OrgUnit.objects.get(org=org, parent__isnull=True)
                roles = {r: JobRole.objects.create(org=org, name=r) for r in spec["roles"]}
                sites = []
                for region_name, site_names in spec["tree"]:
                    region = org_services.create_unit(parent=root, kind="region", name=region_name)
                    if not site_names:
                        sites.append((region, None))
                    for site_name in site_names:
                        site = org_services.create_unit(parent=region, kind="site", name=site_name)
                        sites.append((site, [org_services.create_unit(parent=site, kind="team", name=t)
                                             for t in spec["teams"]]))  # fmt: skip
                links_u, links_r, managers = [], [], []
                for i in range(spec["people"]):
                    site, teams = sites[i % len(sites)]
                    first, last = self.rnd.choice(C.FIRST), self.rnd.choice(C.LAST)
                    u = self.user(f"{first}.{last}.{i}".lower(), f"{first} {last}", domain=spec["domain"])
                    is_manager = i < len(sites)  # the first person at each site manages it
                    m = OrgMember.objects.create(
                        org=org, user=u, role="manager" if is_manager else "learner", joined_at=self.ago(30, 900),
                        job_title="Site Manager" if is_manager else "", employee_ref=f"E{1000 + i}",
                    )  # fmt: skip
                    unit = site if (is_manager or not teams) else teams[i % len(teams)]
                    links_u.append(MemberUnit(org=org, member=m, unit=unit, is_primary=True))
                    if is_manager:
                        managers.append(UnitManager(org=org, unit=site, member=m))
                        role = roles[[r for r in spec["roles"] if "Manager" in r or "Leader" in r][0]]
                    elif teams is None:
                        role = roles[spec["roles"][-1]]
                    else:
                        team_roles = (
                            spec["roles"][:2] if unit.name == spec["teams"][0] else spec["roles"][1:3]
                        )
                        role = roles[self.rnd.choice(team_roles)]
                    links_r.append(MemberJobRole(org=org, member=m, job_role=role))
                    info["members"].append(m)
                MemberUnit.objects.bulk_create(links_u)
                MemberJobRole.objects.bulk_create(links_r)
                UnitManager.objects.bulk_create(managers)
                info["roles"], info["units"] = roles, list(OrgUnit.objects.filter(org=org))
            company_course = (
                self.build(spec["induction"], author=hr, ownership="organization", org_id=org.id)
                if spec["induction"] else None
            )  # fmt: skip
            with tenant_context(org_id=org.id, user_id=hr.id):
                for slug, name, renewal, target in spec["requirements"]:
                    course = (
                        company_course
                        if company_course and slug == company_course.slug
                        else self.lib.get(slug)
                    )
                    if course is None:
                        course = next(c for c in self.market if c.slug == slug)
                    if target == "all":
                        targets = [{}]
                    elif target[0] == "role":
                        targets = [{"job_role_id": roles[target[1]].id}]
                    else:
                        targets = [{"unit_id": u.id} for u in info["units"] if u.name == target[1]]
                    compliance.create_requirement(org_id=org.id, course=course, name=name, created_by=hr,
                                                  targets=targets, renewal_months=renewal, due_days=30)  # fmt: skip
            platform.sync_entitlement(feature="business", source="grant", source_ref=org.id, active=True,
                                      ends_at=self.now + timedelta(days=300), org_id=org.id,
                                      seats_count=spec["people"] + 10)  # fmt: skip
            self.orgs.append(info)

    def compliance_history(self):
        """A realistic spread for the HR matrix: most people compliant, some expiring,
        a few expired or overdue, some part-way through, one exemption."""
        for info in self.orgs:
            org, hr = info["org"], info["hr"]
            with tenant_context(org_id=org.id, user_id=hr.id):
                rows = list(MemberStatus.objects.filter(org=org).select_related("requirement", "member"))
                records, overdue, in_progress = [], [], []
                for s in rows:
                    roll = self.rnd.random()
                    renewal = s.requirement.renewal_months or 0
                    if roll < 0.58:
                        days = self.rnd.uniform(15, (renewal * 30 - 40) if renewal else 400)
                    elif roll < 0.70 and renewal:
                        days = renewal * 30.4 - self.rnd.uniform(3, 25)  # expiring soon
                    elif roll < 0.78 and renewal:
                        days = renewal * 30.4 + self.rnd.uniform(5, 120)  # expired
                    elif roll < 0.88:
                        overdue.append(s.id)
                        continue
                    else:
                        in_progress.append((s.member.user_id, s.requirement.course_id))
                        continue
                    done = self.now - timedelta(days=days)
                    expires = None
                    if renewal:
                        expires = done + timedelta(days=renewal * 30.4)
                    records.append(CompletionRecord(
                        org=org, requirement=s.requirement, member=s.member, source="import", completed_at=done,
                        expires_at=expires, note="Imported from the previous training system", recorded_by=hr,
                    ))  # fmt: skip
                CompletionRecord.objects.bulk_create(records)
                MemberStatus.objects.filter(id__in=overdue).update(
                    assigned_at=self.now - timedelta(days=50), initial_due_at=self.now - timedelta(days=20)
                )
                for user_id, course_id in in_progress:
                    Enrollment.objects.filter(org=org, user_id=user_id, course_id=course_id).update(
                        progress_pct=self.rnd.choice([20, 40, 60, 80]), last_accessed_at=self.ago(1, 10)
                    )
                status = rows[0] if rows else None
                if status:
                    compliance.grant_exemption(status=status, reason="Office-based role, task not performed",
                                               granted_by=hr)  # fmt: skip
                engine.allow_long_statements()
                engine.refresh_org(org.id, reminders=False)

            # a few real completions through the player, producing company certificates
            fire = self.lib["fire-safety-awareness"]
            for m in info["members"][-3:]:
                with tenant_context(org_id=org.id, user_id=m.user_id):
                    e = Enrollment.objects.exclude(status="superseded").filter(org=org, user_id=m.user_id,
                                                                               course=fire).first()  # fmt: skip
                    if e is None or e.completed_at:
                        continue
                    for key in Lecture.objects.filter(version_id=fire.live_version_id).values_list(
                        "lecture_key", flat=True
                    ):
                        learning.complete_lecture(enrollment=e, lecture_key=key)

    def learners(self):
        """Marketplace learners buy through real orders (payment confirmed on the webhook
        path), then make progress; finished courses issue certificates."""
        self.people = []
        sellable = self.market + list(self.lib.values())
        weights = [8, 6, 7, 3, 6, 5, 6, 5, 3, 4, 5] + [2] * len(self.lib)
        for i in range(36):
            first, last = self.rnd.choice(C.FIRST), self.rnd.choice(C.LAST)
            u = self.user(f"{first}.{last}.l{i}".lower(), f"{first} {last}")
            self.people.append(u)
            picks = []
            for c in self.rnd.choices(sellable, weights=weights, k=self.rnd.randint(1, 4)):
                if c not in picks:
                    picks.append(c)
            currency = self.rnd.choices(["GBP", "USD", "EUR"], weights=[6, 3, 2])[0]
            with tenant_context(user_id=u.id):
                coupon = "WELCOME20" if self.rnd.random() < 0.15 else None
                order = shop.create_order(user=u, course_ids=[c.id for c in picks], currency=currency,
                                          coupon_code=coupon)["order"]  # fmt: skip
            if order.status == "pending":
                with self.staff_ctx():
                    cur = order.currency
                    shop.fulfil_order(order_id=order.id, payment_intent=f"pi_demo_{order.id.hex[:16]}",
                                      amount_minor=to_stripe_amount(order.total_minor, cur.code, cur.exponent),
                                      currency=cur.code)  # fmt: skip
            with tenant_context(user_id=u.id):
                for e in Enrollment.objects.filter(user=u, org__isnull=True).select_related("course"):
                    self.progress(e, self.rnd.choice([0, 0.15, 0.4, 0.7, 1, 1, 1]))
                if self.rnd.random() < 0.4:
                    for c in self.rnd.sample(self.market, 2):
                        if not Enrollment.objects.filter(user=u, course=c).exists():
                            WishlistItem.objects.get_or_create(user=u, course=c)
                if self.rnd.random() < 0.2:
                    c = self.rnd.choice(self.market)
                    if not Enrollment.objects.filter(user=u, course=c).exists():
                        CartItem.objects.get_or_create(user=u, course=c)

    def progress(self, enrollment, share):
        keys = list(
            Lecture.objects.filter(version_id=enrollment.course.live_version_id, is_required=True)
            .order_by("section__position", "position")
            .values_list("lecture_key", flat=True)
        )
        done = keys[: round(len(keys) * share)]
        if not done:
            return
        LectureProgress.objects.bulk_create([
            LectureProgress(enrollment=enrollment, org_id=None, user_id=enrollment.user_id, lecture_key=k,
                            watched_sec=self.rnd.randint(120, 600), completed_at=self.now) for k in done
        ])  # fmt: skip
        Enrollment.objects.filter(pk=enrollment.pk).update(
            last_lecture_key=done[-1], last_accessed_at=self.now
        )
        learning.refresh_course_progress(enrollment)

    def subscriptions(self):
        for u in self.people[:4]:  # personal-plan subscribers learning through the plan
            with self.staff_ctx():
                sub = Subscription.objects.create(
                    user=u, plan=self.personal_plan, currency_id="GBP", status="active",
                    stripe_subscription_id=f"sub_demo_{u.id.hex[:12]}", current_period_end=self.now + timedelta(days=21),
                )  # fmt: skip
                platform.sync_entitlement(feature="personal_plan", source="subscription", source_ref=sub.id,
                                          active=True, ends_at=sub.current_period_end, user_id=u.id)  # fmt: skip
            with tenant_context(user_id=u.id):
                for c in self.rnd.sample(self.market, 3):
                    if not Enrollment.objects.filter(user=u, course=c).exists():
                        self.progress(shop.enrol_with_plan(user=u, course=c), self.rnd.choice([0.2, 0.5, 1]))
        daniel = self.teachers["daniel.reeve"]
        platform.sync_entitlement(feature="content_protection", source="grant", source_ref=daniel.id, active=True,
                                  ends_at=self.now + timedelta(days=200), user_id=daniel.id)  # fmt: skip

    def social(self):
        for u in self.people:
            with tenant_context(user_id=u.id):
                for e in Enrollment.objects.filter(
                    user=u, org__isnull=True, progress_pct__gte=40
                ).select_related("course"):
                    if self.rnd.random() < 0.75:
                        rating, body = self.rnd.choice(C.REVIEWS)
                        social.write_review(user=u, course_id=e.course_id, rating=rating, body=body)
        for c in self.market[:6]:
            with self.staff_ctx():  # an instructor cannot list learners' enrolments (RLS), staff can
                learners = list(
                    Enrollment.objects.filter(course=c, org__isnull=True).values_list("user_id", flat=True)[
                        :3
                    ]
                )
            for (question, reply), learner_id in zip(C.QUESTIONS, learners, strict=False):
                learner = User.objects.get(pk=learner_id)
                with tenant_context(user_id=learner.id):
                    q = social.ask(user=learner, course_id=c.id, title=question, body=f"<p>{question}</p>")
                with tenant_context(user_id=c.created_by_id):
                    social.answer(user=c.created_by, question=q, body=f"<p>{reply}</p>")
        with tenant_context(user_id=self.teachers["daniel.reeve"].id):
            social.announce(user=self.teachers["daniel.reeve"], course_id=self.market[0].id,
                            title="New bonus lecture: debugging like a pro",
                            body="<p>I added a new lecture on debugging. Enjoy!</p>")  # fmt: skip
        for u, subject, category, text in (
            (self.people[0], "I was charged twice", "payment", "My card shows two payments for one order."),
            (self.people[1], "Video will not play", "technical", "The second lecture shows a black screen."),
            (self.orgs[0]["hr"], "Add 20 more seats", "business", "We are opening a new site next month."),
        ):
            with tenant_context(user_id=u.id):
                t = social.open_ticket(user=u, subject=subject, category=category, body=text)
            with self.staff_ctx():
                if category == "payment":
                    social.reply(ticket=t, author=self.admin, internal=True,
                                 body="Checked the payment logs: one charge is a card hold.")  # fmt: skip
                social.reply(ticket=t, author=self.admin, body="Thanks for getting in touch, we are on it.")
        for u in self.people:
            social.award_badges(u.id)

    def finish(self):
        """Spread purchases over the last six months (charts, revenue, payouts), close
        the payable months into payouts, and refresh denormalised counters."""
        with self.staff_ctx(), connection.cursor() as cur:
            cur.execute("SELECT id FROM commerce.orders WHERE status = 'paid' AND org_id IS NULL")
            ids = [r[0] for r in cur.fetchall()]
            dates = [self.ago(2, 180) for _ in ids]
            cur.execute(
                """
                WITH m AS (SELECT * FROM unnest(%s::uuid[], %s::timestamptz[]) AS t(order_id, d)),
                o AS (UPDATE commerce.orders x SET created_at = m.d, paid_at = m.d FROM m WHERE x.id = m.order_id),
                p AS (UPDATE commerce.payments x SET created_at = m.d FROM m WHERE x.order_id = m.order_id),
                i AS (UPDATE commerce.order_items x SET created_at = m.d FROM m WHERE x.order_id = m.order_id
                      RETURNING x.id, x.enrollment_id, m.d),
                e AS (UPDATE learning.enrollments x
                         SET enrolled_at = i.d, created_at = i.d,
                             completed_at = CASE WHEN x.completed_at IS NULL THEN NULL
                                                 ELSE LEAST(now(), i.d + interval '9 days') END,
                             last_accessed_at = LEAST(now(), i.d + interval '12 days')
                        FROM i WHERE x.id = i.enrollment_id RETURNING x.id, x.completed_at),
                c AS (UPDATE learning.certificates x SET issued_at = e.completed_at FROM e
                       WHERE x.enrollment_id = e.id AND e.completed_at IS NOT NULL)
                UPDATE payouts.earnings x SET earned_at = i.d, available_at = i.d + interval '30 days'
                  FROM i WHERE x.order_item_id = i.id
                """,
                [ids, dates],
            )
            cur.execute(
                """
                UPDATE catalog.courses c SET student_count = s.n
                  FROM (SELECT course_id, count(DISTINCT user_id) AS n FROM learning.enrollments
                         WHERE status IN ('active', 'completed') GROUP BY course_id) s
                 WHERE c.id = s.course_id
                """
            )
            cur.execute(
                """
                UPDATE identity.instructor_profiles p SET
                  student_count = s.students, rating_count = s.ratings,
                  rating_avg = COALESCE(s.avg, 0)
                  FROM (SELECT ci.user_id, sum(c.student_count) AS students, sum(c.rating_count) AS ratings,
                               round(sum(c.rating_avg * c.rating_count) / NULLIF(sum(c.rating_count), 0), 2) AS avg
                          FROM catalog.course_instructors ci JOIN catalog.courses c ON c.id = ci.course_id
                         GROUP BY ci.user_id) s
                 WHERE p.user_id = s.user_id
                """
            )
        last_month_end = self.now.date().replace(day=1) - timedelta(days=1)
        made = payouts.create_payouts(period_end=last_month_end, now=self.now)
        with self.staff_ctx():
            for p in Payout.objects.filter(id__in=made, user=self.teachers["daniel.reeve"]):
                payouts.approve_payout(payout=p, by=self.admin)
            platform.set_setting(key="demo.seeded", value=self.now.isoformat(), by=self.admin,
                                 description="Set by seed_demo")  # fmt: skip

    def summary(self):
        with self.staff_ctx():
            counts = {
                "users": User.objects.count(),
                "companies": len(self.orgs),
                "courses": Course.objects.count(),
                "enrolments": Enrollment.objects.count(),
                "orders": Order.objects.filter(status="paid").count(),
                "compliance rows": MemberStatus.objects.count(),
            }
        self.stdout.write(
            self.style.SUCCESS("\nDemo ready: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        )
        self.stdout.write(f"\nAll accounts share the password: {self.password}")
        self.stdout.write("  Platform admin       admin@learnhub.example.com")
        for handle, name, _ in C.INSTRUCTORS:
            self.stdout.write(f"  Instructor           {handle}@learnhub.example.com ({name})")
        for info in self.orgs:
            self.stdout.write(f"  Company HR           {info['hr'].email} ({info['org'].name})")
            self.stdout.write(f"  Company manager      {info['members'][0].user.email}")
        self.stdout.write(f"  Learner              {self.people[0].email}")
