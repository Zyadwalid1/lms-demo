"""python manage.py check_mail you@kentbusinesscollege.com

Sends ONE real test email through Microsoft Graph (whatever MAIL_MODE says), step by
step, with a fix for each failure. Never prints secrets.
"""

import logging

import httpx
from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings

from core.mail import GraphEmailBackend, allowed

HINTS = {
    "token": "Check MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET (the secret's Value, "
    "not its Secret ID, and not expired).",
    401: "The token was refused: the app registration needs the Microsoft Graph APPLICATION permission "
    "'Mail.Send' with admin consent granted.",
    403: "Graph refused to send as this mailbox: check 'Mail.Send' (application) has admin consent, and that "
    "no Exchange application access policy blocks this app from MICROSOFT_GRAPH_SENDER.",
    404: "MICROSOFT_GRAPH_SENDER is not a mailbox in this tenant (it must be a real user or shared mailbox).",
}


class Command(BaseCommand):
    help = "Send one real test email through Microsoft Graph."

    def add_arguments(self, parser):
        parser.add_argument("to", help="recipient (must be inside MAIL_ALLOWED_DOMAINS when that is set)")

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  PASS  {msg}"))

    def fail(self, msg, hint, detail=""):
        self.stdout.write(self.style.ERROR(f"  FAIL  {msg}{f' ({detail})' if detail else ''}"))
        self.stdout.write(f"        -> {hint}")

    def handle(self, *args, to, **opts):
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("core.mail").setLevel(logging.CRITICAL)  # this command reports failures itself
        self.stdout.write("Microsoft Graph email check")
        missing = [n for n, v in (("MICROSOFT_TENANT_ID", settings.GRAPH_TENANT_ID),
                                  ("MICROSOFT_CLIENT_ID", settings.GRAPH_CLIENT_ID),
                                  ("MICROSOFT_CLIENT_SECRET", settings.GRAPH_CLIENT_SECRET)) if not v]  # fmt: skip
        if missing:
            raise CommandError("Fill these in backend/.env: " + ", ".join(missing))
        sender = settings.GRAPH_SENDER
        if "@" not in sender or sender.endswith("@example.com"):
            raise CommandError(
                "Set MICROSOFT_GRAPH_SENDER to the no-reply mailbox, e.g. no-reply@yourdomain.com"
            )
        if not allowed(to):
            raise CommandError(f"{to} is outside MAIL_ALLOWED_DOMAINS; use an address in an allowed domain.")
        self.ok(f"settings present (sender {sender})")
        if settings.MAIL_MODE != "graph":
            self.stdout.write(
                "  NOTE  MAIL_MODE is not 'graph': the app itself only logs emails until you set it."
            )

        with override_settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        ):
            backend = GraphEmailBackend(fail_silently=False)
            with backend._client() as client:
                try:
                    backend._token(client)
                    self.ok("app sign-in (client credentials)")
                except httpx.HTTPStatusError as e:
                    codes = e.response.json().get("error_codes", []) if e.response.content else []
                    return self.fail(
                        "app sign-in", HINTS["token"], f"HTTP {e.response.status_code} AADSTS{codes}"
                    )
                except httpx.HTTPError as e:
                    return self.fail("app sign-in", "Network problem reaching login.microsoftonline.com",
                                     type(e).__name__)  # fmt: skip
            msg = mail.EmailMessage(
                "LearnHub test email", "If you can read this, LearnHub can send email through Microsoft Graph.",
                to=[to],
            )  # fmt: skip
            try:
                sent = backend.send_messages([msg])
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                return self.fail("send", HINTS.get(code, "Graph rejected the message."), f"HTTP {code}")
            except httpx.HTTPError as e:
                return self.fail("send", "Network problem reaching graph.microsoft.com", type(e).__name__)
        if sent == 1:
            self.ok(f"sent to {to} (check the inbox, and junk folder)")
        self.stdout.write("Done.")
