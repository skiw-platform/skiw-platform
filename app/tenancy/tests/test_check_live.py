"""The schema check against pass and fail fixtures (plan M4c-6b). Each case is DDL in the scratch
schema `chk`, as the migrator, in a transaction that rolls back. `search_path` is `chk, public`,
so `tenant_table()` SQL and its `agency` FK resolve as in a real migration."""

import os
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest

from tenancy.check import Violation, check
from tenancy.template import tenant_table_sql

pytestmark = pytest.mark.live

TEST_ONLY = ("public.jobs_probe", "public.files_probe")
ALL = {"SELECT", "INSERT", "UPDATE", "DELETE"}
TENANT_COLUMNS = "id uuid PRIMARY KEY, agency_id uuid NOT NULL"


@pytest.fixture
def conn() -> Iterator["psycopg.Connection[Any]"]:
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
    ):
        conn.execute("CREATE SCHEMA chk")
        conn.execute("SET LOCAL search_path = chk, public")
        yield conn


def tenant(
    conn: "psycopg.Connection[Any]",
    table: str,
    columns: str = f"{TENANT_COLUMNS}, UNIQUE (agency_id, id)",
    **kwargs: Any,
) -> None:
    conn.execute(f"CREATE TABLE {table} ({columns})")
    for forward, _ in tenant_table_sql(table, commands=kwargs.pop("commands", ALL), **kwargs):
        for statement in forward:
            conn.execute(statement)


def scratch(conn: "psycopg.Connection[Any]") -> list[str]:
    return [str(v) for v in check(conn, schemas=["chk"])]


def test_the_real_schema_passes(conn: "psycopg.Connection[Any]") -> None:
    assert check(conn, extra_allowed=TEST_ONLY) == []


def test_compliant_tenant_tables_pass(conn: "psycopg.Connection[Any]") -> None:
    tenant(conn, "parent")
    tenant(
        conn,
        "child",
        f"{TENANT_COLUMNS}, parent_id uuid, UNIQUE (agency_id, id)",
        commands={"SELECT", "INSERT"},
        composite_fks=[("parent_id", "parent")],
    )
    assert scratch(conn) == []


def test_a_listed_global_with_agency_id_is_global(conn: "psycopg.Connection[Any]") -> None:
    """List membership comes before the agency_id rule (`bridge_session`, spec §4.1)."""
    conn.execute(
        "CREATE TABLE public.bridge_session (token_hash text PRIMARY KEY, agency_id uuid NOT NULL)"
    )
    assert check(conn, schemas=["public"], extra_allowed=TEST_ONLY) == []
    # An FK to a global is an ordinary FK (spec §4), even when the global has agency_id.
    tenant(
        conn,
        "t",
        f"{TENANT_COLUMNS}, token_hash text REFERENCES public.bridge_session,"
        " UNIQUE (agency_id, id)",
    )
    assert scratch(conn) == []


def _no_unique(conn: "psycopg.Connection[Any]") -> None:
    tenant(conn, "t", TENANT_COLUMNS)


def _agency_shaped(conn: "psycopg.Connection[Any]") -> None:
    conn.execute("CREATE TABLE agency2 (id uuid PRIMARY KEY, name text)")
    conn.execute("ALTER TABLE agency2 ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE agency2 FORCE ROW LEVEL SECURITY")
    predicate = "id = (SELECT guard.current_agency())"
    conn.execute(
        f"CREATE POLICY a2_tenant ON agency2 AS RESTRICTIVE FOR ALL TO skiw_app"
        f" USING ({predicate}) WITH CHECK ({predicate})"
    )
    conn.execute(f"CREATE POLICY a2_sel ON agency2 FOR SELECT TO skiw_app USING ({predicate})")


def _single_column_fk(conn: "psycopg.Connection[Any]") -> None:
    tenant(conn, "parent")
    tenant(
        conn,
        "child",
        f"{TENANT_COLUMNS}, parent_id uuid REFERENCES parent(id), UNIQUE (agency_id, id)",
    )


def _ddl(sql: str) -> Callable[["psycopg.Connection[Any]"], None]:
    def build(conn: "psycopg.Connection[Any]") -> None:
        conn.execute(sql)

    return build


