"""Live fixtures shared by the tenancy tests (plans M4c-4a, M4c-4b, M4c-7a, M4c-7b)."""

import os
from collections.abc import Iterator
from typing import Any, LiteralString

import psycopg
import pytest
from pytest_django import DjangoDbBlocker

from tenancy import seed
from tenancy.ddl import owner_role
from tenancy.template import tenant_table_sql
from tenancy.tests.isolation import COMMANDS, A, B
from tenancy.tests.isolation_cases import SCHEMA
from tenancy.tests.test_token import VECTOR_KEY

ACTIVE, RETIRED, ABSENT = 999_996, 999_997, 999_998
COLUMNS = "id uuid PRIMARY KEY, agency_id uuid NOT NULL"


def migrator() -> "psycopg.Connection[Any]":
    return psycopg.connect(os.environ["MIGRATION_DATABASE_URL"])


def build(conn: "psycopg.Connection[Any]", table: str, columns: str, **kwargs: Any) -> None:
    conn.execute(f"CREATE TABLE {table} ({columns}, UNIQUE (agency_id, id))")
    for forward, _ in tenant_table_sql(table, **kwargs):
        for statement in forward:
            conn.execute(statement)


@pytest.fixture(scope="session", autouse=True)
def no_fixture_leftover(request: pytest.FixtureRequest) -> None:
    """Before the first tenancy test of a live run, drop a fixture schema an interrupted run left
    behind (PR 101 review R1 P3): the compliant pair passes the schema check, but its policies
    call guard.current_agency(), so test_guard_schema_live could not migrate back past it."""
    if any(item.get_closest_marker("live") for item in request.session.items):
        with migrator() as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture(scope="module")
def fixture_pair() -> Iterator[None]:
    """The fixture pair (`isolation_cases.py`) built from tenant_table() SQL for one module, then
    dropped; leftovers are dropped first. A and B are committed with `insert_agency` and kept."""
    with migrator() as conn, conn.transaction():
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {SCHEMA}")
        conn.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO skiw_app")
        conn.execute(f"SET LOCAL search_path = {SCHEMA}, public")
        build(conn, "parent", COLUMNS, commands=COMMANDS)
        build(
            conn,
            "child",
            f"{COLUMNS}, parent_id uuid NOT NULL",
            commands={"SELECT", "INSERT"},
            composite_fks=[("parent_id", "parent")],
        )
        with conn.cursor() as cursor:
            seed.insert_agency(cursor, A, "Isolation A")
            seed.insert_agency(cursor, B, "Isolation B")
    try:
        yield
    finally:
        with migrator() as conn:
            conn.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


@pytest.fixture
def vector_keys() -> Iterator[None]:
    """The vector key under two high test versions, one active and one retired, committed as the
    owner (skiw_app sees only committed rows) and deleted again afterwards. ABSENT stays unused."""

    def write(statement: LiteralString, *params: object) -> None:
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
            cursor = psycopg.Cursor(conn)
            with owner_role(cursor, "skiw_tenant_guard"):
                cursor.execute(statement, params)

    write(
        "INSERT INTO guard.tenant_mac_key (version, key, retired_at)"
        " VALUES (%s, %s, NULL), (%s, %s, now())",
        ACTIVE, VECTOR_KEY, RETIRED, VECTOR_KEY,
    )  # fmt: skip
    try:
        yield
    finally:
        write("DELETE FROM guard.tenant_mac_key WHERE version = ANY(%s)", [ACTIVE, RETIRED])


@pytest.fixture(scope="session")
def django_db_setup() -> None:
    """Use the database `make migrate` prepared; skiw_app may not create a test database."""


@pytest.fixture
def live_db(django_db_setup: None, django_db_blocker: DjangoDbBlocker) -> Iterator[None]:
    """The real Django connection (skiw_app) in autocommit. with_agency() writes no rows."""
    with django_db_blocker.unblock():
        yield
