"""accounts.0030 on the live schema (plan row M4r-1g, split M4r-1g-i; slice spec Decisions 3, 32,
33; the §7 intermediate-migration items). As the migrator, each in a rolled-back transaction: the
precondition refuses, and grants nothing, with any Decision 32 trigger dropped, disabled or set to
fire on replicas only, and with security_event's RLS or a policy changed; it passes on the real
schema; the reverse and the forward restore every grant and policy; the earlier reverses refuse
while the grants exist; and skiw_app holds no write on the roles tables at any accounts prefix from
0016 to 0029, and exactly Decision 3's at 0030, migrated back and then forward one at a time; on
the way back, the reverses of 0025 and 0024 refuse while a change row exists, before the shape
trigger or a policy of security_event is dropped (PR 186 R1 P1), and so does 0022's."""

import importlib
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from urllib.parse import unquote, urlsplit

import psycopg
import pytest
from django.db import DatabaseError, connection, connections, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db.backends.utils import CursorWrapper
from django.db.migrations.executor import MigrationExecutor

from accounts.tests import event_probe
from accounts.tests.test_access_tables_live import COLUMN_GRANTS, DECISION_3
from accounts.tests.test_roles_guards_live import GUARD_REFUSED, migrator_rolled_back, refusal

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MIGRATION = importlib.import_module("accounts.migrations.0030_roles_write_grants")
REFUSED = (
    "55000",
    "grant refused: a roles trigger or the security_event isolation is missing or not enabled",
)
TABLES = [*DECISION_3]
HELD = (
    "SELECT t, p FROM unnest(%s::text[]) t,"
    " unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) p"
    " WHERE to_regclass(t) IS NOT NULL AND (has_table_privilege('skiw_app', t, p)"
    " OR p IN ('INSERT', 'UPDATE') AND has_any_column_privilege('skiw_app', t, p))"
)
DECISION_3_WRITES = {
    *((t, p) for t, privileges in DECISION_3.items() for p in privileges - {"SELECT"}),
    *((t, p) for t, _, p in COLUMN_GRANTS),
}
SNAPSHOT = (
    "SELECT c.relname::text, c.relacl::text, ARRAY(SELECT a.attname || '=' || a.attacl::text"
    " FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attacl IS NOT NULL ORDER BY 1)::text,"
    " ARRAY(SELECT concat_ws(':', p.polname, p.polcmd, p.polpermissive, p.polroles,"
    " pg_get_expr(p.polqual, c.oid), pg_get_expr(p.polwithcheck, c.oid))"
    " FROM pg_policy p WHERE p.polrelid = c.oid"
    " ORDER BY 1)::text FROM pg_class c WHERE c.oid = ANY(%s::regclass[]) ORDER BY 1"
)
type Cursor = psycopg.Cursor[Any]


def writes(cursor: "Cursor | CursorWrapper") -> set[tuple[str, str]]:
    cursor.execute(HELD, [TABLES])
    return set(cursor.fetchall())


def forward(cursor: Cursor) -> tuple[str, str]:
    """accounts.0030's statements in a savepoint; the SQLSTATE and message they raise."""
    with pytest.raises(psycopg.Error) as caught, cursor.connection.transaction():
        for statement in MIGRATION.FORWARD:
            cursor.execute(statement)
    return str(caught.value.sqlstate), str(caught.value.diag.message_primary)


@contextmanager
def ungranted() -> Iterator[Cursor]:
    with migrator_rolled_back() as cursor:
        for statement in MIGRATION.REVERSE:
            cursor.execute(statement)
        assert writes(cursor) == set()
        yield cursor


TRIGGERS = [(t, name) for t, names in MIGRATION.DECISION_32.items() for name in names]
CHANGES = {
    "dropped": "DROP TRIGGER {name} ON {table}",
    "disabled": "ALTER TABLE {table} DISABLE TRIGGER {name}",
    "replica": "ALTER TABLE {table} ENABLE REPLICA TRIGGER {name}",
}


@pytest.mark.parametrize("change", CHANGES)
@pytest.mark.parametrize(("table", "name"), TRIGGERS)
def test_the_precondition_refuses_without_each_trigger_enabled(
    table: str, name: str, change: str
) -> None:
    with ungranted() as cursor:
        cursor.execute(CHANGES[change].format(table=table, name=name))
        assert forward(cursor) == REFUSED
        assert writes(cursor) == set()


EVENT_CHANGES = {
    "rls-disabled": "ALTER TABLE security_event DISABLE ROW LEVEL SECURITY",
    "not-forced": "ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY",
    **{
        f"{policy}-dropped": f"DROP POLICY {policy} ON security_event"
        for policy in ("security_event_tenant", "security_event_sel", "security_event_ins")
    },
    "sel-widened": "ALTER POLICY security_event_sel ON security_event USING (true)",
    "tenant-to-public": "ALTER POLICY security_event_tenant ON security_event TO PUBLIC",
    "extra-policy": "CREATE POLICY security_event_x ON security_event FOR SELECT TO skiw_app"
    " USING (agency_id IS NULL)",
}


