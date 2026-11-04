"""TEN-08 isolation tests generated from every registered case, the coverage and composite-FK
checks, and the proof (plan M4c-7a; DECISIONS "M4c-7a"), on the conftest's fixture pair."""

import uuid
from collections.abc import Mapping

import pytest
from django.db.backends.utils import CursorWrapper

from tenancy.check import check, tenant_tables
from tenancy.tests import isolation
from tenancy.tests.conftest import COLUMNS, build, migrator
from tenancy.tests.isolation import COMMANDS, IsolationCase
from tenancy.tests.isolation_cases import SCHEMA

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db", "fixture_pair")]

TEST_ONLY = ("public.jobs_probe", "public.files_probe")
CASES = isolation.registry()
LEAKY = f"{SCHEMA}.leaky"


GENERATED = [
    (table, name)
    for table, case in sorted(CASES.items())
    for name, (_, applies) in isolation.CHECKS.items()
    if applies(case)
]


@pytest.mark.parametrize(("table", "check"), GENERATED, ids=[f"{t}:{c}" for t, c in GENERATED])
def test_isolation(table: str, check: str) -> None:
    isolation.CHECKS[check][0](CASES, CASES[table])


FOREIGN_KEYS = [(table, column) for table, case in sorted(CASES.items()) for column in case.parents]


@pytest.mark.parametrize(("table", "column"), FOREIGN_KEYS)
def test_a_child_of_another_agencys_parent_fails_the_composite_fk(table: str, column: str) -> None:
    isolation.check_cross_fk(CASES, CASES[table], column)


def test_the_fixture_pair_passes_the_schema_check() -> None:
    with migrator() as conn:
        assert check(conn, schemas=[SCHEMA]) == []


def uncovered() -> list[str]:
    with migrator() as conn:
        tables = tenant_tables(conn, extra_allowed=TEST_ONLY)
    assert {f"{SCHEMA}.parent", f"{SCHEMA}.child"} <= tables  # the classification is not empty
    return sorted(tables - set(CASES))


def test_every_tenant_table_has_a_case() -> None:
    missing = uncovered()
    assert missing == [], f"tenant tables without an isolation case (TEN-08): {missing}"


def test_the_fixture_pair_runs_every_check() -> None:
    assert {check for table, check in GENERATED if table.startswith(SCHEMA)} == set(
        isolation.CHECKS
    )


COMPOSITE_FKS = """
    SELECT cn.nspname || '.' || c.relname, pn.nspname || '.' || p.relname,
           ARRAY(SELECT a.attname::text FROM unnest(k.conkey) AS key(num)
                 JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = key.num)
    FROM pg_constraint k
    JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace cn ON cn.oid = c.relnamespace
    JOIN pg_class p ON p.oid = k.confrelid JOIN pg_namespace pn ON pn.oid = p.relnamespace
    WHERE k.contype = 'f'
"""


def test_every_composite_fk_is_a_declared_parent() -> None:
    """Each composite FK in pg_constraint between tenant tables is a case's `parents` entry, so it
    gets a cross-agency test, and each declared parent is a real FK."""
    with migrator() as conn:
        tables = tenant_tables(conn, extra_allowed=TEST_ONLY)
        rows = conn.execute(COMPOSITE_FKS).fetchall()
    found = {
        (child, next(c for c in columns if c != "agency_id"), parent)
        for child, parent, columns in rows
        if child in tables and parent in tables and "agency_id" in columns and len(columns) == 2
    }
    declared = {
        (table, column, parent)
        for table, case in CASES.items()
        for column, parent in case.parents.items()
    }
    assert found == declared


def _leaky(cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO tenancy_fixture.leaky (id, agency_id) VALUES (%s, %s)", [row, agency]
    )
    return row


def test_the_harness_fails_on_a_table_that_leaks() -> None:
    """The proof: a template table whose policies are opened with `USING (true)` must fail the
    generated read test because A sees B's row, as skiw_app through with_agency(). Committed (and
    dropped before and after), because skiw_app cannot see the migrator's open transaction."""
    with migrator() as conn, conn.transaction():
        conn.execute(f"DROP TABLE IF EXISTS {LEAKY}")
        conn.execute(f"SET LOCAL search_path = {SCHEMA}, public")
        build(conn, "leaky", COLUMNS, commands=COMMANDS)
        conn.execute("DROP POLICY leaky_tenant ON leaky")
        conn.execute(
            "CREATE POLICY leaky_tenant ON leaky AS RESTRICTIVE FOR ALL TO skiw_app"
            " USING (true) WITH CHECK (true)"
        )
        conn.execute("CREATE POLICY leaky_open ON leaky FOR SELECT TO skiw_app USING (true)")
    try:
        assert uncovered() == [LEAKY]  # the coverage test names an unregistered tenant table
        case = IsolationCase(LEAKY, _leaky, COMMANDS)
        with pytest.raises(AssertionError, match=f"{LEAKY}: under A, 1 of B's rows visible"):
            isolation.CHECKS["read"][0]({**CASES, LEAKY: case}, case)  # the generated read test
    finally:
        with migrator() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {LEAKY}")
