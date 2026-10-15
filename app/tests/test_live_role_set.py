"""Role-set test (spec §8.4 H6, §4.2 TEN-02 row; plan §3 M1e). Runs wherever `make test-live`
points: the local/CI database (docker/postgres/10-roles.sh applies infra/host/db/roles.sql) and,
in G-S1, the VPS. It reads only the catalogs, which every role may read."""

import os
from typing import LiteralString

import psycopg
import pytest

pytestmark = pytest.mark.live

CLOSED_ROLE_SET = {
    "postgres",
    "skiw_migrator",
    "skiw_app",
    "skiw_readonly",
    "skiw_backup",
    "skiw_tenant_guard",
    "skiw_auth_lookup",
}


def rows(sql: LiteralString) -> list[tuple[object, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def names(sql: LiteralString) -> set[object]:
    return {row[0] for row in rows(sql)}


def test_exactly_the_closed_role_set_exists_besides_pg_roles() -> None:
    assert names("select rolname from pg_roles where rolname !~ '^pg_'") == CLOSED_ROLE_SET


def test_only_postgres_is_superuser() -> None:
    assert names("select rolname from pg_roles where rolsuper") == {"postgres"}


def test_bypassrls_only_on_postgres_auth_lookup_and_backup() -> None:
    bypass = names("select rolname from pg_roles where rolbypassrls")
    assert bypass == {"postgres", "skiw_auth_lookup", "skiw_backup"}


def test_app_role_is_a_member_of_no_role() -> None:
    sql = "select roleid from pg_auth_members where member = 'skiw_app'::regrole"
    assert rows(sql) == []


def test_function_owners_cannot_log_in() -> None:
    login = names("select rolname from pg_roles where rolcanlogin and rolname !~ '^pg_'")
    assert login == CLOSED_ROLE_SET - {"skiw_tenant_guard", "skiw_auth_lookup"}


def test_backup_role_is_read_only_by_default_and_bounded() -> None:
    (role,) = rows(
        "select rolcreatedb, rolcreaterole, rolreplication, rolconnlimit, rolconfig "
        "from pg_roles where rolname = 'skiw_backup'"
    )
    assert role == (False, False, False, 2, ["default_transaction_read_only=on"])
    granted = names(
        "select roleid::regrole::text from pg_auth_members where member = 'skiw_backup'::regrole"
    )
    assert granted == {"pg_read_all_data"}
