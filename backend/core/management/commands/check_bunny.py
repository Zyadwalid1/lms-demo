"""python manage.py check_bunny: live check of the Bunny Stream setup.

Checks the settings, the library row in the database, the API key, creates and deletes
one empty test video, and signs an upload and a playback link. Never prints keys.
Use --fix-library to point the default library row at BUNNY_STREAM_LIBRARY_ID.
"""

import logging
import re
import time

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalog import bunny, media
from apps.catalog.models import MediaAsset, VideoLibrary
from core.tenancy import tenant_context

HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.I)


class Command(BaseCommand):
    help = "Live check of Bunny Stream: keys, library, upload signature and signed playback."

    def add_arguments(self, parser):
        parser.add_argument("--fix-library", action="store_true", help="update the default library row")

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  PASS  {msg}"))

    def warn(self, msg, hint=""):
        self.stdout.write(self.style.WARNING(f"  NOTE  {msg}"))
        if hint:
            self.stdout.write(f"        -> {hint}")

    def fail(self, msg, hint, detail=""):
        self.stdout.write(self.style.ERROR(f"  FAIL  {msg}{f' ({detail})' if detail else ''}"))
        self.stdout.write(f"        -> {hint}")

    def handle(self, *args, fix_library, **opts):
        logging.getLogger("httpx").setLevel(logging.WARNING)
        cfg = settings.BUNNY_STREAM
        self.stdout.write("Bunny Stream check")
        if not str(cfg["LIBRARY_ID"]).isdigit():
            raise CommandError(
                "BUNNY_STREAM_LIBRARY_ID must be the library's number (Stream > library > API)."
            )
        if not cfg["API_KEY"]:
            raise CommandError("BUNNY_STREAM_API_KEY is empty (Stream > library > API > API Key).")
        lib_id = int(cfg["LIBRARY_ID"])
        self.ok(f"library id {lib_id} and API key present")
        if not cfg["TOKEN_KEY"]:
            self.warn("BUNNY_STREAM_TOKEN_KEY is empty: playback links will not be signed",
                      "Stream > library > Security > Token authentication key")  # fmt: skip
        if not cfg["CDN_HOST"] or not HOST.match(cfg["CDN_HOST"]):
            self.warn("BUNNY_STREAM_CDN_HOST is empty or not a hostname",
                      "Stream > library > API > CDN hostname, e.g. vz-xxxx.b-cdn.net")  # fmt: skip
        ro = cfg["READONLY_KEY"]
        if not ro or HOST.match(ro):
            self.warn("BUNNY_STREAM_READONLY_KEY is empty or holds a hostname (webhooks would be refused)",
                      "use the library's Read-only API key; the vz-....b-cdn.net value belongs in CDN_HOST")  # fmt: skip

        with tenant_context(staff=True):
            library = VideoLibrary.objects.filter(is_default=True).first()
            if library is None:
                return self.fail("library row", "No default video library: run seed_demo first.")
            if library.bunny_library_id != lib_id or (
                cfg["CDN_HOST"] and library.cdn_hostname != cfg["CDN_HOST"]
            ):
                if fix_library:
                    VideoLibrary.objects.filter(pk=library.pk).update(
                        bunny_library_id=lib_id, cdn_hostname=cfg["CDN_HOST"] or library.cdn_hostname
                    )
                    library.refresh_from_db()
                    self.ok("default library row updated to match .env")
                else:
                    what = "library id" if library.bunny_library_id != lib_id else "CDN hostname"
                    return self.fail("library row", "The default library in the database differs from .env: "
                                     "run again with --fix-library", f"{what} differs")  # fmt: skip
            else:
                self.ok("default library row matches .env")

        with httpx.Client(timeout=15) as client:
            r = client.get(f"{bunny.API}/library/{lib_id}/videos", params={"page": 1, "itemsPerPage": 1},
                           headers={"AccessKey": cfg["API_KEY"], "accept": "application/json"})  # fmt: skip
        if r.status_code != 200:
            return self.fail("API key", "Use the library's API key (Stream > library > API), not the account key.",
                             f"HTTP {r.status_code}")  # fmt: skip
        self.ok("API key accepted by the library")

        guid = None
        try:
            guid = bunny.create_video(library, "LearnHub check (safe to delete)")
            self.ok("test video created")
            session = bunny.upload_session(library, guid)
            if len(session["headers"]["AuthorizationSignature"]) == 64 and cfg["API_KEY"] not in str(session):
                self.ok("upload signature made for that one video (the key itself stays on the server)")
            fake = MediaAsset(bunny_video_guid=guid, library=library, duration_sec=0)
            play = media.playback(fake)
            signed = "token=" in (play["url"] or "")
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                page = client.get(play["url"])
            if signed:
                self.ok(f"signed playback link works (HTTP {page.status_code})" if page.status_code < 400
                        else f"signed playback link made (HTTP {page.status_code})")  # fmt: skip
            else:
                self.warn("playback link is not signed (no token key)")
        except Exception as exc:  # noqa: BLE001 - report plainly
            self.fail("test video", "Check the API key and library id.", type(exc).__name__)
        finally:
            if guid:
                time.sleep(1)
                bunny.delete_video(library, guid)
                self.ok("test video deleted")
        self.warn("webhooks need a public URL: after deployment set Stream > library > Webhook URL to "
                  "https://<your-domain>/api/v1/platform/webhooks/bunny")  # fmt: skip
        self.stdout.write("Done.")
