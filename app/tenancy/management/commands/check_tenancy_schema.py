"""`manage.py check_tenancy_schema` (plan M4c-6b): `tenancy.check.check()` on the default database.
Runs last in the migrate step (`make migrate`, `skiw-deploy` after `migrate`), so a bad schema
fails CI and stops a deploy before the switch. Prints each violation as `<table>: <reason>`, never
data."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from tenancy.check import check


class Command(BaseCommand):
    help = "Fail if any table is not a listed global, the agency root or a compliant tenant table."

    def handle(self, *args: Any, **options: Any) -> None:
        connection.ensure_connection()
        violations = check(connection.connection)
        for violation in violations:
            self.stderr.write(str(violation))
        if violations:
            raise CommandError(f"tenancy schema check: {len(violations)} violations")
        self.stdout.write("tenancy schema check: ok")
