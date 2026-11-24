"""The roles lock and the refusal triggers on the live schema (plan row M4r-1d, split M4r-1d-i;
slice spec Decisions 27, 28, 32; accounts.0026). skiw_app may only SELECT the four tables until
M4r-1g, so every write here runs as the owner, skiw_migrator, on one connection, in one transaction
under transaction-local NO FORCE with a test skiw.operator (the tenancy.seed pattern), rolled back.
The two-connection races are M4r-1h; the grant audit (SELECT only) is test_access_tables_live."""

import importlib
import os
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from psycopg import IsolationLevel

from accounts.tests.test_access_tables_live import AGENCY, add_role
from accounts.tests.test_org_tables_live import add_root, add_unit, assign, assignment
from tenancy import seed

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MIGRATION = importlib.import_module("accounts.migrations.0026_roles_lock_refusals")
TABLES = MIGRATION.TABLES
LIFTED = ("app_user", "security_event", *TABLES)  # NO FORCE: the writes and their audit events
X, Y = uuid.uuid4(), uuid.uuid4()  # this module's agencies, gone with each rollback
NOT_READ_COMMITTED = ("25000", "roles change refused: the transaction must be read committed")
REFUSED = ("42501", "roles change refused: this statement is not allowed on this table")
TICK = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (gen_random_uuid(), %s, %s, 'client.view', 'own') RETURNING id"
)
type Cursor = psycopg.Cursor[Any]


