"""The audit trigger of org_unit on the live schema (plan row M4r-1e, split M4r-1e-ii; slice spec
Decisions 30, 31, 32; accounts.0029). As in test_roles_audit_live: the owner, skiw_migrator, in one
transaction under transaction-local NO FORCE with a test skiw.operator, rolled back. The operator
refusals are in test_roles_audit_live, the trigger set and function properties in
test_roles_guards_live, the pg_proc scan in test_security_event_shape_live. No deferred check
touches org_unit (0027's two are on role and user_role), so its failure case is a statement one:
a tree-guard refusal."""

import importlib
import os
import uuid
from typing import Any

import psycopg
import pytest
from django.db import connection

from accounts.tests.test_org_tables_live import add_root, add_unit
from accounts.tests.test_roles_audit_live import Event, Log, keys, ordered
from accounts.tests.test_roles_guards_live import (
    REFUSED,
    Cursor,
    X,
    Y,
    owner,
    refusal,
    revoke_writes,
)
from accounts.tests.test_roles_tree_owner_live import CYCLE, DEEP, DEPTH, MOVE, UNDER, chain
from tenancy import seed
from tenancy.binding import with_agency
from tenancy.tests.isolation import A, B

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MIGRATION = importlib.import_module("accounts.migrations.0029_org_unit_audit_trigger")
UNITS = "SELECT array_agg(o::text ORDER BY o.id) FROM org_unit o WHERE agency_id = ANY(%s)"
RENAME = "UPDATE org_unit SET name = %s WHERE id = %s"


def added(unit: uuid.UUID, parent: uuid.UUID | None, kind: str) -> Event:
    return (
        "org.added",
        X,
        {**keys(org_unit_id=unit, unit_kind=kind), "parent_id": parent and str(parent)},
    )


def moved(unit: uuid.UUID, old: uuid.UUID, new: uuid.UUID) -> Event:
    return ("org.moved", X, keys(org_unit_id=unit, old_parent_id=old, new_parent_id=new))


def renamed(unit: uuid.UUID) -> Event:
    return ("org.renamed", X, keys(org_unit_id=unit))


def units(cursor: Cursor) -> Any:
    return cursor.execute(UNITS, [[X, Y]]).fetchone()


def test_each_org_change_writes_its_events_with_the_decision_30_keys() -> None:
    """Root (JSON null parent) and child added; move only, rename only, both in one UPDATE (two
    events); no-op UPDATEs, also ones that set the immutable columns to themselves, write none."""
    with owner() as cursor:
        log = Log(cursor, X)
        root = add_root(cursor, X)
        unit = add_unit(cursor, X, root)
        team = add_unit(cursor, X, unit, kind="team")
        assert log.new() == ordered(
            [added(root, None, "agency"), added(unit, root, "unit"), added(team, unit, "team")]
        )
        cursor.execute(MOVE, [root, team])
        assert log.new() == [moved(team, unit, root)]
        cursor.execute(RENAME, ["Renamed", team])
        assert log.new() == [renamed(team)]
        cursor.execute(
            "UPDATE org_unit SET parent_id = %s, name = 'Both' WHERE id = %s", [unit, team]
        )
        assert log.new() == ordered([moved(team, root, unit), renamed(team)])
        for same in (
            "UPDATE org_unit SET name = name WHERE id = %(team)s",
            "UPDATE org_unit SET name = 'Both', parent_id = %(unit)s WHERE id = %(team)s",
            "UPDATE org_unit SET id = id, agency_id = agency_id, kind = kind,"
            " created_at = created_at, name = name WHERE id = %(team)s",
        ):
            cursor.execute(same, {"unit": unit, "team": team})
            assert log.new() == []


def test_a_multi_row_update_writes_one_event_per_row_and_per_field() -> None:
    with owner() as cursor:
        root = add_root(cursor, X)
        a, b, c, d = (add_unit(cursor, X, root) for _ in range(4))
        log = Log(cursor, X)
        log.new()
        cursor.execute(
            "UPDATE org_unit SET parent_id = CASE id WHEN %(c)s THEN parent_id ELSE %(d)s END,"
            " name = CASE id WHEN %(b)s THEN name ELSE 'M' END WHERE id IN (%(a)s, %(b)s, %(c)s)",
            {"a": a, "b": b, "c": c, "d": d},
        )
        expected = [moved(a, root, d), moved(b, root, d), renamed(a), renamed(c)]
        assert log.new() == ordered(expected)


