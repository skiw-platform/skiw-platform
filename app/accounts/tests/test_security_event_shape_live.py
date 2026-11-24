"""`security_event_shape` (slice spec Decisions 30, 32; §7 "Other code writes or forges change
events" and "Personal data in a change event"; plan row M4r-1c-ii): a change kind written straight
into security_event is refused for every role and context; the same row written from inside a
trigger (the test-only probe trigger, event_probe) is accepted, so the depth rule is what refuses;
through the probe, every key set and value outside Decision 30 is refused. Every insert here is
rolled back. Pre-tenant kinds keep working unchanged (also test_security_event_rls_live)."""

import json
import os
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from accounts.auth.tables import CHANGE_KINDS
from accounts.tests import event_probe
from tenancy.binding import with_agency
from tenancy.tests.isolation import A, B

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

CONTEXTS = {"A": A, "B": B, "none": None}
DIRECT = (
    "INSERT INTO security_event (id, at, kind, agency_id, details_json)"
    " VALUES (%s, now(), %s, %s, %s)"
)
BY_TRIGGER = ("42501", "change event refused: written only by a trigger")
BAD_SHAPE = ("23514", "change event refused: details do not match the kind")


def bound(context: str) -> AbstractContextManager[Any]:
    agency = CONTEXTS[context]
    return transaction.atomic() if agency is None else with_agency(agency)


def app_write(context: str, statement: str, params: list[Any]) -> int:
    """`statement` as skiw_app in `context`, rolled back; the rows the transaction then sees with
    the id of params[0]."""
    with bound(context), connection.cursor() as cursor:
        cursor.execute(statement, params)
        cursor.execute("SELECT count(*) FROM security_event WHERE id = %s", [params[0]])
        transaction.set_rollback(True)
        return int(cursor.fetchone()[0])


def probe(kind: str, details: Any, context: str = "A") -> int:
    """`kind` with `details` for the context's agency (A with no token), through the probe."""
    params = [uuid.uuid4(), kind, CONTEXTS[context] or A, None, None, json.dumps(details)]
    return app_write(context, event_probe.INSERT, params)


def refusal(action: Callable[[], object]) -> tuple[str | None, str]:
    """The SQLSTATE and message of the error `action` raises."""
    with pytest.raises((DatabaseError, psycopg.Error)) as raised:
        action()
    cause = raised.value if isinstance(raised.value, psycopg.Error) else raised.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate, str(cause.diag.message_primary)


def owner_direct(kind: str) -> None:
    """A direct INSERT by the table owner under transaction-local NO FORCE, rolled back."""
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
    ):
        conn.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
        conn.execute(DIRECT, [uuid.uuid4(), kind, A, json.dumps(event_probe.details(kind))])


@pytest.mark.parametrize("context", [*CONTEXTS, "owner"])
@pytest.mark.parametrize("kind", CHANGE_KINDS)
def test_a_direct_change_kind_insert_is_refused(kind: str, context: str) -> None:
    if context == "owner":
        assert refusal(lambda: owner_direct(kind)) == BY_TRIGGER
        return
    params = [uuid.uuid4(), kind, CONTEXTS[context] or A, json.dumps(event_probe.details(kind))]
    assert refusal(lambda: app_write(context, DIRECT, params)) == BY_TRIGGER


@pytest.mark.parametrize("context", ["A", "B"])
@pytest.mark.parametrize("kind", CHANGE_KINDS)
def test_the_same_row_from_inside_a_trigger_is_accepted(kind: str, context: str) -> None:
    assert probe(kind, event_probe.details(kind), context) == 1


def test_the_root_of_the_org_tree_is_added_with_a_null_parent() -> None:
    root = {**event_probe.details("org.added"), "parent_id": None, "unit_kind": "agency"}
    assert probe("org.added", root) == 1


def _without(kind: str, key: str) -> dict[str, Any]:
    return {k: v for k, v in event_probe.details(kind).items() if k != key}


def _with(kind: str, **values: Any) -> dict[str, Any]:
    return {**event_probe.details(kind), **values}


