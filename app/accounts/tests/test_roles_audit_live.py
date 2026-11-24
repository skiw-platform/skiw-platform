"""The audit triggers of role, role_permission and user_role on the live schema (plan row M4r-1e,
split M4r-1e-i; slice spec Decisions 30, 31, 32; accounts.0028). As in test_roles_guards_live: the
owner, skiw_migrator, in one transaction under transaction-local NO FORCE with a test
skiw.operator, rolled back; skiw_app has no write grant until M4r-1g. The trigger set, the function
properties and the grant audit are in test_roles_guards_live and test_access_tables_live, the
pg_proc scan in test_security_event_shape_live; org_unit_audit (M4r-1e-ii, accounts.0029) is in
test_org_audit_live, except its operator refusals, which are here with the other tables'."""

import importlib
import json
import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from django.db import connection, transaction

from accounts.access.catalogue import PAIRS
from accounts.tests.test_access_tables_live import add_role
from accounts.tests.test_org_tables_live import add_unit, assign, assignment
from accounts.tests.test_roles_guards_live import (
    LIFTED,
    Cursor,
    X,
    owner,
    refusal,
    revoke_writes,
    tick,
)
from accounts.tests.test_roles_tree_owner_live import (
    EVERY_PAIR,
    INCOMPLETE,
    NO_HOLDER,
    commit_refusal,
    incomplete_owner,
    last_owner_removed,
)
from tenancy import seed
from tenancy.binding import with_agency
from tenancy.tests.isolation import A, B

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MIGRATION = importlib.import_module("accounts.migrations.0028_role_audit_triggers")
OPERATOR = "test-operator"  # set by owner()
NO_OPERATOR = ("22023", "roles change refused: skiw.operator is missing or malformed")
EVENTS = "SELECT id, kind, agency_id, details_json FROM security_event WHERE agency_id = ANY(%s)"
AUDITS = [f"{t}_audit" for t in MIGRATION.AUDITS]
AUDITED = (*MIGRATION.AUDITS, "org_unit")  # 0028's three tables and accounts.0029's org_unit
type Event = tuple[str, uuid.UUID, dict[str, Any]]


class Log:
    """The change events of the given agencies that are new since the last call."""

    def __init__(self, cursor: Cursor, *agencies: uuid.UUID) -> None:
        self.cursor, self.agencies, self.seen = cursor, list(agencies), set[Any]()

    def new(self) -> list[Event]:
        rows = self.cursor.execute(EVENTS, [self.agencies]).fetchall()
        fresh = [row for row in rows if row[0] not in self.seen]
        self.seen.update(row[0] for row in fresh)
        return ordered([(k, a, d) for _, k, a, d in fresh])


def ordered(events: list[Event]) -> list[Event]:
    """Sorted independently of the key order of each details dict."""
    return sorted(events, key=lambda event: json.dumps(event, sort_keys=True, default=str))


def keys(**values: object) -> dict[str, Any]:
    return {"operator": OPERATOR, **{key: str(value) for key, value in values.items()}}


def root_of(cursor: Cursor, agency: uuid.UUID) -> uuid.UUID:
    row = cursor.execute(
        "SELECT id FROM org_unit WHERE agency_id = %s AND parent_id IS NULL", [agency]
    ).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def test_each_change_writes_one_event_with_its_decision_30_keys() -> None:
    """The seven kinds of this PR, each with exactly its keys, the row's agency and the operator;
    every event passed security_event_shape. A name-unchanged UPDATE writes none."""
    with owner() as cursor:
        log = Log(cursor, X)
        ids = assignment(cursor, X)  # also a root and a unit (org.added: test_org_audit_live)
        role, root, unit = ids["role_id"], root_of(cursor, X), ids["org_unit_id"]
        assert log.new() == ordered(
            [
                ("role.created", X, keys(role_id=role)),
                ("org.added", X, {**keys(org_unit_id=root, unit_kind="agency"), "parent_id": None}),
                ("org.added", X, keys(org_unit_id=unit, parent_id=root, unit_kind="unit")),
            ]
        )
        assign(cursor, X, ids, "investment")
        row = cursor.execute("SELECT id FROM user_role WHERE role_id = %s", [role]).fetchone()
        assert row is not None
        assignment_keys = keys(user_role_id=row[0], **ids, line="investment")
        assert log.new() == [("role.assigned", X, assignment_keys)]
        role_tick = tick(cursor, X, role)
        tick_keys = keys(role_permission_id=role_tick, role_id=role, permission_code="client.view")
        assert log.new() == [("permission.set", X, {**tick_keys, "scope": "own"})]
        cursor.execute("UPDATE role SET name = 'Renamed' WHERE id = %s", [role])
        assert log.new() == [("role.renamed", X, keys(role_id=role))]
        for same in ("UPDATE role SET name = name", "UPDATE role SET name = 'Renamed'"):
            cursor.execute(f"{same} WHERE id = %s", [role])  # no change of name: no event
            assert log.new() == []
        cursor.execute("DELETE FROM role_permission WHERE id = %s", [role_tick])
        assert log.new() == [("permission.unset", X, {**tick_keys, "scope": "own"})]
        cursor.execute("DELETE FROM user_role WHERE role_id = %s", [role])
        assert log.new() == [("role.unassigned", X, assignment_keys)]
        cursor.execute("DELETE FROM role WHERE id = %s", [role])
        assert log.new() == [("role.deleted", X, keys(role_id=role))]