def _policy(sql: str) -> Callable[["psycopg.Connection[Any]"], None]:
    def build(conn: "psycopg.Connection[Any]") -> None:
        tenant(conn, "t")
        conn.execute(sql)

    return build


FAIL_CASES: dict[str, tuple[Callable[["psycopg.Connection[Any]"], None], list[str]]] = {
    "undeclared table without agency_id": (
        _ddl("CREATE TABLE loose (id uuid PRIMARY KEY)"),
        ["chk.loose: not on the global list and has no agency_id column"],
    ),
    "no unique (agency_id, id)": (_no_unique, ["chk.t: no unique (agency_id, id)"]),
    "agency-shaped under another name": (
        _agency_shaped,
        ["chk.agency2: not on the global list and has no agency_id column"],
    ),
    "single-column FK to a tenant table": (
        _single_column_fk,
        [
            "chk.child: FK child_parent_id_fkey to tenant table chk.parent"
            " is not composite on agency_id"
        ],
    ),
    "current_setting('app.agency_id') policy": (
        _policy(
            "CREATE POLICY t_cs ON t FOR SELECT TO skiw_app"
            " USING (agency_id = current_setting('app.agency_id')::uuid)"
        ),
        [
            "chk.t: permissive policy t_cs is not template-shaped",
            "chk.t: policy t_cs reads current_setting directly",
        ],
    ),
    "RLS not forced": (
        _policy("ALTER TABLE t NO FORCE ROW LEVEL SECURITY"),
        ["chk.t: RLS not forced"],
    ),
    "RLS not enabled": (
        _policy("ALTER TABLE t DISABLE ROW LEVEL SECURITY"),
        ["chk.t: RLS not enabled"],
    ),
    "permissive USING (true)": (
        _policy("CREATE POLICY t_open ON t FOR SELECT TO skiw_app USING (true)"),
        [
            "chk.t: permissive policy t_open is not template-shaped",
            "chk.t: policy t_open has a true predicate",
        ],
    ),
    "PUBLIC policy with the template predicate": (
        _policy(
            "CREATE POLICY t_pub ON t FOR SELECT"
            " USING (agency_id = (SELECT guard.current_agency()))"
        ),
        [
            "chk.t: permissive policy t_pub is not template-shaped",
            "chk.t: policy t_pub applies to PUBLIC",
        ],
    ),
    "no restrictive policy": (
        _policy("DROP POLICY t_tenant ON t"),
        ["chk.t: no restrictive tenant policy with USING and WITH CHECK"],
    ),
    "restrictive policy without WITH CHECK": (
        _policy(
            "DROP POLICY t_tenant ON t;"
            " CREATE POLICY t_tenant ON t AS RESTRICTIVE FOR ALL TO skiw_app"
            " USING (agency_id = (SELECT guard.current_agency()))"
        ),
        ["chk.t: no restrictive tenant policy with USING and WITH CHECK"],
    ),
    "no FK to agency": (
        _policy("ALTER TABLE t DROP CONSTRAINT t_agency_fk"),
        ["chk.t: no FK (agency_id) to agency(id)"],
    ),
    "agency_id nullable": (
        _policy("ALTER TABLE t ALTER COLUMN agency_id DROP NOT NULL"),
        ["chk.t: agency_id is not uuid not null"],
    ),
    "unlisted view": (
        _ddl("CREATE VIEW v AS SELECT 1 AS one"),
        ["chk.v: unlisted view"],
    ),
}


@pytest.mark.parametrize("case", FAIL_CASES)
def test_a_noncompliant_table_fails(conn: "psycopg.Connection[Any]", case: str) -> None:
    build, expected = FAIL_CASES[case]
    build(conn)
    assert scratch(conn) == expected


def test_the_real_agency_fails_without_force_or_with_another_permissive_policy(
    conn: "psycopg.Connection[Any]",
) -> None:
    conn.execute("ALTER TABLE agency NO FORCE ROW LEVEL SECURITY")
    conn.execute(
        "CREATE POLICY agency_ins ON agency FOR INSERT TO skiw_app"
        " WITH CHECK (id = (SELECT guard.current_agency()))"
    )
    assert check(conn, schemas=["public"], extra_allowed=TEST_ONLY) == [
        Violation("public.agency", "RLS not forced"),
        Violation(
            "public.agency", "the tenant root needs exactly one permissive SELECT policy on id"
        ),
    ]
