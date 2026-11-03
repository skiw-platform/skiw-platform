from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser

from jobs.startup import require_migrated
from tenancy.binding import require_token_key


class Command(BaseCommand):
    help = "Run the Procrastinate worker, but only against a fully migrated database (spec D16)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("worker_args", nargs="*", help="passed to `procrastinate worker`")

    def handle(self, *args: Any, **options: Any) -> None:
        # Fail closed on a missing or malformed tenant_source_key or login_blob_key, as
        # config.asgi does for web (plan M3 (j), M3b); through settings, so jobs imports no
        # accounts. tenant_token_key through tenancy.binding, which caches it (plan M4c-4b).
        settings.SKIW_TENANT_SOURCE_KEYS()
        settings.SKIW_LOGIN_BLOB_KEYS()
        require_token_key()
        require_migrated()
        call_command("procrastinate", "worker", *options["worker_args"])
