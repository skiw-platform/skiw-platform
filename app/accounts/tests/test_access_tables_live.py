"""`permission`, `role` and `role_permission` on the live schema (plan row M4r-1a; slice spec §4,
Decisions 1, 3, 4). Reads run as skiw_app; rows are written by the owner, skiw_migrator, inside one
transaction under transaction-local NO FORCE that is rolled back, because skiw_app may only SELECT
these tables until M4r-1g. TEN-08 read isolation and the cross-agency composite FK run through
the harness (accounts/tests/isolation_cases.py)."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from django.db import connection

from accounts.access.catalogue import PAIRS
from tenancy.tests.isolation import B

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

APP_ROLE = "skiw_app"
TABLES = ("permission", "role", "role_permission")
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
AGENCY = uuid.UUID(os.environ.get("SKIW_DEPLOYMENT_AGENCY_ID", str(uuid.UUID(int=0))))


@pytest.fixture
def owner(agency_b: uuid.UUID) -> Iterator["psycopg.Cursor[Any]"]:
    """The migrator fixture: the table owner in one transaction with FORCE lifted on the two tenant
    tables, rolled back at the end (DDL is transactional, so FORCE is back too)."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        for table in ("role", "role_permission"):
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        yield cursor
        conn.rollback()


def refused_by(cursor: "psycopg.Cursor[Any]", sql: str, params: list[object]) -> str:
    """Run `sql` in a savepoint; return the name of the constraint that refused it."""
    with pytest.raises(psycopg.errors.IntegrityError) as caught, cursor.connection.transaction():
        cursor.execute(sql, params)
    return str(caught.value.diag.constraint_name)


def add_role(
    cursor: "psycopg.Cursor[Any]", name: str, agency: uuid.UUID = AGENCY, is_system: bool = False
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO role (id, agency_id, name, is_system) VALUES (%s, %s, %s, %s)",
        [row, agency, name, is_system],
    )
    return row


TICK = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (gen_random_uuid(), %s, %s, %s, %s)"
)
ROLE = "INSERT INTO role (id, agency_id, name, is_system) VALUES (gen_random_uuid(), %s, %s, %s)"


def test_permission_equals_the_catalogue() -> None:
    with connection.cursor() as cursor:  # skiw_app, no tenant token: a global table
        cursor.execute("SELECT code, scope FROM permission")
        assert set(cursor.fetchall()) == PAIRS


@pytest.mark.parametrize(
    ("code", "scope"),
    [("client.fly", "own"), ("staff.manage", "own"), ("connector.connect", "agency")],
    ids=["unknown-code", "disallowed-scope", "disallowed-scope-2"],
)
def test_the_fk_refuses_a_pair_outside_the_catalogue(
    owner: "psycopg.Cursor[Any]", code: str, scope: str
) -> None:
    role = add_role(owner, "Adviser")
    assert refused_by(owner, TICK, [AGENCY, role, code, scope]) == "role_permission_permission_fk"
    owner.execute(TICK, [AGENCY, role, "staff.manage", "agency"])  # a catalogue pair is accepted
    assert refused_by(owner, TICK, [AGENCY, role, "staff.manage", "agency"]) == (
        "role_permission_tick_uq"
    )


def test_permission_scopes_are_closed(owner: "psycopg.Cursor[Any]") -> None:
    sql = "INSERT INTO permission (code, scope) VALUES (%s, %s)"
    assert refused_by(owner, sql, ["client.view", "global"]) == "permission_scope_known"


def test_a_role_with_a_tick_cannot_be_deleted(owner: "psycopg.Cursor[Any]") -> None:
    role = add_role(owner, "Staff")
    owner.execute(TICK, [AGENCY, role, "client.view", "own"])
    sql = "DELETE FROM role WHERE id = %s"
    assert refused_by(owner, sql, [role]) == "role_permission_role_id_fk"


@pytest.mark.parametrize(
    "name",
    ["", "x" * 65, "a\tb", "a\nb", "a\x7fb", "a\x85b"],
    ids=["empty", "65-chars", "tab", "newline", "del", "c1-nel"],
)
def test_role_names_are_1_to_64_characters_without_control_characters(
    owner: "psycopg.Cursor[Any]", name: str
) -> None:
    assert refused_by(owner, ROLE, [AGENCY, name, False]).startswith("role_name_")


def test_role_names_are_unique_per_agency_ignoring_case(owner: "psycopg.Cursor[Any]") -> None:
    add_role(owner, "Unit Manager")
    add_role(owner, "Ünit manager " + "é" * 50)  # 64 characters, more bytes: accepted
    assert refused_by(owner, ROLE, [AGENCY, "unit MANAGER", False]) == "role_agency_name_uq"
    add_role(owner, "unit manager", agency=B)  # another agency may use the name


def test_one_system_role_per_agency(owner: "psycopg.Cursor[Any]") -> None:
    add_role(owner, "Owner", is_system=True)
    assert refused_by(owner, ROLE, [AGENCY, "Second owner", True]) == "role_one_system_per_agency"
    add_role(owner, "Owner", agency=B, is_system=True)


def separate(sql: str, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchall()


@pytest.mark.parametrize("table", TABLES)
def test_app_role_holds_select_only(table: str) -> None:
    held = {
        privilege
        for privilege in TABLE_PRIVILEGES
        if separate("SELECT has_table_privilege(%s, %s, %s)", APP_ROLE, table, privilege)[0][0]
    }
    assert held == {"SELECT"}


def test_the_only_grants_are_skiw_app_select() -> None:
    rows = separate(
        "SELECT c.relname, c.relowner::regrole::text, a.grantee::regrole::text, a.privilege_type"
        " FROM pg_class c, aclexplode(c.relacl) a"
        " WHERE c.oid = ANY(%s::regclass[]) AND a.grantee <> c.relowner",
        list(TABLES),
    )
    assert sorted(rows) == [(table, "skiw_migrator", APP_ROLE, "SELECT") for table in TABLES]
