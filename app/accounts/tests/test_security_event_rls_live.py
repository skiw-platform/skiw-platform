"""`security_event` agency isolation (slice spec Decision 33, owner Q6; §7 "Agency B reads or writes
agency A's change events"; plan row M4r-1c-i), as skiw_app in three contexts: agency A's token, B's
and none. The owner plants one pre-tenant row and a change row for A and for B under
transaction-local NO FORCE and deletes them afterwards; rows the writers add stay (skiw_app may not
delete, TEN-03), as in the other auth tests. The TEN-08 harness case is in isolation_cases.py and
the grant audit in jobs/tests/test_queue_grants.py."""

import os
import secrets
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from accounts.auth.events import KINDS, record_event
from tenancy import seed
from tenancy.binding import with_agency
from tenancy.check import SECURITY_EVENT, check
from tenancy.tests.isolation import A, B

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

CONTEXTS = {"A": A, "B": B, "none": None}
SEEN = {"A": {"pre", "A"}, "B": {"pre", "B"}, "none": {"pre"}}
INSERT = (
    "INSERT INTO security_event (id, at, kind, agency_id, email_hmac, ip_hmac, details_json)"
    " VALUES (%s, now(), %s, %s, %s, %s, '{}')"
)
HMAC = secrets.token_bytes(32)
AGENCY_CHECK, HMAC_CHECK = "security_event_change_kind_agency", "security_event_change_kind_no_hmac"


def bound(context: str) -> AbstractContextManager[Any]:
    agency = CONTEXTS[context]
    return transaction.atomic() if agency is None else with_agency(agency)


def as_owner(statement: str, params: list[Any]) -> list[tuple[Any, ...]]:
    """`statement` committed by the owner under NO FORCE, which is back on before the commit."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        forced = "SELECT relforcerowsecurity FROM pg_class WHERE oid = 'security_event'::regclass"
        assert conn.execute(forced).fetchone() == (True,), "FORCE must be on before it is lifted"
        conn.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
        cursor = conn.execute(statement, params)
        rows = cursor.fetchall() if cursor.description else []
        conn.execute("ALTER TABLE security_event FORCE ROW LEVEL SECURITY")
    return rows


@pytest.fixture(scope="module")
def planted() -> Iterator[dict[str, uuid.UUID]]:
    rows = {"pre": uuid.uuid4(), "A": uuid.uuid4(), "B": uuid.uuid4()}
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        seed.insert_agency(cursor, A, "Isolation A")
        seed.insert_agency(cursor, B, "Isolation B")
    as_owner(INSERT, [rows["pre"], "login.failed", None, HMAC, None])
    for name in ("A", "B"):
        as_owner(INSERT, [rows[name], "role.created", CONTEXTS[name], None, None])
    yield rows
    as_owner("DELETE FROM security_event WHERE id = ANY(%s)", [list(rows.values())])


def sqlstate(action: Callable[[], object]) -> tuple[str | None, str | None]:
    """The SQLSTATE and constraint name of the error `action` raises."""
    with pytest.raises(DatabaseError) as raised:
        action()
    cause = raised.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate, cause.diag.constraint_name


def app_insert(context: str, kind: str, agency: uuid.UUID | None, *hmacs: bytes | None) -> None:
    """One INSERT as skiw_app in `context`, rolled back if it passes."""
    email, ip = (*hmacs, None, None)[:2]
    with bound(context), connection.cursor() as cursor:
        cursor.execute(INSERT, [uuid.uuid4(), kind, agency, email, ip])
        transaction.set_rollback(True)


def app_count(sql: str, params: list[Any]) -> int:
    """A count as skiw_app with no token (pre-tenant rows only)."""
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return int(cursor.fetchone()[0])


@pytest.mark.parametrize("context", CONTEXTS)
def test_each_context_reads_the_pre_tenant_rows_and_only_its_own_change_rows(
    planted: dict[str, uuid.UUID], context: str
) -> None:
    with bound(context), connection.cursor() as cursor:
        cursor.execute("SELECT id FROM security_event WHERE id = ANY(%s)", [list(planted.values())])
        seen = {row for (row,) in cursor.fetchall()}
    assert seen == {planted[name] for name in SEEN[context]}


@pytest.mark.parametrize(
    ("context", "agency"), [("A", "B"), ("B", "A"), ("none", "A"), ("none", "B")]
)
def test_a_change_row_for_another_agency_or_with_no_token_is_refused(
    context: str, agency: str
) -> None:
    refused = sqlstate(lambda: app_insert(context, "role.created", CONTEXTS[agency]))
    assert refused == ("42501", None)


@pytest.mark.parametrize("context", ["A", "B"])
def test_a_change_row_for_the_own_agency_passes_the_policies(context: str) -> None:
    app_insert(context, "role.created", CONTEXTS[context])  # until M4r-1c-ii's shape trigger


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE security_event SET kind = kind",
        "DELETE FROM security_event",
        "TRUNCATE security_event",
    ],
)
def test_no_context_updates_deletes_or_truncates(context: str, statement: str) -> None:
    def run() -> None:
        with bound(context), connection.cursor() as cursor:
            cursor.execute(statement)

    assert sqlstate(run) == ("42501", None)


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", sorted(KINDS))
def test_record_event_writes_its_null_agency_row_in_every_context(context: str, kind: str) -> None:
    email = secrets.token_bytes(32)
    if CONTEXTS[context] is None:
        record_event(kind, email, HMAC, {"count": 1})  # autocommit, as factor_failed runs it
    else:
        with bound(context):
            record_event(kind, email, HMAC, {"count": 1})
    found = "SELECT count(*) FROM security_event WHERE email_hmac = %s AND kind = %s"
    assert app_count(found + " AND agency_id IS NULL", [email, kind]) == 1


LOOKUPS: dict[str, tuple[str, Callable[[], str | bytes]]] = {
    "login.lookup": ("SELECT guard.auth_lookup_login(%s)", lambda: f"{uuid.uuid4()}@example.test"),
    "passkey.lookup": ("SELECT guard.auth_lookup_credential(%s)", lambda: secrets.token_bytes(32)),
}


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", LOOKUPS)
def test_the_lookup_definers_write_their_null_agency_row_in_every_context(
    context: str, kind: str
) -> None:
    query, key = LOOKUPS[kind]
    count = "SELECT count(*) FROM security_event WHERE kind = %s AND agency_id IS NULL"
    before = app_count(count, [kind])
    with bound(context), connection.cursor() as cursor:
        cursor.execute(query, [key()])
    assert app_count(count, [kind]) == before + 1


CHECK_CASES = {
    "change kind with no agency": ("role.created", None, None, None, AGENCY_CHECK),
    "pre-tenant kind with an agency": ("login.failed", A, None, None, AGENCY_CHECK),
    "change kind with an email HMAC": ("role.created", A, HMAC, None, HMAC_CHECK),
    "change kind with an IP HMAC": ("role.created", A, None, HMAC, HMAC_CHECK),
}


@pytest.mark.parametrize("case", CHECK_CASES)
def test_the_check_refuses_a_row_the_policies_let_through(case: str) -> None:
    kind, agency, email, ip, constraint = CHECK_CASES[case]
    assert sqlstate(lambda: app_insert("A", kind, agency, email, ip)) == ("23514", constraint)


def test_force_binds_the_owner_too(planted: dict[str, uuid.UUID]) -> None:
    """No policy names skiw_migrator: under FORCE it reads nothing and may insert nothing."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT count(*) FROM security_event WHERE id = ANY(%s)", [list(planted.values())]
        ).fetchall()
        assert rows == [(0,)]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(INSERT, [uuid.uuid4(), "login.failed", None, None, None])