def test_a_multi_row_statement_writes_one_event_per_row() -> None:
    with owner() as cursor:
        log = Log(cursor, X)
        role = add_role(cursor, "Many", agency=X)
        cursor.execute(EVERY_PAIR, [X, role])
        cursor.execute("UPDATE role SET name = 'Many renamed' WHERE agency_id = %s", [X])
        ticks = cursor.execute("SELECT id FROM role_permission WHERE role_id = %s", [role])
        expected = {str(tick_id) for (tick_id,) in ticks.fetchall()}
        cursor.execute("DELETE FROM role_permission WHERE role_id = %s", [role])
        events = log.new()
        assert len(expected) == len(PAIRS)
        for kind in ("permission.set", "permission.unset"):
            written = [d["role_permission_id"] for k, _, d in events if k == kind]
            assert sorted(written) == sorted(expected)
        assert [k for k, _, _ in events if k.startswith("role.")] == [
            "role.created",
            "role.renamed",
        ]


BAD_OPERATORS = {
    "never-set": None,
    "ended-earlier": "",  # set in an earlier transaction of this session: '' afterwards
    "empty": "",
    "capitals": "Bob",
    "33-characters": "a" * 33,
    "one-character": "a",
    "comma": "ops,1",
    "digit-first": "1ops",
    "trailing-newline": "ops-1\n",
}
REFUSED_WRITES = {
    "role insert": "INSERT INTO role (id, agency_id, name) VALUES (gen_random_uuid(), %(a)s, 'N')",
    "role rename": "UPDATE role SET name = 'New' WHERE id = %(r)s",
    "role no-op update": "UPDATE role SET name = name WHERE id = %(r)s",
    "role delete": "DELETE FROM role WHERE id = %(spare)s",
    "tick": "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (gen_random_uuid(), %(a)s, %(r)s, 'client.edit', 'own')",
    "untick": "DELETE FROM role_permission WHERE role_id = %(r)s",
    "assign": "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (gen_random_uuid(), %(a)s, %(user_id)s, %(spare)s, %(org_unit_id)s, 'both')",
    "unassign": "DELETE FROM user_role WHERE role_id = %(r)s",
    "org add": "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (gen_random_uuid(), %(a)s, %(root)s, 'unit', 'N')",
    "org move": "UPDATE org_unit SET parent_id = %(root)s WHERE id = %(team)s",
    "org rename": "UPDATE org_unit SET name = 'New' WHERE id = %(org_unit_id)s",
    "org no-op update": "UPDATE org_unit SET name = name WHERE id = %(org_unit_id)s",
}
STATE = (
    "SELECT (SELECT array_agg(name ORDER BY name) FROM role WHERE agency_id = %(a)s),"
    " (SELECT count(*) FROM role_permission WHERE agency_id = %(a)s),"
    " (SELECT count(*) FROM user_role WHERE agency_id = %(a)s),"
    " (SELECT array_agg(o::text ORDER BY o.id) FROM org_unit o WHERE agency_id = %(a)s)"
)


