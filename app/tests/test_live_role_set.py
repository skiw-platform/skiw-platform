"""Role-set test (spec §8.4 H6, §4.2 TEN-02 row; plans M1e, M4c-1). Runs wherever `make test-live`
points: the local/CI database (docker/postgres/10-roles.sh applies infra/host/db/roles.sql) and,
in G-S1, the VPS. It reads the catalogs, which every role may read, except the FORCE-RLS probe,
which runs DDL, grants and SET LOCAL ROLE as the migrator in one transaction it rolls back, so it
leaves nothing behind."""

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


GUARD_ROLES = {"skiw_tenant_guard", "skiw_auth_lookup"}


def test_migrator_is_a_set_only_member_of_exactly_the_two_guard_roles() -> None:
    # Hard-coded, not read from roles.sql: a change to the GRANT and the drift guard together
    # must still fail here (owner Q1 (a), plan M4c-1).
    granted = rows(
        "select roleid::regrole::text, admin_option, inherit_option, set_option, "
        "pg_has_role('skiw_migrator', roleid, 'USAGE'), "
        "pg_has_role('skiw_migrator', roleid, 'SET') "
        "from pg_auth_members where member = 'skiw_migrator'::regrole order by 1"
    )
    assert granted == [
        ("skiw_auth_lookup", False, False, True, False, True),
        ("skiw_tenant_guard", False, False, True, False, True),
    ]


def test_no_other_role_is_a_member_of_a_guard_role() -> None:
    members = rows(
        "select member::regrole::text, roleid::regrole::text from pg_auth_members "
        "where roleid in ('skiw_tenant_guard'::regrole, 'skiw_auth_lookup'::regrole) order by 2"
    )
    assert members == [
        ("skiw_migrator", "skiw_auth_lookup"),
        ("skiw_migrator", "skiw_tenant_guard"),
    ]


def test_migrator_sees_no_force_rls_row_until_it_sets_role_to_the_bypass_owner() -> None:
    # No FORCE-RLS table exists before M4c-5, so a probe table is made and rolled back. The
    # positive control (the row is visible after SET ROLE skiw_auth_lookup) keeps it from being
    # vacuous; the inherit probe fails when the membership is INHERIT TRUE.
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("create table skiw_force_rls_probe (id int)")
        cur.execute("insert into skiw_force_rls_probe values (1)")
        cur.execute("alter table skiw_force_rls_probe enable row level security")
        cur.execute("alter table skiw_force_rls_probe force row level security")
        cur.execute("select count(*) from skiw_force_rls_probe")
        assert cur.fetchone() == (0,)
        cur.execute("grant select on skiw_force_rls_probe to skiw_auth_lookup")
        cur.execute("revoke select on skiw_force_rls_probe from skiw_migrator")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            cur.execute("select count(*) from skiw_force_rls_probe")  # no inherited grant
        cur.execute("set local role skiw_auth_lookup")
        cur.execute("select current_user, count(*) from skiw_force_rls_probe group by 1")
        assert cur.fetchone() == ("skiw_auth_lookup", 1)
        cur.execute("reset role")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            cur.execute("set local role skiw_app")
        conn.rollback()


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