KEYS = [(kind, key) for kind in CHANGE_KINDS for key in event_probe.details(kind)]
VALUES: dict[str, tuple[str, dict[str, Any] | list[Any] | None]] = {
    "not an object": ("role.created", []),
    "JSON null": ("role.created", None),
    "operator in capitals": ("role.created", _with("role.created", operator="Bob")),
    "operator of 33 characters": ("role.created", _with("role.created", operator="o" * 33)),
    "operator with a comma": ("role.created", _with("role.created", operator="ops,1")),
    "uuid in capitals": ("role.created", _with("role.created", role_id=str(uuid.uuid4()).upper())),
    "uuid without dashes": ("role.deleted", _with("role.deleted", role_id=uuid.uuid4().hex)),
    "uuid in braces": ("org.renamed", _with("org.renamed", org_unit_id=f"{{{uuid.uuid4()}}}")),
    "uuid as JSON null": ("role.renamed", _with("role.renamed", role_id=None)),
    "unknown line": ("role.assigned", _with("role.assigned", line="all")),
    "unknown unit kind": ("org.added", _with("org.added", unit_kind="branch")),
    "unknown permission code": ("permission.set", _with("permission.set", permission_code="x.y")),
    "pair not in the catalogue": ("permission.unset", _with("permission.unset", scope="galaxy")),
    "null parent below the root": ("org.added", _with("org.added", parent_id=None)),
    "a root with a parent": ("org.added", _with("org.added", unit_kind="agency")),
    "moved from the root position": ("org.moved", _with("org.moved", old_parent_id=None)),
}


@pytest.mark.parametrize(("kind", "key"), KEYS)
def test_a_missing_key_is_refused(kind: str, key: str) -> None:
    assert refusal(lambda: probe(kind, _without(kind, key))) == BAD_SHAPE


@pytest.mark.parametrize("kind", CHANGE_KINDS)
@pytest.mark.parametrize("extra", ["role_name", "email", "note"])
def test_an_extra_key_is_refused(kind: str, extra: str) -> None:
    assert refusal(lambda: probe(kind, _with(kind, **{extra: "Jane Doe"}))) == BAD_SHAPE


@pytest.mark.parametrize("value", ["jane@example.test", "Jane Doe", "free text, any words", 7])
@pytest.mark.parametrize(("kind", "key"), KEYS)
def test_an_email_name_free_text_or_number_is_refused(kind: str, key: str, value: Any) -> None:
    assert refusal(lambda: probe(kind, _with(kind, **{key: value}))) == BAD_SHAPE


@pytest.mark.parametrize("case", VALUES)
def test_a_value_of_the_wrong_shape_is_refused(case: str) -> None:
    kind, details = VALUES[case]
    assert refusal(lambda: probe(kind, details)) == BAD_SHAPE


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", ["login.failed", "account.locked", "factor.locked", "x.unknown"])
def test_a_pre_tenant_kind_is_written_directly_as_before(context: str, kind: str) -> None:
    """No key list and no depth rule for any other kind: pre-tenant rows stay as they were."""
    params = [uuid.uuid4(), kind, None, json.dumps({"count": 1, "free": "any text"})]
    assert app_write(context, DIRECT, params) == 1


def as_migrator(query: str, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        return conn.execute(query, params).fetchall()


def test_the_shape_function_is_an_invoker_with_a_pinned_search_path() -> None:
    assert as_migrator(
        "SELECT p.proowner::regrole::text, p.prosecdef, p.proconfig, l.lanname::text,"
        " has_function_privilege('skiw_app', p.oid, 'EXECUTE')"
        " FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang"
        " WHERE p.oid = to_regprocedure('public.security_event_shape()')"
    ) == [("skiw_migrator", False, ["search_path=pg_catalog, pg_temp"], "plpgsql", False)]


# Bodies of every function, SQL-standard bodies included, that name the table as a word.
NAMES_THE_TABLE = r"""
    SELECT n.nspname || '.' || p.proname FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE coalesce(p.prosrc, '') || coalesce(pg_get_function_sqlbody(p.oid), '')
          ~ '\msecurity_event\M'
"""


def test_only_the_lookup_definers_and_audit_functions_name_security_event() -> None:
    """Decision 32: no other function can reach depth 2 with a change kind. Today the two lookup
    definers and M4r-1e-i's three audit functions; M4r-1e-ii adds org_unit_audit (the six).
    The probe trigger is removed for the scan."""
    event_probe.remove()
    try:
        found = sorted(name for (name,) in as_migrator(NAMES_THE_TABLE))
    finally:
        event_probe.install()
    assert found == [
        "guard.auth_lookup_credential",
        "guard.auth_lookup_login",
        "public.role_audit",
        "public.role_permission_audit",
        "public.user_role_audit",
    ]


def test_skiw_app_cannot_create_temporary_objects() -> None:
    """With no TEMP on the database (roles.sql revokes ALL from PUBLIC and grants CONNECT only),
    skiw_app cannot create a pg_temp trigger function to write a change kind at depth 2
    (DECISIONS 2026-11-24, M4r-1c-ii, open item)."""
    assert as_migrator(
        "SELECT has_database_privilege('skiw_app', current_database(), 'TEMPORARY'),"
        " has_database_privilege('skiw_app', current_database(), 'CREATE')"
    ) == [(False, False)]
    with (
        pytest.raises(DatabaseError) as raised,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("CREATE TEMPORARY TABLE probe_temp (id int)")
    assert isinstance(raised.value.__cause__, psycopg.errors.InsufficientPrivilege)
