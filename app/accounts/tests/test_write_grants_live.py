"""accounts.0030 on the live schema (plan row M4r-1g, split M4r-1g-i; slice spec Decisions 3, 32,
33; the §7 intermediate-migration items). As the migrator, each in a rolled-back transaction: the
precondition refuses, and grants nothing, with any Decision 32 trigger dropped, disabled or set to
fire on replicas only, and with security_event's RLS or a policy changed; it passes on the real
schema; the reverse and the forward restore every grant and policy; the earlier reverses refuse
while the grants exist; and skiw_app holds no write on the roles tables at any accounts prefix from
0016 to 0029, and exactly Decision 3's at 0030, migrated back and then forward one at a time; on
the way back, 0022's reverse refuses while a change row exists."""

import importlib
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
from django.db.migrations.executor import MigrationExecutor

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


def writes(cursor: Any) -> set[tuple[str, str]]:
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


def unapply_0022_refused_while_change_rows(executor: MigrationExecutor, cursor: Any) -> None:
    """0022's reverse refuses while a change row exists and keeps it (PR 177 P2). Then the test,
    not the migration, clears the change rows this database holds (the seed, the TEN-08 harness
    and the audit tests commit them), so the walk's own reverse of 0022 runs."""
    planted = uuid.uuid4()
    cursor.execute(
        "INSERT INTO security_event (id, at, kind, agency_id, details_json)"
        " VALUES (%s, now(), 'role.created', %s, '{}')",
        [planted, uuid.uuid4()],  # no shape trigger, RLS or agency FK at this prefix
    )
    with pytest.raises(DatabaseError) as caught:
        executor.migrate([("accounts", "0021_org_unit_user_role_rls")])
    cause = cast(psycopg.Error, caught.value.__cause__)
    assert (cause.sqlstate, cause.diag.message_primary) == KEPT
    executor.loader.build_graph()
    cursor.execute("SELECT count(*) FROM security_event WHERE id = %s", [planted])
    assert cursor.fetchone() == (1,)
    cursor.execute("DELETE FROM security_event WHERE kind = ANY(%s)", [CHANGE_KINDS])


def test_no_write_grant_at_any_prefix_before_0030() -> None:
    """Back from 0030 to 0016, then forward to 0030, one migration at a time (Decision 32
    "Intermediate states"). 0023 is recorded only (fake): its index is built CONCURRENTLY, which
    cannot run in a transaction, and grants nothing (test_write_grants pins every GRANT). Before
    0022 is reversed, its reverse is shown to refuse while change rows exist."""
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
                if target == "0021_org_unit_user_role_rls" and direction == "back":
                    unapply_0022_refused_while_change_rows(executor, cursor)
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