@contextmanager
def without_operator(value: str | None, earlier: bool) -> Iterator[Cursor]:
    """owner()'s setup with `value` as skiw.operator (None: never set in this session; `earlier`:
    set and committed in a previous transaction first). Rows are made with audit triggers off."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        if earlier:
            conn.execute("SELECT set_config('skiw.operator', 'ops-1', true)")
            conn.commit()
        with conn.transaction(force_rollback=True), conn.cursor() as cursor:
            for table in LIFTED:
                cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            for table in AUDITED:
                cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER {table}_audit")
            yield cursor


@pytest.mark.parametrize("bad", BAD_OPERATORS)
def test_a_missing_empty_or_malformed_operator_is_refused_with_nothing_written(bad: str) -> None:
    value = BAD_OPERATORS[bad]
    with without_operator(value, earlier=bad == "ended-earlier") as cursor:
        seed.insert_agency(cursor, X, "Operator test X")
        ids = assignment(cursor, X)
        assign(cursor, X, ids, "both")
        tick(cursor, X, ids["role_id"])
        params = {**ids, "a": X, "r": ids["role_id"], "spare": add_role(cursor, "Spare", agency=X)}
        params |= {"root": root_of(cursor, X), "team": add_unit(cursor, X, ids["org_unit_id"])}
        for table in AUDITED:
            cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER {table}_audit")
        if bad not in ("never-set", "ended-earlier"):
            cursor.execute("SELECT set_config('skiw.operator', %s, true)", [value])
        found = cursor.execute("SELECT current_setting('skiw.operator', true)").fetchone()
        assert found == (value,)
        before = cursor.execute(STATE, {"a": X}).fetchone()
        for sql in REFUSED_WRITES.values():
            assert refusal(cursor, sql, params) == NO_OPERATOR
        assert cursor.execute(STATE, {"a": X}).fetchone() == before
        assert Log(cursor, X).new() == []


def test_a_change_and_its_event_roll_back_together() -> None:
    with owner() as cursor:
        log = Log(cursor, X)
        with pytest.raises(RuntimeError), cursor.connection.transaction():
            role = add_role(cursor, "Gone", agency=X)
            assert [k for k, _, _ in log.new()] == ["role.created"]
            raise RuntimeError("before commit")
        assert cursor.execute("SELECT count(*) FROM role WHERE id = %s", [role]).fetchone() == (0,)
        log.seen.clear()
        assert log.new() == []


CHECKS: dict[str, tuple[Callable[[Cursor, uuid.UUID], None], tuple[str, str], list[str]]] = {
    "role_system_complete": (incomplete_owner, INCOMPLETE, ["permission.set", "role.created"]),
    "user_role_owner_remains": (last_owner_removed, NO_HOLDER, ["role.unassigned"]),
}


@pytest.mark.parametrize("check", CHECKS)
def test_a_deferred_check_failing_at_commit_leaves_no_change_and_no_event(check: str) -> None:
    build, error, kinds = CHECKS[check]
    agencies: list[uuid.UUID] = []

    def built(cursor: Cursor, agency: uuid.UUID) -> None:
        build(cursor, agency)
        agencies.append(agency)
        assert set(kinds) <= {k for k, _, _ in Log(cursor, agency).new()}  # written before COMMIT

    assert commit_refusal(built) == error
    with owner(agencies=False) as cursor:
        assert Log(cursor, *agencies).new() == []
        roles = cursor.execute("SELECT count(*) FROM role WHERE agency_id = %s", agencies)
        assert roles.fetchone() == (0,)


def test_the_event_carries_the_rows_agency_and_only_that_agency_sees_it() -> None:
    """A role of A committed by the owner (FORCE back on before the commit); read as skiw_app."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT set_config('skiw.operator', %s, true)", [OPERATOR])
        seed.insert_agency(cursor, A, "Agency A")
        seed.insert_agency(cursor, B, "Agency B")
        for table in ("role", "security_event"):
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        role = add_role(cursor, f"Audit {uuid.uuid4()}", agency=A)
        for table in ("role", "security_event"):
            cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    seen: dict[str, list[tuple[Any, ...]]] = {}
    for context, agency in {"A": A, "B": B, "none": None}.items():
        with (
            transaction.atomic() if agency is None else with_agency(agency),
            connection.cursor() as app,
        ):
            app.execute(
                "SELECT kind, agency_id FROM security_event WHERE details_json ->> 'role_id' = %s",
                [str(role)],
            )
            seen[context] = app.fetchall()
    assert seen == {"A": [("role.created", A)], "B": [], "none": []}


def test_the_reverse_refuses_with_a_write_grant_and_otherwise_drops_the_audit_triggers() -> None:
    assert MIGRATION.REVERSE[0] == MIGRATION.LOCKS.GUARD  # the 0026 guard, the same statement
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)  # accounts.0030's grants, so the one below is what the guard sees
        cursor.execute("GRANT INSERT ON role_permission TO skiw_app")
        assert refusal(cursor, MIGRATION.REVERSE[0])[0] == "55000"
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)
        for statement in MIGRATION.REVERSE:
            cursor.execute(statement)
        left = cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname = ANY(%s)", [AUDITS])
        assert left.fetchone() == (0,)
        for function in MIGRATION.FUNCTIONS.values():
            assert cursor.execute("SELECT to_regprocedure(%s)", [function]).fetchone() == (None,)