@contextmanager
def owner(level: IsolationLevel | None = None, agencies: bool = True) -> Iterator[Cursor]:
    """The migrator in one transaction at `level` (the server default, READ COMMITTED, when None),
    FORCE lifted on the tables written, agencies X and Y added unless `agencies` is false (then
    nothing is written before the test's own first write); all rolled back."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        conn.isolation_level = level
        with conn.transaction(force_rollback=True), conn.cursor() as cursor:
            cursor.execute("SELECT set_config('skiw.operator', 'test-operator', true)")
            for table in LIFTED:
                cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            if agencies:
                seed.insert_agency(cursor, X, "Lock test X")
                seed.insert_agency(cursor, Y, "Lock test Y")
            yield cursor


def refusal(
    cursor: Cursor, sql: str, params: Sequence[object] | Mapping[str, object] | None = None
) -> tuple[str, str]:
    """Run `sql` in a savepoint; the SQLSTATE and message of the error it raises."""
    with pytest.raises(psycopg.Error) as caught, cursor.connection.transaction():
        cursor.execute(sql, params)
    return str(caught.value.sqlstate), str(caught.value.diag.message_primary)


def tick(cursor: Cursor, agency: uuid.UUID, role: uuid.UUID) -> uuid.UUID:
    row = cursor.execute(TICK, [agency, role]).fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def roles_locks(cursor: Cursor) -> set[tuple[int, int]]:
    """The roles locks this backend holds, as (key1, key2) of the two-key form (pg_locks shows
    the keys in classid and objid as oid, with objsubid 2)."""
    rows = cursor.execute(
        "SELECT classid::bigint, objid::bigint FROM pg_locks WHERE locktype = 'advisory'"
        " AND objsubid = 2 AND granted AND pid = pg_backend_pid() AND classid = %s::oid",
        [MIGRATION.ROLES_LOCK_CLASS],
    ).fetchall()
    return {(int(a), int(b)) for a, b in rows}


def lock_of(cursor: Cursor, agency: uuid.UUID) -> tuple[int, int]:
    row = cursor.execute(
        "SELECT %s::oid::bigint, hashtext(%s::text)::oid::bigint",
        [MIGRATION.ROLES_LOCK_CLASS, str(agency)],
    ).fetchone()
    assert row is not None
    return int(row[0]), int(row[1])


# A write to each table that names rows which do not exist: the BEFORE trigger runs before any
# FK or CHECK, so the isolation refusal is the only error it can raise.
FIRST_WRITE = {
    "role": "INSERT INTO role (id, agency_id, name) VALUES (gen_random_uuid(), %s, 'Rr')",
    "role_permission": "INSERT INTO role_permission (id, agency_id, role_id, permission_code,"
    " scope) VALUES (gen_random_uuid(), %s, gen_random_uuid(), 'client.view', 'own')",
    "user_role": "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (gen_random_uuid(), %s, gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),"
    " 'both')",
    "org_unit": "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (gen_random_uuid(), %s, NULL, 'agency', 'Rr')",
}
LEVELS = {
    "repeatable-read": IsolationLevel.REPEATABLE_READ,
    "serializable": IsolationLevel.SERIALIZABLE,
    "read-uncommitted": IsolationLevel.READ_UNCOMMITTED,  # runs as read committed, still refused
}


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("table", TABLES)
def test_a_writer_not_at_read_committed_is_refused_at_its_first_write(
    table: str, level: str
) -> None:
    with owner(LEVELS[level], agencies=False) as cursor:
        assert cursor.execute("SHOW transaction_isolation").fetchone() == (level.replace("-", " "),)
        assert refusal(cursor, FIRST_WRITE[table], [AGENCY]) == NOT_READ_COMMITTED


def test_read_committed_writes_to_the_four_tables_are_accepted() -> None:
    with owner(IsolationLevel.READ_COMMITTED) as cursor:
        ids = assignment(cursor, X)  # a root, a unit, a role and a user
        assign(cursor, X, ids, "both")
        role_tick = tick(cursor, X, ids["role_id"])
        cursor.execute("UPDATE role SET name = 'Renamed' WHERE id = %s", [ids["role_id"]])
        cursor.execute("UPDATE role SET name = name WHERE id = %s", [ids["role_id"]])  # no-op
        cursor.execute("UPDATE org_unit SET name = 'Renamed' WHERE id = %s", [ids["org_unit_id"]])
        cursor.execute("DELETE FROM role_permission WHERE id = %s", [role_tick])
        cursor.execute("DELETE FROM user_role WHERE agency_id = %s", [X])
        cursor.execute("DELETE FROM role WHERE id = %s", [ids["role_id"]])
        counts = cursor.execute(
            "SELECT (SELECT count(*) FROM role WHERE agency_id = %(a)s),"
            " (SELECT count(*) FROM role_permission WHERE agency_id = %(a)s),"
            " (SELECT count(*) FROM user_role WHERE agency_id = %(a)s),"
            " (SELECT count(*) FROM org_unit WHERE agency_id = %(a)s AND name = 'Renamed')",
            {"a": X},
        ).fetchone()
        assert counts == (0, 0, 0, 1)


def write_role(cursor: Cursor, agency: uuid.UUID, ids: dict[str, uuid.UUID]) -> None:
    add_role(cursor, f"Lock {uuid.uuid4()}", agency=agency)


def write_tick(cursor: Cursor, agency: uuid.UUID, ids: dict[str, uuid.UUID]) -> None:
    tick(cursor, agency, ids["role_id"])


def write_assignment(cursor: Cursor, agency: uuid.UUID, ids: dict[str, uuid.UUID]) -> None:
    assign(cursor, agency, ids, "both")


def write_unit(cursor: Cursor, agency: uuid.UUID, ids: dict[str, uuid.UUID]) -> None:
    add_unit(cursor, agency, ids["org_unit_id"])


WRITE: dict[str, Callable[[Cursor, uuid.UUID, dict[str, uuid.UUID]], None]] = {
    "role": write_role,
    "role_permission": write_tick,
    "user_role": write_assignment,
    "org_unit": write_unit,
}


@pytest.mark.parametrize("table", TABLES)
def test_a_write_to_each_table_takes_its_agencys_roles_lock(table: str) -> None:
    """The rows it needs are made with every lock trigger off (DDL, rolled back), then only
    `table`'s is turned on, so the lock seen after the write is the one its own trigger took."""
    with owner() as cursor:
        for each in TABLES:
            cursor.execute(f"ALTER TABLE {each} DISABLE TRIGGER {each}_roles_lock")
        ids = {agency: assignment(cursor, agency) for agency in (X, Y)}
        cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER {table}_roles_lock")
        assert roles_locks(cursor) == set()
        WRITE[table](cursor, X, ids[X])
        assert roles_locks(cursor) == {lock_of(cursor, X)}
        WRITE[table](cursor, Y, ids[Y])
        assert roles_locks(cursor) == {lock_of(cursor, X), lock_of(cursor, Y)}


