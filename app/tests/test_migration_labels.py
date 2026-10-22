"""`migration_labels` (plan §3 M1g, UNI-15): head and contract list from the migration files."""

import json
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar

from django.apps import apps
from django.core.management import call_command
from django.db import migrations
from django.db.migrations.loader import MigrationLoader

from config.management.commands.migration_labels import labels, needs_flag

APP_DIR = Path(__file__).resolve().parents[1]


def test_prints_head_contracts_and_migrations_without_a_database() -> None:
    out = StringIO()
    call_command("migration_labels", stdout=out)  # no django_db mark: no database access
    found = json.loads(out.getvalue())
    assert set(found) == {"head", "contracts", "migrations"}
    assert "jobs.0001_procrastinate_queue_grants" in found["head"]
    assert set(found["head"]) <= set(found["migrations"]) and found["contracts"] == []


def test_every_own_migration_with_a_drop_or_rename_is_flagged_as_contract() -> None:
    own = {c.label for c in apps.get_app_configs() if Path(c.path).is_relative_to(APP_DIR)}
    loader = MigrationLoader(None, ignore_no_migrations=True)
    bad = [key for key, m in loader.disk_migrations.items() if key[0] in own and needs_flag(m)]
    assert bad == []


class Drop(migrations.Migration):
    operations: ClassVar = [migrations.RemoveField("thing", "old")]


class FlaggedDrop(Drop):
    skiw_contract = True


class Add(migrations.Migration):
    operations: ClassVar = [migrations.RunSQL("SELECT 1", migrations.RunSQL.noop)]


def test_the_flag_rule_and_the_contract_list_on_fixture_migrations() -> None:
    assert needs_flag(Drop("0002_drop", "x")) and not needs_flag(FlaggedDrop("0002_drop", "x"))
    assert not needs_flag(Add("0001_add", "x"))

    class Graph:
        def leaf_nodes(self) -> list[tuple[str, str]]:
            return [("x", "0002_drop")]

    class Loader:
        def __init__(self) -> None:
            self.disk_migrations: dict[tuple[str, str], Any] = {
                ("x", "0001_add"): Add("0001_add", "x"),
                ("x", "0002_drop"): FlaggedDrop("0002_drop", "x"),
            }
            self.graph = Graph()

    assert labels(Loader()) == {
        "head": ["x.0002_drop"],
        "contracts": ["x.0002_drop"],
        "migrations": ["x.0001_add", "x.0002_drop"],
    }
