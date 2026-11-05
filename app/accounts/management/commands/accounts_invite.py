"""`manage.py accounts_invite <email> --name <display name>` (spec AUTH-08; plan M3 §3 M3e, owner Q5
(a)). The operator runs it with `compose exec` in the running `web` container (`host-rebuild.md`,
"Enrol a user"; a `compose run` container's output would reach journald). It prints one
enrolment link and nothing else; a refusal exits 1 with a reason that names no other account."""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from accounts.auth import enrol

PATH = "/enrol"  # the SPA's enrolment page (M3i); the token is in the fragment


class Command(BaseCommand):
    help = "Invite a user of the deployment agency: print a single-use enrolment link."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email")
        parser.add_argument("--name", required=True, help="the user's display name")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            token = enrol.invite(options["email"], options["name"])
        except enrol.Refused as error:
            raise CommandError(str(error)) from error
        host = settings.ALLOWED_HOSTS[0]
        minutes = settings.SKIW_ENROL_LINK_MIN
        self.stdout.write(f"https://{host}{PATH}#{token}")
        self.stderr.write(f"Single use, valid for {minutes} minutes. Send it to the user only.")
