"""Email through Microsoft Graph (the Azure no-reply sender, as in Communication Centre).

    MAIL_MODE=console   print emails to the log (default: nothing leaves the machine)
    MAIL_MODE=graph     send with Graph: POST /users/{MICROSOFT_GRAPH_SENDER}/sendMail, using an app
                        registration with the Mail.Send application permission
                        (client-credentials token, cached until 5 minutes before expiry)

MAIL_ALLOWED_DOMAINS (comma-separated, e.g. "kentbusinesscollege.com,example.com") is a
safety switch for demos and staging: recipients outside these domains are dropped and
logged, so seeded or test data can never email a real customer by accident. Leave it
empty in production to allow everyone.

Settings use the Communication Centre names (MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID,
MICROSOFT_CLIENT_SECRET, MICROSOFT_GRAPH_SCOPE, MICROSOFT_GRAPH_BASE_URL). Secrets come from the environment only.
"""

import logging

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)
TOKEN_CACHE_KEY = "mail:graph:token"  # noqa: S105 - a cache key name, not a secret


def allowed(address: str) -> bool:
    domains = settings.MAIL_ALLOWED_DOMAINS
    if not domains:
        return True
    return address.rsplit("@", 1)[-1].lower() in domains


class GraphEmailBackend(BaseEmailBackend):
    transport = None  # tests inject an httpx.MockTransport

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=20, transport=self.transport)

    def _token(self, client: httpx.Client) -> str:
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        r = client.post(
            f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": settings.GRAPH_CLIENT_ID,
                "client_secret": settings.GRAPH_CLIENT_SECRET,
                "scope": settings.GRAPH_SCOPE,
                "grant_type": "client_credentials",
            },
        )
        r.raise_for_status()
        body = r.json()
        cache.set(
            TOKEN_CACHE_KEY, body["access_token"], timeout=max(60, int(body.get("expires_in", 3600)) - 300)
        )
        return body["access_token"]

    def _payload(self, message, recipients: list[str]) -> dict:
        html_body = next((c for c, mime in getattr(message, "alternatives", []) if mime == "text/html"), None)
        return {
            "message": {
                "subject": message.subject,
                "body": {
                    "contentType": "HTML" if html_body else "Text",
                    "content": html_body or message.body,
                },
                "toRecipients": [{"emailAddress": {"address": a}} for a in recipients],
                **(
                    {"replyTo": [{"emailAddress": {"address": a}} for a in message.reply_to]}
                    if message.reply_to
                    else {}
                ),
            },
            "saveToSentItems": False,
        }

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0
        sent = 0
        with self._client() as client:
            token = None
            for message in email_messages:
                recipients = [a for a in message.recipients() if allowed(a)]
                dropped = set(message.recipients()) - set(recipients)
                if dropped:
                    log.warning("mail: %d recipient(s) outside MAIL_ALLOWED_DOMAINS dropped", len(dropped))
                if not recipients:
                    continue
                try:
                    token = token or self._token(client)
                    r = client.post(
                        f"{settings.GRAPH_BASE_URL}/users/{settings.GRAPH_SENDER}/sendMail",
                        headers={"Authorization": f"Bearer {token}"},
                        json=self._payload(message, recipients),
                    )
                    if r.status_code == 401:  # token revoked or expired early: one fresh retry
                        cache.delete(TOKEN_CACHE_KEY)
                        token = self._token(client)
                        r = client.post(
                            f"{settings.GRAPH_BASE_URL}/users/{settings.GRAPH_SENDER}/sendMail",
                            headers={"Authorization": f"Bearer {token}"},
                            json=self._payload(message, recipients),
                        )
                    r.raise_for_status()
                    sent += 1
                except httpx.HTTPError:
                    log.exception("mail: Graph sendMail failed")
                    if not self.fail_silently:
                        raise
        return sent


class SafeConsoleBackend(BaseEmailBackend):
    """MAIL_MODE=console: logs subject and recipients only (never message bodies, which
    can contain sign-in links)."""

    def send_messages(self, email_messages) -> int:
        for m in email_messages:
            log.info("mail (console): to=%s subject=%r", [a for a in m.recipients() if allowed(a)], m.subject)
        return len(email_messages)
