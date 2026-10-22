"""`migration_labels` (plan §3 M1g, UNI-15): head and contract list from the migration files."""

import json
from io import StringIO
from pathlib import Path
from typing import ClassVar

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import migrations, models
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.base import Operation

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
            self.disk_migrations: dict[tuple[str, str], migrations.Migration] = {
                ("x", "0001_add"): Add("0001_add", "x"),
                ("x", "0002_drop"): FlaggedDrop("0002_drop", "x"),
            }
            self.graph = Graph()

    assert labels(Loader()) == {
        "head": ["x.0002_drop"],
        "contracts": ["x.0002_drop"],
        "migrations": ["x.0001_add", "x.0002_drop"],
    }


# The five contract operations, each built as an own migration would write it.
CONTRACT = {
    "RemoveField": migrations.RemoveField("thing", "old"),
    "DeleteModel": migrations.DeleteModel("Thing"),
    "RenameField": migrations.RenameField("thing", "old", "new"),
    "RenameModel": migrations.RenameModel("Thing", "Item"),
    "AlterField": migrations.AlterField("thing", "name", models.TextField()),
}


def migration(ops: list[Operation], flagged: bool) -> migrations.Migration:
    """A migration class as an own app writes it; the UNI-15 marker is a class attribute."""
    body: dict[str, object] = {"operations": ops} | ({"skiw_contract": True} if flagged else {})
    case: type[migrations.Migration] = type("Case", (migrations.Migration,), body)
    return case("0003_case", "x")


def wrapped(op: Operation) -> Operation:
    """The database runs `op`; the state sees nothing."""
    return migrations.SeparateDatabaseAndState(database_operations=[op], state_operations=[])


@pytest.mark.parametrize("name", sorted(CONTRACT))
@pytest.mark.parametrize("wrap", [False, True], ids=["direct", "in-database-operations"])
def test_a_contract_operation_needs_the_flag_direct_or_wrapped(name: str, wrap: bool) -> None:
    op = wrapped(wrapped(CONTRACT[name])) if wrap else CONTRACT[name]
    assert needs_flag(migration([op], flagged=False))
    flagged = migration([op], flagged=True)
    assert not needs_flag(flagged)

    class Loader:
        def __init__(self) -> None:
            self.disk_migrations = {("x", "0003_case"): flagged}
            self.graph = type("G", (), {"leaf_nodes": lambda _: [("x", "0003_case")]})()

    assert labels(Loader())["contracts"] == ["x.0003_case"]


def test_state_only_and_safe_wrapped_operations_need_no_flag() -> None:
    state_only = migrations.SeparateDatabaseAndState(state_operations=[CONTRACT["RemoveField"]])
    safe = wrapped(migrations.AddField("thing", "new", models.TextField(null=True)))
    assert not needs_flag(migration([state_only, safe], flagged=False))


class Custom(Operation):
    """An operation class Django does not define: the guard cannot see what it runs."""

    def state_forwards(self, app_label: str, state: object) -> None:
        pass


def test_an_unknown_operation_class_needs_the_flag_even_when_wrapped() -> None:
    assert needs_flag(migration([Custom()], flagged=False))
    assert needs_flag(migration([wrapped(Custom())], flagged=False))
    assert not needs_flag(migration([wrapped(Custom())], flagged=True))