def test_one_agency_takes_one_lock_across_the_four_tables_and_another_agency_its_own() -> None:
    with owner() as cursor:
        ids = assignment(cursor, X)
        assign(cursor, X, ids, "insurance")
        cursor.execute(
            "DELETE FROM role_permission WHERE id = %s", [tick(cursor, X, ids["role_id"])]
        )
        add_unit(cursor, X, ids["org_unit_id"], kind="team")
        assert roles_locks(cursor) == {lock_of(cursor, X)}  # re-entrant: one lock, held
        add_root(cursor, Y)
        assert roles_locks(cursor) == {lock_of(cursor, X), lock_of(cursor, Y)}
        assert lock_of(cursor, X) != lock_of(cursor, Y)
        assert lock_of(cursor, X)[0] == MIGRATION.ROLES_LOCK_CLASS


def test_role_permission_and_user_role_rows_are_never_updated() -> None:
    with owner() as cursor:
        ids = assignment(cursor, X)
        assign(cursor, X, ids, "both")
        role_tick = tick(cursor, X, ids["role_id"])
        for sql, params in [
            ("UPDATE role_permission SET scope = scope WHERE id = %s", [role_tick]),
            ("UPDATE user_role SET line = 'insurance' WHERE agency_id = %s", [X]),
            ("UPDATE user_role SET line = line WHERE agency_id = %s", [X]),  # a no-op too
        ]:
            assert refusal(cursor, sql, params) == REFUSED


def test_an_org_unit_is_never_deleted() -> None:
    with owner() as cursor:
        root = add_root(cursor, X)
        leaf = add_unit(cursor, X, root, kind="team")
        for unit in (leaf, root):
            assert refusal(cursor, "DELETE FROM org_unit WHERE id = %s", [unit]) == REFUSED
        count = cursor.execute("SELECT count(*) FROM org_unit WHERE agency_id = %s", [X]).fetchone()
        assert count == (2,)


ROLE_COLUMNS = {
    "id": ("UPDATE role SET id = gen_random_uuid() WHERE id = %s", []),
    "agency_id": ("UPDATE role SET agency_id = %s WHERE id = %s", [Y]),
    "is_system": ("UPDATE role SET is_system = true WHERE id = %s", []),
    "created_at": ("UPDATE role SET created_at = created_at - interval '1 day' WHERE id = %s", []),
    "name-and-is_system": ("UPDATE role SET name = 'Other', is_system = true WHERE id = %s", []),
}


@pytest.mark.parametrize("column", ROLE_COLUMNS)
def test_a_role_update_of_any_column_but_name_is_refused(column: str) -> None:
    with owner() as cursor:
        role = add_role(cursor, "Before", agency=X)
        sql, params = ROLE_COLUMNS[column]
        assert refusal(cursor, sql, [*params, role]) == REFUSED
        cursor.execute("UPDATE role SET name = 'After' WHERE id = %s", [role])  # name: accepted
        row = cursor.execute("SELECT name, is_system FROM role WHERE id = %s", [role]).fetchone()
        assert row == ("After", False)


@pytest.mark.parametrize("table", TABLES)
def test_truncate_is_refused_on_each_table(table: str) -> None:
    """TRUNCATE … CASCADE reaches the tables with an FK to `table` (a plain TRUNCATE of role or
    org_unit fails the FK check before any trigger); their TRUNCATE triggers are off for this
    rolled-back transaction, so `table`'s own trigger is the one that refuses."""
    with owner() as cursor:
        add_role(cursor, "Kept", agency=X)
        for other in TABLES:
            if other != table:
                cursor.execute(f"ALTER TABLE {other} DISABLE TRIGGER {other}_refuse_truncate")
        assert refusal(cursor, f"TRUNCATE {table} CASCADE") == REFUSED
        assert cursor.execute("SELECT count(*) FROM role WHERE agency_id = %s", [X]).fetchone() == (
            1,
        )


