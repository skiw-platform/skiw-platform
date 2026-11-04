"""`guard.auth_lookup_login` (spec §4.1 "Pre-tenant lookups", TEN-12; plan M3 §3 M3e and the §4 M3e
row, split M3e-1b) through `accounts.auth.lookup`, as skiw_app. A known email gives its
`login_blob_ct`; an unknown email, or a user with no password yet, gives a decoy of the same length
that is stable, differs per email and never opens. Every call writes one `security_event` that is
the same for both. skiw_app may not delete `app_user` rows, so each test runs in a rolled-back
with_agency() transaction; the decoy-key cases run as the key owner in a rolled-back transaction."""

import hashlib
import hmac
import os
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from typing import Any

import psycopg
import pytest
from django.conf import settings
from django.db import connection, transaction
from django.db.backends.utils import CursorWrapper

from accounts.auth import blob
from accounts.auth.blob import LoginRecord
from accounts.auth.lookup import lookup_login
from accounts.tests.conftest import committed_user
from accounts.user_model import LOGIN_BLOB_LENGTH
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

FUNCTION = "guard.auth_lookup_login(public.citext)"
LOOKUP = "skiw_auth_lookup"
RECORD = LoginRecord(uuid.uuid4(), uuid.uuid4(), "$argon2id$v=19$m=65536,t=3,p=1$c2FsdA$aGFzaA")
EVENT = ("login.lookup", None, None, "{}")


def decoy(email: str, key: bytes) -> bytes:
    """The decoy the function must give: HMAC-SHA-256 in counter mode over the lower-cased email."""
    label, address = b"skiw-decoy-login-v1", email.lower().encode()
    blocks = (
        hmac.digest(key, label + i.to_bytes(4, "big") + address, hashlib.sha256)
        for i in range(1, 8)
    )
    return b"".join(blocks)[:LOGIN_BLOB_LENGTH]


def oldest_key() -> bytes:
    return min(settings.SKIW_LOOKUP_DECOY_KEYS())[1]


def unknown() -> str:
    return f"{uuid.uuid4()}@example.test"


@pytest.fixture
def cursor() -> Iterator[CursorWrapper]:
    agency = uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])
    with with_agency(agency), connection.cursor() as bound:
        yield bound
        transaction.set_rollback(True)


def add_user(cursor: CursorWrapper, email: str, login_blob_ct: bytes | None) -> None:
    cursor.execute(
        "INSERT INTO app_user (agency_id, id, email, display_name, login_blob_ct)"
        " VALUES (guard.current_agency(), %s, %s, 'User', %s)",
        [uuid.uuid4(), email, login_blob_ct],
    )


def direct(cursor: CursorWrapper, email: str) -> bytes:
    """The function called as typed, without accounts.auth.lookup's normalising."""
    cursor.execute("SELECT guard.auth_lookup_login(%s)", [email])
    (found,) = cursor.fetchone()
    return bytes(found)


def events(cursor: CursorWrapper) -> dict[Any, tuple[Any, ...]]:
    cursor.execute(
        "SELECT id, kind, email_hmac, ip_hmac, details_json::text FROM security_event ORDER BY at"
    )
    return {row[0]: row[1:] for row in cursor.fetchall()}


