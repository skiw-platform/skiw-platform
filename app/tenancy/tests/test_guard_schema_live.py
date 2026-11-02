"""The `guard` schema, `pgcrypto` and the key tables after `make migrate` (spec §4.1, §4.2 "Tenant
binding", TEN-01, TEN-02 (hard); plan M4c-2a). Plain psycopg connections on the two URLs: every
check reads the catalogs, and the few that write run in one transaction they roll back."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql

from tenancy.ddl import GUARD_OWNERS, as_owner

pytestmark = pytest.mark.live

# Built with zip(), not a literal dict: gitleaks reads a key name next to a long value as a secret.
_TABLES = ("tenant_mac_key", "lookup_decoy_key")
_OWNERS = ("skiw_tenant_guard", "skiw_auth_lookup")
KEY_TABLES = dict(zip(_TABLES, _OWNERS, strict=True))
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
# skiw_backup is left out on purpose: pg_read_all_data gives it SELECT on every table, and spec
# §8.4 H6 keeps the key data out of dumps (plan M4c-2a, PR 82 notes).
NO_KEY_ACCESS = ("skiw_app", "skiw_readonly", "skiw_migrator")
MANAGE = Path(__file__).resolve().parents[2] / "manage.py"


def rows(sql: LiteralString, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchall()


def set_role(role: str) -> sql.Composed:
    return sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role))


def test_the_schema_is_the_migrators_and_each_key_table_its_nologin_owners() -> None:
    assert rows("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'guard'") == [
        ("skiw_migrator",)
    ]
    owners = rows(
        "SELECT relname, relowner::regrole::text FROM pg_class"
        " WHERE relnamespace = 'guard'::regnamespace AND relkind = 'r'"
    )
    assert dict(owners) == KEY_TABLES


def test_guard_acl_is_exactly_migrator_usage_create_and_owner_usage() -> None:
    acl = rows(
        "SELECT a.grantee::regrole::text, a.privilege_type FROM pg_namespace n,"
        " aclexplode(n.nspacl) a WHERE n.nspname = 'guard'"
    )
    assert sorted(acl) == [
        ("skiw_auth_lookup", "USAGE"),
        ("skiw_migrator", "CREATE"),
        ("skiw_migrator", "USAGE"),
        ("skiw_tenant_guard", "USAGE"),
    ]


def test_skiw_app_has_no_usage_on_guard_until_current_agency_exists() -> None:
    # M4c-4a grants USAGE together with guard.current_agency().
    assert rows(
        "SELECT has_schema_privilege('skiw_app', 'guard', 'USAGE'),"
        " has_schema_privilege('skiw_app', 'guard', 'CREATE')"
    ) == [(False, False)]


def test_skiw_app_has_create_on_no_schema() -> None:
    assert (
        rows(
            "SELECT nspname FROM pg_namespace WHERE has_schema_privilege('skiw_app', oid, 'CREATE')"
        )
        == []
    )


def test_no_grant_of_any_kind_on_a_key_table() -> None:
    assert (
        rows(
            "SELECT relname FROM pg_class WHERE relnamespace = 'guard'::regnamespace"
            " AND relkind = 'r' AND relacl IS NOT NULL"
        )
        == []
    )


@pytest.mark.parametrize("role", NO_KEY_ACCESS)
@pytest.mark.parametrize("table", sorted(KEY_TABLES))
def test_no_privilege_on_the_key_tables(role: str, table: str) -> None:
    # Includes has_table_privilege('skiw_migrator', 'guard.tenant_mac_key', 'SELECT'): INHERIT
    # FALSE means the migrator's membership in the owner adds nothing here.
    held = [
        privilege
        for privilege in TABLE_PRIVILEGES
        if rows("SELECT has_table_privilege(%s, %s, %s)", role, f"guard.{table}", privilege)[0][0]
    ]
    assert held == []


@pytest.mark.parametrize(("table", "owner"), sorted(KEY_TABLES.items()))
def test_the_migrator_reads_a_key_table_only_after_set_role(table: str, owner: str) -> None:
    query = sql.SQL("SELECT count(*) FROM guard.{}").format(sql.Identifier(table))
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(query)
        conn.rollback()
        conn.execute(set_role(owner))
        conn.execute(query)  # the positive control
        conn.rollback()


@pytest.mark.parametrize(("table", "owner"), sorted(KEY_TABLES.items()))
@pytest.mark.parametrize(
    ("version", "length", "ok"),
    [(1, 32, True), (999_999, 64, True), (0, 32, False), (1_000_000, 32, False), (1, 31, False)],
)
def test_key_table_checks(table: str, owner: str, version: int, length: int, ok: bool) -> None:
    insert = sql.SQL("INSERT INTO guard.{} (version, key) VALUES (%s, %s)").format(
        sql.Identifier(table)
    )
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        conn.execute(set_role(owner))
        if ok:
            conn.execute(insert, (version, bytes(length)))
        else:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(insert, (version, bytes(length)))
        conn.rollback()


def test_pgcrypto_lives_in_guard() -> None:
    # A1: the migrator installs the trusted extension and owns it; its functions belong to the
    # bootstrap superuser and keep PUBLIC EXECUTE (plan §9 item 9; unreachable without USAGE).
    assert rows(
        "SELECT extnamespace::regnamespace::text, extowner::regrole::text FROM pg_extension"
        " WHERE extname = 'pgcrypto'"
    ) == [("guard", "skiw_migrator")]
    assert rows(
        "SELECT DISTINCT proowner::regrole::text FROM pg_proc"
        " WHERE pronamespace = 'guard'::regnamespace"
    ) == [("postgres",)]
    assert rows("SELECT to_regprocedure('guard.hmac(bytea,bytea,text)') IS NOT NULL") == [(True,)]


SNAPSHOT: LiteralString = """
SELECT c.relname, c.relowner::regrole::text, c.relacl::text,
       (SELECT string_agg(concat_ws(' ', a.attname, format_type(a.atttypid, a.atttypmod),
                                    a.attnotnull, pg_get_expr(d.adbin, d.adrelid)), ', '
                          ORDER BY a.attnum)
          FROM pg_attribute a
          LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
         WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
       (SELECT string_agg(pg_get_constraintdef(k.oid), ', ' ORDER BY pg_get_constraintdef(k.oid))
          FROM pg_constraint k WHERE k.conrelid = c.oid)
FROM pg_class c WHERE c.relnamespace = 'guard'::regnamespace AND c.relkind = 'r'
UNION ALL
SELECT 'acl:guard', nspowner::regrole::text, nspacl::text, NULL, NULL
FROM pg_namespace WHERE nspname = 'guard'
ORDER BY 1"""


def migrate(*target: str) -> None:
    env = {**os.environ, "DATABASE_URL": os.environ["MIGRATION_DATABASE_URL"]}
    command = [sys.executable, str(MANAGE), "migrate", *target]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_the_unlinted_key_table_migration_reverses_and_reapplies_exactly() -> None:
    # make migrate skips 0002 in lintmigrations (docs/DECISIONS.md "M4c-2a"), so its forward
    # and reverse are proven here: the reverse drops both tables as their owners and leaves the
    # schema ACL as 0001 made it; the forward rebuilds the same tables.
    before = rows(SNAPSHOT)
    assert len(before) == 3
    try:
        migrate("tenancy", "0001")
        assert rows(
            "SELECT to_regclass('guard.tenant_mac_key'), to_regclass('guard.lookup_decoy_key')"
        ) == [(None, None)]
        assert rows(SNAPSHOT) == [row for row in before if row[0] == "acl:guard"]
    finally:
        migrate()
    assert rows(SNAPSHOT) == before


PROBE_TABLE = "guard.as_owner_probe"


def owner_probe(role: str) -> list[sql.SQL]:
    op = as_owner(role, [f"CREATE TABLE {PROBE_TABLE} (x int)"], [f"DROP TABLE {PROBE_TABLE}"])
    return [sql.SQL(statement) for statement in op.sql if isinstance(statement, str)]


@pytest.mark.parametrize("role", sorted(GUARD_OWNERS))
def test_as_owner_in_a_transaction_creates_the_object_as_the_role(role: str) -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        for statement in owner_probe(role):
            conn.execute(statement)
        owner = conn.execute(
            "SELECT relowner::regrole::text FROM pg_class WHERE oid = %s::regclass", (PROBE_TABLE,)
        ).fetchall()
        assert owner == [(role,)]
        assert conn.execute("SELECT current_user::text").fetchall() == [("skiw_migrator",)]
        conn.rollback()


@pytest.mark.parametrize("role", sorted(GUARD_OWNERS))
def test_as_owner_outside_a_transaction_stops_before_the_first_object(role: str) -> None:
    # A non-atomic migration: SET LOCAL ROLE is a no-op there (only a notice), so the DO check
    # must raise before the CREATE runs as the migrator. The GRANT before it has committed and
    # is left behind (docs/DECISIONS.md "M4c-2b"); the finally takes it back.
    try:
        with (
            psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn,
            pytest.raises(psycopg.errors.RaiseException, match="as_owner: current_user"),
        ):
            for statement in owner_probe(role):
                conn.execute(statement)
        assert rows("SELECT to_regclass(%s)", PROBE_TABLE) == [(None,)]
        assert rows("SELECT has_schema_privilege(%s, 'guard', 'CREATE')", role) == [(True,)]
    finally:
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.SQL(PROBE_TABLE)))
            conn.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA guard FROM {}").format(sql.Identifier(role))
            )