ROW, BEFORE, INSERT, DELETE, UPDATE, TRUNCATE = 1, 2, 4, 8, 16, 32
LOCK, REFUSE = "public.roles_lock", "public.roles_refuse"
TREE, SYSTEM = "public.org_unit_tree_guard", "public.role_system_guard"
REMAINS = "public.user_role_owner_remains"
AUDITED = ("role_permission", "user_role")  # INSERT OR DELETE; role also on UPDATE
EXPECTED_TRIGGERS = {
    *((t, f"{t}_roles_lock", ROW | BEFORE | INSERT | DELETE | UPDATE, LOCK, False) for t in TABLES),
    ("role_permission", "role_permission_refuse_update", ROW | BEFORE | UPDATE, REFUSE, False),
    ("user_role", "user_role_refuse_update", ROW | BEFORE | UPDATE, REFUSE, False),
    ("org_unit", "org_unit_refuse_delete", ROW | BEFORE | DELETE, REFUSE, False),
    ("role", "role_refuse_update", ROW | BEFORE | UPDATE, REFUSE, True),  # WHEN: not only name
    *((t, f"{t}_refuse_truncate", BEFORE | TRUNCATE, REFUSE, False) for t in TABLES),
    # M4r-1d-ii (accounts.0027): the tree guard (UPDATE OF parent_id), the system-role guards and
    # the two deferred constraint triggers (AFTER, no BEFORE bit).
    ("org_unit", "org_unit_tree_guard", ROW | BEFORE | INSERT | UPDATE, TREE, False),
    ("role", "role_system_guard", ROW | BEFORE | DELETE, SYSTEM, True),  # WHEN: OLD.is_system
    ("role_permission", "role_permission_system_guard", ROW | BEFORE | DELETE, SYSTEM, False),
    ("role", "role_system_complete", ROW | INSERT, "public.role_system_complete", True),
    ("user_role", "user_role_owner_remains", ROW | UPDATE | DELETE, REMAINS, False),
    # M4r-1e-i (accounts.0028): the audit triggers, AFTER (no BEFORE bit) FOR EACH ROW.
    ("role", "role_audit", ROW | INSERT | UPDATE | DELETE, "public.role_audit", False),
    *((t, f"{t}_audit", ROW | INSERT | DELETE, f"public.{t}_audit", False) for t in AUDITED),
}
DEFERRED = {"role_system_complete", "user_role_owner_remains"}  # DEFERRABLE INITIALLY DEFERRED


