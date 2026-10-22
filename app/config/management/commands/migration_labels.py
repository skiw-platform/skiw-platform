"""`manage.py migration_labels` (spec §8.4 H3; plan §3 M1g): from the migration files alone, no
database. Prints one JSON object, every entry "<app label>.<migration name>", sorted:
  head        the leaf migrations (the migration head),
  contracts   the contract migrations: a drop or rename, whose class sets `skiw_contract = True`
              (UNI-15; skiw-deploy refuses a rollback across one),
  migrations  every migration the image ships.

The contract-flag guard (`needs_flag`) looks at the operations a migration runs against the
database: top-level operations and, recursively, `SeparateDatabaseAndState.database_operations`.
Its `state_operations` only change Django's model state and run no SQL, so they are not inspected.
An operation class that Django does not define (a project or third-party Operation) counts as a
contract operation: the guard cannot see what it does, so it needs the flag (fail closed). Raw SQL
in `RunSQL` / `RunPython` is not parsed; a drop written that way is caught only by review.
"""

import json
from collections.abc import Iterable, Iterator
from typing import Any, Protocol

from django.core.management.base import BaseCommand
from django.db import migrations
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.base import Operation

# Operations that drop or rename what an older release may still read: contract only.
CONTRACT_OPERATIONS = (
    migrations.RemoveField,
    migrations.DeleteModel,
    migrations.RenameField,
    migrations.RenameModel,
    migrations.AlterField,
)
# Where Django's own operation classes live; any other class is unknown to the guard.
DJANGO_OPERATIONS = ("django.db.migrations.operations.", "django.contrib.postgres.operations")


class Graph(Protocol):
    def leaf_nodes(self) -> list[tuple[str, str]]: ...


class Loader(Protocol):
    @property
    def disk_migrations(self) -> dict[tuple[str, str], migrations.Migration]: ...
    @property
    def graph(self) -> Graph: ...


def is_contract(migration: migrations.Migration) -> bool:
    return getattr(migration, "skiw_contract", False) is True


def database_operations(operations: Iterable[Operation]) -> Iterator[Operation]:
    """The operations that run against the database, through SeparateDatabaseAndState."""
    for op in operations:
        if isinstance(op, migrations.SeparateDatabaseAndState):
            yield from database_operations(op.database_operations)
        else:
            yield op


def is_contract_operation(op: Operation) -> bool:
    unknown = not type(op).__module__.startswith(DJANGO_OPERATIONS)
    return unknown or isinstance(op, CONTRACT_OPERATIONS)


def needs_flag(migration: migrations.Migration) -> bool:
    """A migration that runs a contract operation and does not say so."""
    ops = database_operations(migration.operations)
    return any(is_contract_operation(op) for op in ops) and not is_contract(migration)


def labels(loader: Loader | None = None) -> dict[str, list[str]]:
    found: Loader = loader or MigrationLoader(None, ignore_no_migrations=True)
    disk = found.disk_migrations
    return {
        "head": sorted(f"{app}.{name}" for app, name in found.graph.leaf_nodes()),
        "contracts": sorted(f"{a}.{n}" for (a, n), m in disk.items() if is_contract(m)),
        "migrations": sorted(f"{app}.{name}" for app, name in disk),
    }


class Command(BaseCommand):
    help = "Print the migration head, the contract migrations and every migration (no database)."

    # BaseCommand's own signature: Django passes parsed options of any type; none are read here.
    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(json.dumps(labels(), separators=(",", ":")))