P = "agency_id IS NULL OR agency_id = (SELECT guard.current_agency())"
OWN = "agency_id = (SELECT guard.current_agency())"
POLICIES = "policies are not exactly the Decision 33 set"
MUTANTS = {
    "FORCE dropped": ("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY", ["RLS not forced"]),
    "RLS disabled": ("ALTER TABLE security_event DISABLE ROW LEVEL SECURITY", ["RLS not enabled"]),
    "restrictive policy dropped": (
        "DROP POLICY security_event_tenant ON security_event",
        [POLICIES],
    ),
    "no IS NULL branch": (
        f"ALTER POLICY security_event_tenant ON security_event USING ({OWN}) WITH CHECK ({OWN})",
        [POLICIES],
    ),
    "no own-agency branch": (
        "ALTER POLICY security_event_sel ON security_event USING (agency_id IS NULL)",
        [POLICIES],
    ),
    "extra permissive policy": (
        "CREATE POLICY security_event_x ON security_event FOR SELECT TO skiw_app USING (true)",
        [POLICIES, "policy security_event_x has a true predicate"],
    ),
    "UPDATE policy added": (
        f"CREATE POLICY security_event_upd ON security_event FOR UPDATE TO skiw_app USING ({P})",
        [POLICIES],
    ),
    "DELETE policy added": (
        f"CREATE POLICY security_event_del ON security_event FOR DELETE TO skiw_app USING ({P})",
        [POLICIES],
    ),
    "policy for another role": (
        f"CREATE POLICY security_event_ro ON security_event FOR SELECT TO skiw_readonly"
        f" USING ({P})",
        [POLICIES],
    ),
    "kind-agency CHECK dropped": (
        f"ALTER TABLE security_event DROP CONSTRAINT {AGENCY_CHECK}",
        [f"CHECK {AGENCY_CHECK} missing or changed"],
    ),
    "HMAC CHECK dropped": (
        f"ALTER TABLE security_event DROP CONSTRAINT {HMAC_CHECK}",
        [f"CHECK {HMAC_CHECK} missing or changed"],
    ),
    "FK dropped": (
        "ALTER TABLE security_event DROP CONSTRAINT security_event_agency_fk",
        ["no FK (agency_id) to agency(id)"],
    ),
}


@pytest.mark.parametrize("mutant", [None, *MUTANTS])
def test_the_schema_check_flags_each_mutant(mutant: str | None) -> None:
    """Each mutant as DDL by the owner in a transaction that is rolled back; None: the real one."""
    statement, expected = MUTANTS[mutant] if mutant else ("SELECT 1", [])
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
    ):
        conn.execute(statement)
        found = [v.reason for v in check(conn, schemas=["public"]) if v.table == SECURITY_EVENT]
    assert found == sorted(expected)