def as_migrator(query: str, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        return conn.execute(query, params).fetchall()


def test_every_trigger_on_the_four_tables_is_listed_and_enabled() -> None:
    """Exactly the M4r-1d and M4r-1e-i triggers (M4r-1e-ii adds org_unit_audit), each enabled in
    the normal session_replication_role ('O'), with its event, timing, level and function; only
    the two constraint triggers are deferred."""
    rows = as_migrator(
        "SELECT c.relname::text, t.tgname::text, t.tgenabled::text, t.tgtype::int,"
        " n.nspname || '.' || p.proname, t.tgqual IS NOT NULL,"
        " t.tgconstraint <> 0 AND t.tgdeferrable AND t.tginitdeferred"
        " FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
        " JOIN pg_proc p ON p.oid = t.tgfoid JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE NOT t.tgisinternal AND t.tgrelid = ANY(%s::regclass[])",
        [f"public.{t}" for t in TABLES],
    )
    assert {row[2] for row in rows} == {"O"}
    assert {
        (table, name, kind, function, when) for table, name, _, kind, function, when, _ in rows
    } == (EXPECTED_TRIGGERS)
    assert {row[1] for row in rows if row[6]} == DEFERRED


# BEFORE row triggers of one event fire in name order (CREATE TRIGGER, PostgreSQL 17): the lock
# first, then the guard that relies on it. Names compare as bytes (the name type), as here.
FIRING_ORDER = {
    ("org_unit", INSERT): ["org_unit_roles_lock", "org_unit_tree_guard"],
    ("org_unit", UPDATE): ["org_unit_roles_lock", "org_unit_tree_guard"],
    ("role", DELETE): ["role_roles_lock", "role_system_guard"],
    ("role_permission", DELETE): ["role_permission_roles_lock", "role_permission_system_guard"],
}


@pytest.mark.parametrize(("table", "event"), FIRING_ORDER)
def test_each_guard_fires_after_the_roles_lock(table: str, event: int) -> None:
    rows = as_migrator(
        "SELECT tgname::text, tgtype::int FROM pg_trigger WHERE NOT tgisinternal"
        ' AND tgrelid = %s::regclass ORDER BY tgname COLLATE "C"',
        f"public.{table}",
    )
    ordered = [name for name, kind in rows if kind & (ROW | BEFORE | event) == ROW | BEFORE | event]
    assert ordered == FIRING_ORDER[table, event] == sorted(ordered)


def test_the_tree_guard_fires_only_on_parent_id_updates() -> None:
    assert as_migrator(
        "SELECT ARRAY(SELECT attname::text FROM pg_attribute"
        " WHERE attrelid = tgrelid AND attnum = ANY(tgattr)) FROM pg_trigger"
        " WHERE tgname = 'org_unit_tree_guard'"
    ) == [(["parent_id"],)]


@pytest.mark.parametrize(
    "function",
    [
        LOCK,
        REFUSE,
        TREE,
        SYSTEM,
        REMAINS,
        "public.role_system_complete",
        *(f"public.{t}_audit" for t in ("role", *AUDITED)),
    ],
)
def test_the_functions_are_invokers_with_a_pinned_search_path(function: str) -> None:
    assert as_migrator(
        "SELECT p.proowner::regrole::text, p.prosecdef, p.proconfig, l.lanname::text,"
        " has_function_privilege('skiw_app', p.oid, 'EXECUTE')"
        " FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang"
        " WHERE p.oid = to_regprocedure(%s)",
        f"{function}()",
    ) == [("skiw_migrator", False, ["search_path=pg_catalog, pg_temp"], "plpgsql", False)]


GUARD_REFUSED = ("55000", "reverse refused: skiw_app holds a write privilege on a roles table")


@contextmanager
def migrator_rolled_back() -> Iterator[Cursor]:
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
        conn.cursor() as cursor,
    ):
        yield cursor


GRANTS = [
    *((table, grant) for table in TABLES for grant in ("INSERT", "UPDATE", "DELETE", "TRUNCATE")),
    ("role", "UPDATE (name)"),  # a column grant, as Decision 3's role UPDATE will be
    ("role", "INSERT (name)"),
]


@pytest.mark.parametrize(("table", "grant"), GRANTS)
def test_the_reverse_refuses_while_skiw_app_holds_a_write_grant(table: str, grant: str) -> None:
    """Decision 32 "Deployment sequence": the grant exists only in this rolled-back transaction."""
    with migrator_rolled_back() as cursor:
        cursor.execute(f"GRANT {grant} ON {table} TO skiw_app")
        assert refusal(cursor, MIGRATION.REVERSE[0]) == GUARD_REFUSED


def test_without_a_write_grant_the_reverse_drops_every_trigger_and_both_functions() -> None:
    """0028's and 0027's reverses run first, as `migrate accounts 0025` would order them."""
    later = [
        importlib.import_module(f"accounts.migrations.{name}").REVERSE
        for name in ("0028_role_audit_triggers", "0027_tree_system_role_guards")
    ]
    with migrator_rolled_back() as cursor:
        for statement in [*later[0], *later[1], *MIGRATION.REVERSE]:
            cursor.execute(statement)
        left = cursor.execute(
            "SELECT count(*) FROM pg_trigger"
            " WHERE NOT tgisinternal AND tgrelid = ANY(%s::regclass[])",
            [[f"public.{t}" for t in TABLES]],
        ).fetchone()
        functions = cursor.execute(
            "SELECT to_regprocedure('public.roles_lock()'),"
            " to_regprocedure('public.roles_refuse()')"
        ).fetchone()
        assert left == (0,) and functions == (None, None)