@pytest.mark.parametrize("change", EVENT_CHANGES)
def test_the_precondition_refuses_without_the_security_event_isolation(change: str) -> None:
    with ungranted() as cursor:
        cursor.execute(EVENT_CHANGES[change])
        assert forward(cursor) == REFUSED
        assert writes(cursor) == set()


def test_the_precondition_passes_and_reverse_then_forward_restores_decision_3() -> None:
    with migrator_rolled_back() as cursor:
        before = cursor.execute(SNAPSHOT, [TABLES]).fetchall()
        assert writes(cursor) == DECISION_3_WRITES
        for statement in MIGRATION.REVERSE:
            cursor.execute(statement)
        assert writes(cursor) == set()
        policies = "SELECT polname::text FROM pg_policy WHERE polrelid = ANY(%s::regclass[])"
        assert {name for (name,) in cursor.execute(policies, [TABLES[1:]])} == {
            f"{t}_{suffix}" for t in TABLES[1:] for suffix in ("tenant", "sel")
        }
        for statement in MIGRATION.FORWARD:
            cursor.execute(statement)
        assert cursor.execute(SNAPSHOT, [TABLES]).fetchall() == before


@pytest.mark.parametrize(
    "name",
    [
        "0026_roles_lock_refusals",
        "0027_tree_system_role_guards",
        "0028_role_audit_triggers",
        "0029_org_unit_audit_trigger",
    ],
)
def test_an_earlier_reverse_refuses_while_the_writes_are_granted(name: str) -> None:
    guard = importlib.import_module(f"accounts.migrations.{name}").REVERSE[0]
    with migrator_rolled_back() as cursor:
        assert refusal(cursor, guard) == GUARD_REFUSED


ALIAS = "prefix_walk"


@contextmanager
def migrator_connection() -> Iterator[BaseDatabaseWrapper]:
    """A Django connection as the migrator, inside one transaction that is rolled back."""
    url = urlsplit(os.environ["MIGRATION_DATABASE_URL"])
    user, password = unquote(url.username or ""), unquote(url.password or "")
    connections[ALIAS] = DatabaseWrapper(
        {**connection.settings_dict, "USER": user, "PASSWORD": password}, ALIAS
    )
    try:
        with transaction.atomic(using=ALIAS):
            yield connections[ALIAS]
            transaction.set_rollback(True, using=ALIAS)
    finally:
        connections[ALIAS].close()
        del connections[ALIAS]


CHANGE_KINDS = list(importlib.import_module("accounts.migrations.0022_security_event_agency").KINDS)
KEPT = ("55000", "reverse refused: security_event holds role or org change events")
BACK_TO_0021 = [("accounts", "0021_org_unit_user_role_rls")]
# Each is true while security_event keeps its Decision 33 isolation: 0030's precondition parts.
ISOLATED = f"SELECT NOT ({MIGRATION.RLS_OFF}) AND NOT ({MIGRATION.POLICIES_CHANGED})"
SHAPE_TRIGGER = (
    "SELECT tgenabled::text FROM pg_trigger WHERE tgrelid = 'security_event'::regclass"
    " AND tgname = 'security_event_shape' AND NOT tgisinternal AND tgqual IS NULL"
)


def applied_head(executor: MigrationExecutor) -> str:
    return max(name for app, name in executor.loader.applied_migrations or {} if app == "accounts")


def count_change_rows(cursor: CursorWrapper, delete: bool = False) -> int:
    """The change rows, as the migrator with FORCE lifted and put back; with `delete`, then
    deleted (the test's, never the migration's: test databases only)."""
    cursor.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
    cursor.execute("SELECT count(*) FROM security_event WHERE kind = ANY(%s)", [CHANGE_KINDS])
    (count,) = cursor.fetchone()
    if delete:
        cursor.execute("DELETE FROM security_event WHERE kind = ANY(%s)", [CHANGE_KINDS])
    cursor.execute("ALTER TABLE security_event FORCE ROW LEVEL SECURITY")
    return int(count)


