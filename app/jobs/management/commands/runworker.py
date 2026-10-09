from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser

from jobs.startup import require_migrated


class Command(BaseCommand):
    help = "Run the Procrastinate worker, but only against a fully migrated database (spec D16)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("worker_args", nargs="*", help="passed to `procrastinate worker`")

    def handle(self, *args: Any, **options: Any) -> None:
        require_migrated()
        call_command("procrastinate", "worker", *options["worker_args"])