IMMUTABLE = {
    "id": "UPDATE org_unit SET id = gen_random_uuid() WHERE id = %(leaf)s",
    # the new parent must be in agency Y, or the FK refuses first
    "agency_id": "UPDATE org_unit SET agency_id = %(y)s, parent_id = %(other)s WHERE id = %(leaf)s",
    "kind": "UPDATE org_unit SET kind = 'team' WHERE id = %(leaf)s",
    "created_at": "UPDATE org_unit SET created_at = created_at - interval '1 day'"
    " WHERE id = %(leaf)s",
    "kind-and-name": "UPDATE org_unit SET kind = 'team', name = 'New' WHERE id = %(leaf)s",
}


@pytest.mark.parametrize("column", IMMUTABLE)
def test_an_update_of_an_immutable_column_is_refused_with_nothing_written(column: str) -> None:
    with owner() as cursor:
        leaf = add_unit(cursor, X, add_root(cursor, X))
        params = {"leaf": leaf, "y": Y, "other": add_root(cursor, Y)}
        log, before = Log(cursor, X, Y), units(cursor)
        log.new()
        assert refusal(cursor, IMMUTABLE[column], params) == REFUSED
        assert units(cursor) == before and log.new() == []


TREE_REFUSALS = {"cycle": (MOVE, -1, CYCLE), "depth-33": (UNDER, None, DEEP)}


@pytest.mark.parametrize("case", TREE_REFUSALS)
def test_a_tree_guard_refusal_writes_no_event_and_changes_nothing(case: str) -> None:
    sql, moved_unit, error = TREE_REFUSALS[case]
    with owner() as cursor:
        path = chain(cursor, X, DEPTH)
        log, before = Log(cursor, X), units(cursor)
        log.new()
        params = [path[-1], path[1]] if moved_unit else [X, path[-1]]  # path[1] under its leaf
        assert refusal(cursor, sql, params) == error
        assert units(cursor) == before and log.new() == []


def test_a_change_and_its_events_roll_back_together() -> None:
    with owner() as cursor:
        root = add_root(cursor, X)
        log, before = Log(cursor, X), units(cursor)
        log.new()
        with pytest.raises(RuntimeError), cursor.connection.transaction():
            add_unit(cursor, X, root)
            cursor.execute(RENAME, ["Gone", root])
            assert sorted(k for k, _, _ in log.new()) == ["org.added", "org.renamed"]
            raise RuntimeError("before commit")
        log.seen.clear()
        assert units(cursor) == before and log.new() == [
            ("org.added", X, added(root, None, "agency")[2])
        ]


def test_the_event_carries_the_rows_agency_and_only_that_agency_sees_it() -> None:
    """A unit of A committed by the owner under A's root (made if missing, kept: the TEN-08 harness
    does the same), FORCE back on before the commit; read as skiw_app."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT set_config('skiw.operator', 'test-operator', true)")
        seed.insert_agency(cursor, A, "Agency A")
        seed.insert_agency(cursor, B, "Agency B")
        for table in ("org_unit", "security_event"):
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        cursor.execute(
            "INSERT INTO org_unit (id, agency_id, kind, name) VALUES (gen_random_uuid(), %s,"
            " 'agency', 'Isolation agency') ON CONFLICT DO NOTHING",
            [A],
        )
        row = cursor.execute(
            "SELECT id FROM org_unit WHERE agency_id = %s AND parent_id IS NULL", [A]
        ).fetchone()
        assert row is not None
        unit = add_unit(cursor, A, row[0], name="Audit unit")
        for table in ("org_unit", "security_event"):
            cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    seen: dict[str, list[tuple[Any, ...]]] = {}
    for context, agency in {"A": A, "B": B}.items():
        with with_agency(agency), connection.cursor() as app:
            app.execute(
                "SELECT kind, agency_id FROM security_event"
                " WHERE details_json ->> 'org_unit_id' = %s",
                [str(unit)],
            )
            seen[context] = app.fetchall()
    assert seen == {"A": [("org.added", A)], "B": []}


def test_the_reverse_refuses_with_a_write_grant_and_otherwise_drops_the_audit_trigger() -> None:
    assert MIGRATION.REVERSE[0] == MIGRATION.LOCKS.GUARD  # the 0026 guard, the same statement
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)  # accounts.0030's grants, so the one below is what the guard sees
        cursor.execute("GRANT UPDATE ON org_unit TO skiw_app")
        assert refusal(cursor, MIGRATION.REVERSE[0])[0] == "55000"
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)
        for statement in MIGRATION.REVERSE:
            cursor.execute(statement)
        left = cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname = 'org_unit_audit'")
        assert left.fetchone() == (0,)
        assert cursor.execute("SELECT to_regprocedure(%s)", [MIGRATION.FUNCTION]).fetchone() == (
            None,
        )