@contextmanager
def as_owner() -> Iterator[psycopg.Cursor[Any]]:
    """skiw_auth_lookup (the migrator through SET LOCAL ROLE), in a transaction rolled back."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        try:
            with conn.cursor() as owner:
                owner.execute("SET LOCAL ROLE skiw_auth_lookup")
                yield owner
        finally:
            conn.rollback()


def owner_lookup(owner: psycopg.Cursor[Any], email: str) -> bytes:
    row = owner.execute("SELECT guard.auth_lookup_login(%s)", (email,)).fetchone()
    assert row is not None
    return bytes(row[0])


def test_the_function_is_hardened_as_the_spec_lists() -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT proowner::regrole::text, prosecdef, proconfig, proacl::text,"
            " prorettype::regtype::text, proargtypes::regtype[]::text[], provolatile, proisstrict"
            " FROM pg_proc WHERE oid = to_regprocedure(%s)",
            (FUNCTION,),
        ).fetchone()
    assert row == (
        LOOKUP,
        True,
        ["search_path=pg_catalog, pg_temp"],
        "{skiw_auth_lookup=X/skiw_auth_lookup,skiw_app=X/skiw_auth_lookup}",
        "bytea",
        ["citext"],
        "v",
        True,
    )


def test_the_decoy_length_is_the_sealed_login_blob_length() -> None:
    migration = import_module("accounts.migrations.0009_auth_lookup_login")
    assert migration.DECOY_LENGTH == LOGIN_BLOB_LENGTH == blob.OVERHEAD + blob.LOGIN_SIZE


def test_the_owner_reads_only_the_two_lookup_columns_of_app_user() -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        columns = conn.execute(
            "SELECT a.attname FROM pg_attribute a WHERE a.attrelid = 'app_user'::regclass"
            " AND a.attnum > 0 AND NOT a.attisdropped"
            " AND has_column_privilege(%s, 'app_user'::regclass, a.attname, 'SELECT')",
            (LOOKUP,),
        ).fetchall()
        table = conn.execute(
            "SELECT p FROM unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']) p"
            " WHERE has_table_privilege(%s, 'app_user', p)",
            (LOOKUP,),
        ).fetchall()
    assert {name for (name,) in columns} == {"email", "login_blob_ct"}
    assert table == []


def test_a_known_email_gives_its_blob_whatever_its_case(cursor: CursorWrapper) -> None:
    email = unknown()
    sealed = blob.seal_login(RECORD, email)
    add_user(cursor, email.upper(), sealed)  # a stored address in another case still matches
    assert lookup_login(email) == sealed
    assert direct(cursor, email.title()) == sealed  # the function's own citext equality
    assert lookup_login(email.upper()) == sealed  # citext equality, not text (OPERATOR(public.=))
    assert lookup_login(f"  {email} ") == sealed  # the caller normalises, as the blob AAD does
    assert blob.open_login(lookup_login(email), email) == RECORD


def test_an_unknown_email_gives_a_stable_decoy_of_the_blob_length_that_never_opens(
    cursor: CursorWrapper,
) -> None:
    email, other = unknown(), unknown()
    first = lookup_login(email)
    assert len(first) == LOGIN_BLOB_LENGTH
    assert lookup_login(email) == first == decoy(email, oldest_key())
    assert lookup_login(email.upper()) == first  # one decoy per citext-equal email, as a row
    assert direct(cursor, email.upper()) == first  # the function itself lower-cases, not the caller
    assert lookup_login(other) != first
    assert blob.open_login(first, email) is None


def test_a_user_with_no_password_yet_gets_the_decoy(cursor: CursorWrapper) -> None:
    email = unknown()
    expected = lookup_login(email)
    add_user(cursor, email, None)
    assert lookup_login(email) == expected


def test_decoys_have_no_fixed_leading_bytes(cursor: CursorWrapper) -> None:
    """Owner 2026-11-04 (5): a real blob has nothing in clear, so neither may a decoy."""
    assert len({lookup_login(unknown())[:2] for _ in range(32)}) > 1


def test_every_call_writes_one_event_that_is_the_same_for_known_and_unknown(
    cursor: CursorWrapper,
) -> None:
    email = unknown()
    add_user(cursor, email, blob.seal_login(RECORD, email))
    before = events(cursor)
    lookup_login(email)
    lookup_login(unknown())
    added = [row for key, row in events(cursor).items() if key not in before]
    assert added == [EVENT, EVENT]


def test_a_new_decoy_key_version_changes_no_decoy() -> None:
    """Owner 2026-11-04 (4): the oldest version is pinned, so a rotation that adds a version leaves
    every decoy as it was; only removing the oldest changes them (docs/DECISIONS.md "M3e-1b")."""
    email, newer = unknown(), secrets.token_bytes(32)
    with as_owner() as owner:
        before = owner_lookup(owner, email)
        owner.execute(
            "INSERT INTO guard.lookup_decoy_key (version, key) VALUES (999999, %s)", (newer,)
        )
        assert owner_lookup(owner, email) == before == decoy(email, oldest_key())
        owner.execute("DELETE FROM guard.lookup_decoy_key WHERE version < 999999")
        assert owner_lookup(owner, email) == decoy(email, newer)


def test_no_decoy_key_is_an_error_for_known_and_unknown_emails_alike() -> None:
    known = committed_user(status="invited").email  # kept: skiw_app may not delete app_user
    for email in (unknown(), known):
        with as_owner() as owner:
            owner.execute("DELETE FROM guard.lookup_decoy_key")
            with pytest.raises(psycopg.errors.RaiseException) as raised:
                owner_lookup(owner, email)
        assert email not in str(raised.value)
