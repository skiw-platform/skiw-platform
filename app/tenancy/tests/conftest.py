"""Live fixtures shared by the tenancy tests (plans M4c-4a, M4c-4b)."""

import os
from collections.abc import Iterator
from typing import LiteralString

import psycopg
import pytest
from pytest_django import DjangoDbBlocker

from tenancy.ddl import owner_role
from tenancy.tests.test_token import VECTOR_KEY

ACTIVE, RETIRED, ABSENT = 999_996, 999_997, 999_998


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
