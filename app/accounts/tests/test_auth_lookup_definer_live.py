"""`tenancy.ddl.as_owner` end to end with the accounts.0003 grant (plan M4c-2b, A2): a SECURITY
DEFINER function in `guard`, owned by skiw_auth_lookup, writes `security_event` when skiw_app
calls it, keeps its owner and ACL through `CREATE OR REPLACE`, and is dropped as its owner. It
lives here because its SQL names `security_event` (Semgrep `auth-tables-accounts-only`).

skiw_app has no USAGE on `guard` until M4c-4a, and a call from the skiw_app login sees only
committed state, so the probe commits a USAGE grant for the call and the fixture revokes it,
drops the function and deletes the probe rows, also when the test fails."""

import os
import uuid
from collections.abc import Iterator
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql

from tenancy.ddl import GUARD_OWNERS, as_owner

pytestmark = pytest.mark.live

LOOKUP = "skiw_auth_lookup"
FUNCTION = "guard.probe_definer()"
KINDS = ("probe.definer", "probe.replaced")


def definition(kind: str) -> str:
    # No RETURNING: it needs SELECT, and the owner holds INSERT only (accounts.0003, TEN-03).
    # S608: only this module's constant kinds are interpolated, never input.
    return (
        f"FUNCTION {FUNCTION} RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER"  # noqa: S608
        " SET search_path = pg_catalog, pg_temp AS $$DECLARE event_id uuid :="
        " pg_catalog.gen_random_uuid(); BEGIN INSERT INTO public.security_event"
        " (id, at, kind, details_json) VALUES (event_id, pg_catalog.now(),"
        f" '{kind}', pg_catalog.jsonb_build_object('current_user', current_user,"
        " 'session_user', session_user)); RETURN event_id; END$$"
    )


CREATE = as_owner(
    LOOKUP,
    [
        f"CREATE {definition(KINDS[0])}",
        f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC",
        f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO skiw_app",
    ],
    [f"DROP FUNCTION {FUNCTION}"],
)
REPLACE = as_owner(LOOKUP, [f"CREATE OR REPLACE {definition(KINDS[1])}"], [])


def migrate_with(statements: object) -> None:
    """Run a RunSQL statement list in one transaction as the migrator, as `migrate` does."""
    assert isinstance(statements, list | tuple)
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        for statement in statements:
            assert isinstance(statement, str)
            conn.execute(sql.SQL(statement))


def as_migrator(query: LiteralString, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall() if cursor.description else []


def call_as_app() -> uuid.UUID:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        row = conn.execute("SELECT guard.probe_definer()").fetchone()
    assert row is not None
    event_id: uuid.UUID = row[0]
    return event_id


def function_row() -> list[tuple[Any, ...]]:
    return as_migrator(
        "SELECT proowner::regrole::text, prosecdef, proconfig, proacl::text FROM pg_proc"
        " WHERE oid = to_regprocedure(%s)",
        FUNCTION,
    )


def events(event_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return as_migrator("SELECT kind, details_json FROM security_event WHERE id = %s", event_id)


@pytest.fixture
def probe() -> Iterator[None]:
    assert function_row() == []
    try:
        yield
    finally:
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
            conn.execute("REVOKE USAGE ON SCHEMA guard FROM skiw_app")
            conn.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA guard FROM {}").format(sql.Identifier(LOOKUP))
            )
            conn.execute("DELETE FROM security_event WHERE kind = ANY(%s)", (list(KINDS),))
            owner = conn.execute(
                "SELECT proowner::regrole::text FROM pg_proc WHERE oid = to_regprocedure(%s)",
                (FUNCTION,),
            ).fetchone()
            if owner is not None:
                if owner[0] in GUARD_OWNERS:
                    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(owner[0])))
                conn.execute(sql.SQL(f"DROP FUNCTION {FUNCTION}"))
        assert function_row() == []
        assert as_migrator(
            "SELECT has_schema_privilege('skiw_app', 'guard', 'USAGE'),"
            " count(*) FROM security_event WHERE kind = ANY(%s)",
            list(KINDS),
        ) == [(False, 0)]


@pytest.mark.usefixtures("probe")
def test_a_definer_function_made_through_as_owner_writes_as_its_owner_and_keeps_it() -> None:
    migrate_with(CREATE.sql)
    created = function_row()
    assert [row[:3] for row in created] == [(LOOKUP, True, ["search_path=pg_catalog, pg_temp"])]
    assert created[0][3] == "{skiw_auth_lookup=X/skiw_auth_lookup,skiw_app=X/skiw_auth_lookup}"

    # The negative control: without USAGE on guard skiw_app cannot reach it (M4c-4a grants it).
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="schema guard"):
        call_as_app()
    as_migrator("GRANT USAGE ON SCHEMA guard TO skiw_app")  # the fixture revokes it

    who = {"current_user": LOOKUP, "session_user": "skiw_app"}
    assert events(call_as_app()) == [(KINDS[0], who)]

    migrate_with(REPLACE.sql)  # A2: the replace keeps the owner and the EXECUTE grants
    assert function_row() == created
    assert events(call_as_app()) == [(KINDS[1], who)]

    migrate_with(CREATE.reverse_sql)
    assert function_row() == []
