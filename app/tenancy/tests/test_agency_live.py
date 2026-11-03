"""The tenant root `agency` and the migrate-time seed (spec §4.1, §4.2 schema check (2); plan
M4c-5, owner Q2 (a); PROJECT §9 second-agency gate). X is the configured agency `make migrate`
seeded; A and B are committed by `insert_agency` before each test and kept (no test flushes; plan
M4c-5), until test_guard_schema_live's migrate-back drops the table and the seed refills it with X
only. Rows are read as skiw_app through with_agency(), or as the migrator inside a rolled-back
NO FORCE block."""

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from django.core.management.base import CommandError
from django.db import ProgrammingError, connection
from django.test import Client

from tenancy import binding, seed
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MANAGE = Path(__file__).resolve().parents[2] / "manage.py"
A = uuid.UUID("aaaaaaaa-0000-4000-8000-0000000000a1")
B = uuid.UUID("bbbbbbbb-0000-4000-8000-0000000000b1")
PREDICATE = "(id = ( SELECT guard.current_agency() AS current_agency))"


def configured() -> uuid.UUID:
    return uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])


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


def migrate(**env: str) -> subprocess.CompletedProcess[str]:
    run_env = {**os.environ, "DATABASE_URL": os.environ["MIGRATION_DATABASE_URL"], **env}
    command = [sys.executable, str(MANAGE), "migrate"]
    return subprocess.run(command, env=run_env, capture_output=True, text=True, check=False)


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


def test_make_migrate_seeded_the_configured_agency() -> None:
    with with_agency(configured()), connection.cursor() as cursor:
        cursor.execute("SELECT id, name, timezone, data_region FROM agency")
        rows = cursor.fetchall()
    assert rows == [
        (configured(), os.environ["SKIW_DEPLOYMENT_AGENCY_NAME"], "Asia/Kuala_Lumpur", "MY")
    ]


def test_the_seed_is_idempotent() -> None:
    before = stored()
    with migrator() as conn, conn.transaction(), conn.cursor() as cursor:
        assert seed.seed_deployment_agency(cursor, configured(), "ignored") is False
    assert stored() == before and forced()
    assert migrate().returncode == 0
    assert stored() == before and forced()


def test_an_empty_table_gets_the_configured_agency() -> None:
    """The branch every fresh database takes (CI's first `make migrate`), here inside a
    transaction that empties the table and rolls back."""
    other = uuid.uuid4()
    with migrator() as conn, conn.transaction(force_rollback=True), conn.cursor() as cursor:
        seed._lift(cursor)
        cursor.execute("DELETE FROM agency")
        seed._restore(cursor)
        assert seed.seed_deployment_agency(cursor, other, "Fresh") is True
        seed._lift(cursor)
        assert seed.stored_ids(cursor) == {other}
        seed._restore(cursor)
    assert other not in stored()


def test_a_seed_failure_after_no_force_leaves_force_on(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(cursor: Any) -> set[uuid.UUID]:
        assert cursor.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'agency'")
        raise RuntimeError("injected")

    monkeypatch.setattr(seed, "stored_ids", fail)
    with (
        pytest.raises(RuntimeError, match="injected"),
        migrator() as conn,
        conn.transaction(),
        conn.cursor() as cursor,
    ):
        seed.seed_deployment_agency(cursor, uuid.uuid4(), "Never")
    assert forced()


def test_a_second_agency_id_stops_migrate_and_writes_nothing() -> None:
    before, other = stored(), uuid.uuid4()
    result = migrate(SKIW_DEPLOYMENT_AGENCY_ID=str(other))
    assert result.returncode != 0
    assert str(other) in result.stderr and "PROJECT §9" in result.stderr
    assert stored() == before and other not in before
    assert forced()


@pytest.mark.parametrize("value", ["", "not-a-uuid", "LIST"], ids=["empty", "malformed", "list"])
def test_a_missing_list_or_malformed_id_stops_migrate(value: str) -> None:
    before = stored()
    if value == "LIST":
        value = f"{configured()},{uuid.uuid4()}"
    result = migrate(SKIW_DEPLOYMENT_AGENCY_ID=value)
    assert result.returncode != 0 and "SKIW_DEPLOYMENT_AGENCY_ID" in result.stderr
    assert stored() == before


def test_the_seed_refuses_a_non_migrator_role() -> None:
    with (
        psycopg.connect(os.environ["DATABASE_URL"]) as conn,
        conn.cursor() as cursor,
        pytest.raises(CommandError, match="only as skiw_migrator"),
    ):
        seed.seed_deployment_agency(cursor, configured(), "x")


def test_the_seed_refuses_autocommit() -> None:
    with migrator() as conn:
        conn.autocommit = True
        with pytest.raises(RuntimeError, match="inside a transaction"):
            seed.seed_deployment_agency(conn.cursor(), configured(), "x")
    assert forced()


def test_skiw_app_sees_only_the_bound_agency() -> None:
    assert visible() == []  # no token: the verifier gives NULL
    for agency in (A, B, configured()):
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


def test_readyz_is_503_when_the_agency_row_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_ID", str(uuid.uuid4()))
    assert Client().get("/readyz").status_code == 503


def test_readyz_is_503_when_the_token_key_differs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(binding, "_token_keys", lambda: ((1, os.urandom(32)),))
    assert Client().get("/readyz").status_code == 503
