"""The tenant root `agency` (spec §4.1, §4.2 schema check (2); plan M4c-5). A and B are committed
by `insert_agency` before each test and kept (no test flushes), until test_guard_schema_live's
migrate-back drops the table. Rows are read as skiw_app through with_agency(), or as the migrator
inside a rolled-back NO FORCE block."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from django.core.management.base import CommandError
from django.db import ProgrammingError, connection

from tenancy import seed
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

A = uuid.UUID("aaaaaaaa-0000-4000-8000-0000000000a1")
B = uuid.UUID("bbbbbbbb-0000-4000-8000-0000000000b1")
PREDICATE = "(id = ( SELECT guard.current_agency() AS current_agency))"


def migrator() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["MIGRATION_DATABASE_URL"])


def stored() -> set[uuid.UUID]:
    """Every agency id, read as the owner with FORCE lifted in a transaction that rolls back."""
    with migrator() as conn, conn.transaction(force_rollback=True), conn.cursor() as cursor:
        seed._lift(cursor)
        return seed.stored_ids(cursor)


def forced() -> bool:
    with migrator() as conn:
        row = conn.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'agency'")
        return bool(row.fetchone() == (True,))


def visible() -> list[uuid.UUID]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM agency ORDER BY id")
        return [agency for (agency,) in cursor.fetchall()]


@pytest.fixture(autouse=True)
def agencies() -> Iterator[None]:
    with migrator() as conn, conn.transaction(), conn.cursor() as cursor:
        seed.insert_agency(cursor, A, "Agency A")
        seed.insert_agency(cursor, B, "Agency B")
    yield
    assert forced()


def test_insert_agency_is_idempotent_and_uses_the_column_defaults() -> None:
    before = stored()
    assert {A, B} <= before
    with migrator() as conn, conn.transaction(), conn.cursor() as cursor:
        seed.insert_agency(cursor, A, "Renamed")
    assert stored() == before and forced()
    with with_agency(A), connection.cursor() as cursor:
        cursor.execute("SELECT name, timezone, data_region FROM agency")
        assert cursor.fetchall() == [("Agency A", "Asia/Kuala_Lumpur", "MY")]


def test_under_force_the_owner_itself_sees_no_rows() -> None:
    """Why every write lifts FORCE first: no policy names the migrator."""
    with migrator() as conn:
        assert conn.execute("SELECT count(*) FROM agency").fetchall() == [(0,)]


def test_a_failure_after_no_force_leaves_force_on() -> None:
    before = stored()
    with (
        pytest.raises(psycopg.errors.NotNullViolation),
        migrator() as conn,
        conn.transaction(),
        conn.cursor() as cursor,
    ):
        seed.insert_agency(cursor, uuid.uuid4(), None)  # type: ignore[arg-type]
    assert forced() and stored() == before


def test_writes_refuse_a_non_migrator_role() -> None:
    with (
        psycopg.connect(os.environ["DATABASE_URL"]) as conn,
        conn.cursor() as cursor,
        pytest.raises(CommandError, match="only as skiw_migrator"),
    ):
        seed.insert_agency(cursor, uuid.uuid4(), "x")


def test_writes_refuse_autocommit() -> None:
    with migrator() as conn:
        conn.autocommit = True
        with pytest.raises(RuntimeError, match="inside a transaction"):
            seed.insert_agency(conn.cursor(), uuid.uuid4(), "x")
    assert forced()


def test_skiw_app_sees_only_the_bound_agency() -> None:
    assert visible() == []  # no token: the verifier gives NULL
    for agency in (A, B):
        with with_agency(agency):
            assert visible() == [agency]


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO agency (id, name) VALUES (%s, 'x')",
        "UPDATE agency SET name = 'x' WHERE id = %s",
        "DELETE FROM agency WHERE id = %s",
    ],
    ids=["insert", "update", "delete"],
)
def test_skiw_app_cannot_write_agency_even_its_own(statement: str) -> None:
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        with_agency(A),
        connection.cursor() as cursor,
    ):
        cursor.execute(statement, [A])


def test_the_table_matches_the_root_template() -> None:
    with migrator() as conn:
        assert conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity, relowner::regrole::text, relacl::text"
            " FROM pg_class WHERE oid = 'public.agency'::regclass"
        ).fetchall() == [
            (
                True,
                True,
                "skiw_migrator",
                "{skiw_migrator=arwdDxtm/skiw_migrator,skiw_app=r/skiw_migrator}",
            )
        ]
        assert conn.execute(
            "SELECT policyname, permissive, cmd, roles::text, qual, with_check FROM pg_policies"
            " WHERE schemaname = 'public' AND tablename = 'agency' ORDER BY policyname"
        ).fetchall() == [
            ("agency_sel", "PERMISSIVE", "SELECT", "{skiw_app}", PREDICATE, None),
            ("agency_tenant", "RESTRICTIVE", "ALL", "{skiw_app}", PREDICATE, PREDICATE),
        ]
