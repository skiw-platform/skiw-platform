"""`manage.py migration_labels` (spec §8.4 H3; plan §3 M1g): from the migration files alone, no
database. Prints one JSON object, every entry "<app label>.<migration name>", sorted:
  head        the leaf migrations (the migration head),
  contracts   the contract migrations: a drop or rename, whose class sets `skiw_contract = True`
              (UNI-15; skiw-deploy refuses a rollback across one),
  migrations  every migration the image ships.
"""

import json
from typing import Any, Protocol

from django.core.management.base import BaseCommand
from django.db import migrations
from django.db.migrations.loader import MigrationLoader

# Operations that drop or rename what an older release may still read: contract only.
CONTRACT_OPERATIONS = (
    migrations.RemoveField,
    migrations.DeleteModel,
    migrations.RenameField,
    migrations.RenameModel,
    migrations.AlterField,
)


class Graph(Protocol):
    def leaf_nodes(self) -> list[tuple[str, str]]: ...


class Loader(Protocol):
    @property
    def disk_migrations(self) -> dict[tuple[str, str], Any]: ...
    @property
    def graph(self) -> Graph: ...


def is_contract(migration: Any) -> bool:
    return getattr(migration, "skiw_contract", False) is True


def needs_flag(migration: Any) -> bool:
    """A migration with a contract operation that does not say so."""
    ops = getattr(migration, "operations", [])
    return any(isinstance(op, CONTRACT_OPERATIONS) for op in ops) and not is_contract(migration)


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

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(json.dumps(labels(), separators=(",", ":")))
