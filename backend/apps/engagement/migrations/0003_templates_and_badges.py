"""Default notification wording and badges. Admins edit both from the console;
re-running never overwrites their edits."""

from django.db import migrations

TEMPLATES = [
    ("question_posted", "New question in {course}", 'A learner asked: "{title}"', True),
    ("answer_posted", "New answer to your question", 'Someone answered "{title}" in {course}.', True),
    ("review_reply", "The instructor replied to your review", "Your review of {course} has a reply.", True),
    ("announcement", "{course}: {title}", "Your instructor posted an announcement.", True),
    ("badge_awarded", "You earned a badge: {badge}", "Well done! See all your achievements.", False),
    ("ticket_reply", "Support replied ({reference})", 'There is a new reply on "{subject}".', True),
    ("certificate_issued", "Your certificate for {course}", "Congratulations on completing {course}.", True),
    ("payout_paid", "Payout sent", "Your payout of {amount} is on its way.", True),
]
BADGES = [
    ("first-course", "First course", "Completed your first course", "graduation-cap", "courses_completed", 1),
    ("five-courses", "Keen learner", "Completed 5 courses", "book-open", "courses_completed", 5),
    ("ten-certificates", "Certified", "Earned 10 certificates", "award", "certificates", 10),
    ("first-review", "Critic", "Wrote your first review", "star", "reviews", 1),
    ("helper", "Helper", "Answered 10 questions", "message-circle", "answers", 10),
]


def load(apps, schema_editor):
    db = schema_editor.connection.alias
    Template = apps.get_model("engagement", "NotificationTemplate")
    Badge = apps.get_model("engagement", "Badge")
    for code, title, body, email in TEMPLATES:
        Template.objects.using(db).get_or_create(code=code, defaults={"title": title, "body": body, "email_enabled": email})
    for code, name, desc, icon, criterion, threshold in BADGES:
        Badge.objects.using(db).get_or_create(
            code=code,
            defaults={"name": name, "description": desc, "icon": icon, "criterion": criterion, "threshold": threshold},
        )


class Migration(migrations.Migration):
    dependencies = [("engagement", "0002_security_and_counters")]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
