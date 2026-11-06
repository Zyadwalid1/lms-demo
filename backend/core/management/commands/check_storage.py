"""python manage.py check_storage: a live end-to-end check of the Azure Blob setup.

Prints pass/fail per step and a hint for each failure. Never prints secrets.
It uploads, reads and deletes one small test file.
"""

import logging
import re
import uuid

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import override_settings

from core import storage

GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HINTS = {
    "token": "Check AZURE_STORAGE_TENANT_ID, CLIENT_ID and CLIENT_SECRET (the secret's Value, not its Secret ID; "
    "not expired).",
    "delegation": "The app needs the 'Storage Blob Data Contributor' role assigned on the STORAGE ACCOUNT "
    "(not on a container), to this app; new roles can take ~5-10 minutes to apply.",
    "upload": "Check AZURE_STORAGE_CONTAINER matches the container name exactly, and the role above.",
    "cors": "Storage account > Resource sharing (CORS) > Blob service: allow origin {origin}, "
    "methods GET,HEAD,PUT,OPTIONS, headers *.",
}


class Command(BaseCommand):
    help = "Live check of Azure Blob storage: sign-in, role, container, signed links, CORS."

    def add_arguments(self, parser):
        parser.add_argument("--origin", default="http://localhost:5173")

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  PASS  {msg}"))

    def fail(self, msg, hint, detail=""):
        self.stdout.write(self.style.ERROR(f"  FAIL  {msg}{f' ({detail})' if detail else ''}"))
        self.stdout.write(f"        -> {hint}")

    def handle(self, *args, origin, **opts):
        logging.getLogger("httpx").setLevel(logging.WARNING)  # signed URLs must not reach the log
        # A private in-memory cache: the check works without Redis and never reuses old tokens.
        with override_settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        ):
            self.run(origin)

    def run(self, origin):
        cfg = settings.AZURE_STORAGE
        self.stdout.write("Azure Blob storage check")
        names = {"ACCOUNT": "ACCOUNT_NAME", "CONTAINER": "CONTAINER", "TENANT_ID": "TENANT_ID",
                 "CLIENT_ID": "CLIENT_ID", "CLIENT_SECRET": "CLIENT_SECRET"}  # fmt: skip
        missing = [f"AZURE_STORAGE_{v}" for k, v in names.items() if not cfg.get(k)]
        if missing:
            return self.fail("settings", "Fill these in backend/.env: " + ", ".join(missing))
        self.ok(f"settings present (account {cfg['ACCOUNT']}, container {cfg['CONTAINER']})")
        if GUID.match(cfg["CLIENT_SECRET"]):
            self.fail("client secret looks like a Secret ID (a GUID)", HINTS["token"])

        with storage.client() as http:
            try:
                storage.token(http)
                self.ok("app sign-in (Entra client credentials)")
            except httpx.HTTPStatusError as e:
                code = e.response.json().get("error_codes", [""])[0] if e.response.content else ""
                return self.fail("app sign-in", HINTS["token"], f"HTTP {e.response.status_code} AADSTS{code}")
            except httpx.HTTPError as e:
                return self.fail(
                    "app sign-in", "Network problem reaching login.microsoftonline.com", type(e).__name__
                )
            try:
                storage._delegation_key(http)
                self.ok("role on storage account (user delegation key)")
            except httpx.HTTPError as e:
                status = getattr(getattr(e, "response", None), "status_code", type(e).__name__)
                return self.fail("role on storage account", HINTS["delegation"], f"HTTP {status}")

            path = f"_healthcheck/{uuid.uuid4()}.txt"
            data = b"learnhub storage check"
            r = http.put(storage.upload_url(path), content=data,
                         headers={"x-ms-blob-type": "BlockBlob", "Content-Type": "text/plain"})  # fmt: skip
            if r.status_code != 201:
                err = r.headers.get("x-ms-error-code", "")
                return self.fail("upload with signed link", HINTS["upload"], f"HTTP {r.status_code} {err}")
            self.ok("upload with signed link (15 min, write-only)")
            r = http.get(storage.download_url(path, "check.txt"))
            if r.status_code == 200 and r.content == data:
                self.ok("download with signed link (1 hour, read-only)")
            else:
                self.fail("download with signed link", HINTS["upload"], f"HTTP {r.status_code}")
            r = http.get(storage.blob_url(path))
            if r.status_code in (401, 403, 404, 409):
                self.ok("container is private (no anonymous access)")
            else:
                self.fail(
                    "container is private",
                    "Set the container access level to Private",
                    f"HTTP {r.status_code}",
                )
            r = http.options(storage.blob_url(path), headers={
                "Origin": origin, "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "x-ms-blob-type,content-type"})  # fmt: skip
            if r.status_code == 200 and r.headers.get("access-control-allow-origin") in (origin, "*"):
                self.ok(f"CORS allows browser uploads from {origin}")
            else:
                self.fail("CORS", HINTS["cors"].format(origin=origin), f"HTTP {r.status_code}")
            try:
                storage.delete(path)
                self.ok("delete (cleanup)")
            except httpx.HTTPError as e:
                self.fail("delete", HINTS["delegation"], type(e).__name__)
        self.stdout.write("Done.")