def refused_before_isolation_dropped(executor: MigrationExecutor, cursor: CursorWrapper) -> None:
    """At 0025 or 0024, with a change row planted through the probe trigger (as M4r-1e's audit
    triggers write) and FORCE on, Django's real reverse to 0021 refuses in the first reverse that
    would drop an isolation of security_event (PR 186 R1 P1): nothing more is unapplied, the row
    is kept, RLS stays enabled and forced with exactly its three policies, the shape trigger (at
    0025) stays enabled, and skiw_app's SELECT and INSERT are the ones those protect. Then the
    test clears the change rows this database holds (the seed, the TEN-08 harness and the audit
    tests commit them), so the walk's own reverse runs."""
    head = applied_head(executor)
    agency, planted = uuid.uuid4(), uuid.uuid4()
    cursor.execute("ALTER TABLE agency NO FORCE ROW LEVEL SECURITY")
    cursor.execute("INSERT INTO agency (id, name) VALUES (%s, 'Prefix walk')", [agency])
    cursor.execute("ALTER TABLE agency FORCE ROW LEVEL SECURITY")
    cursor.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
    details = json.dumps(event_probe.details("role.created"))
    cursor.execute(event_probe.INSERT, [planted, "role.created", agency, None, None, details])
    cursor.execute("ALTER TABLE security_event FORCE ROW LEVEL SECURITY")
    cursor.execute("SELECT count(*) FROM security_event WHERE id = %s", [planted])
    assert cursor.fetchone() == (0,)  # under FORCE the migrator sees none: the reverse lifts it
    with pytest.raises(DatabaseError) as caught:
        executor.migrate(BACK_TO_0021)
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error), caught.value  # not a later reverse's own error
    assert (cause.sqlstate, cause.diag.message_primary) == KEPT
    executor.loader.build_graph()
    assert applied_head(executor) == head
    cursor.execute(ISOLATED)
    assert cursor.fetchone() == (True,)
    cursor.execute(SHAPE_TRIGGER)
    assert cursor.fetchall() == ([("O",)] if head.startswith("0025") else [])
    privileges = "SELECT has_table_privilege('skiw_app', 'security_event', %s)"
    for privilege in ("SELECT", "INSERT"):
        cursor.execute(privileges, [privilege])
        assert cursor.fetchone() == (True,)
    cursor.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
    cursor.execute("SELECT count(*) FROM security_event WHERE id = %s", [planted])
    assert cursor.fetchone() == (1,)
    cursor.execute("ALTER TABLE security_event FORCE ROW LEVEL SECURITY")
    count_change_rows(cursor, delete=True)
    assert count_change_rows(cursor) == 0


def unapply_0022_refused_while_change_rows(
    executor: MigrationExecutor, cursor: CursorWrapper
) -> None:
    """0022's reverse refuses while a change row exists and keeps it (PR 177 P2; defence in depth
    behind 0025's and 0024's, for a database at 0022 or 0023). Then the test deletes it."""
    planted = uuid.uuid4()
    cursor.execute(
        "INSERT INTO security_event (id, at, kind, agency_id, details_json)"
        " VALUES (%s, now(), 'role.created', %s, '{}')",
        [planted, uuid.uuid4()],  # no shape trigger, RLS or agency FK at this prefix
    )
    with pytest.raises(DatabaseError) as caught:
        executor.migrate(BACK_TO_0021)
    cause = cast(psycopg.Error, caught.value.__cause__)
    assert (cause.sqlstate, cause.diag.message_primary) == KEPT
    executor.loader.build_graph()
    assert applied_head(executor) == "0022_security_event_agency"
    cursor.execute("SELECT count(*) FROM security_event WHERE id = %s", [planted])
    assert cursor.fetchone() == (1,)
    cursor.execute("DELETE FROM security_event WHERE kind = ANY(%s)", [CHANGE_KINDS])


# The walk's target whose step runs the reverse that refuses while a change row exists.
REFUSES = {
    "0024_security_event_rls": refused_before_isolation_dropped,  # reverse of 0025
    "0023_security_event_agency_index": refused_before_isolation_dropped,  # reverse of 0024
    "0021_org_unit_user_role_rls": unapply_0022_refused_while_change_rows,
}


def test_no_write_grant_at_any_prefix_before_0030() -> None:
    """Back from 0030 to 0016, then forward to 0030, one migration at a time (Decision 32
    "Intermediate states"). 0023 is recorded only (fake): its index is built CONCURRENTLY, which
    cannot run in a transaction, and grants nothing (test_write_grants pins every GRANT). Before
    0025, 0024 and 0022 are reversed, each reverse is shown to refuse while a change row exists."""
    held: dict[tuple[str, str], set[tuple[str, str]]] = {}
    present: dict[str, int] = {}  # roles tables that exist at each prefix: the walk is not vacuous
    with migrator_connection() as wrapper, wrapper.cursor() as cursor:
        executor = MigrationExecutor(wrapper)
        names = sorted(n for a, n in executor.loader.disk_migrations if a == "accounts")
        names = names[names.index("0016_factor_created_at") :]
        assert names[-1] == "0030_roles_write_grants"
        for direction, steps, unindexed in (
            ("back", names[-2::-1], "0022"),
            ("forward", names[1:], "0023"),
        ):
            for target in steps:
                if direction == "back" and target in REFUSES:
                    REFUSES[target](executor, cursor)
                executor.migrate([("accounts", target)], fake=target.startswith(unindexed))
                executor.loader.build_graph()
                held[direction, target] = writes(cursor)
                cursor.execute("SELECT count(to_regclass(t)) FROM unnest(%s::text[]) t", [TABLES])
                present[target[:4]] = cursor.fetchone()[0]
    assert held.pop(("forward", names[-1])) == DECISION_3_WRITES
    assert len(held) == 2 * len(names) - 3 and all(value == set() for value in held.values())
    assert present == {
        name[:4]: 0 if name < "0017" else 3 if name < "0020" else 5 for name in names
    }
