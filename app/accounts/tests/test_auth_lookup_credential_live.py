"""`guard.auth_lookup_credential` (spec §4.1 "Pre-tenant lookups", TEN-12; plan M3 §3 M3g and the
§4 M3g row, split M3g-1b) through `accounts.auth.lookup`, as skiw_app. A passkey in use gives its
`lookup_blob_ct`; an unknown or retired credential id gives a decoy of the same 60 bytes that is
stable, differs per id and never opens. Every call writes one `security_event` that is the same
for both. Each test runs in a rolled-back with_agency() transaction; the decoy-key cases run as the
key owner in a rolled-back transaction, the one committed passkey is deleted afterwards."""

import hashlib
import hmac
import os
import uuid
from collections.abc import Iterator
from importlib import import_module
from typing import Any

import psycopg
import pytest
from django.db import connection, transaction
from django.db.backends.utils import CursorWrapper

from accounts.auth import blob, passkey
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.factor_model import CREDENTIAL_ID_MAX, LOOKUP_BLOB_LENGTH, SIGN_COUNT_MAX
from accounts.tests.conftest import committed_user
from tenancy.binding import with_agency

from .test_auth_lookup_login_live import as_owner, events, oldest_key
from .test_factor_remove_live import migrate
from .test_user_tables_live import RETIRED, add_factor, add_user

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

FUNCTION = "guard.auth_lookup_credential(bytea)"
LOOKUP = "skiw_auth_lookup"
EVENT = ("passkey.lookup", None, None, "{}")
MIGRATION = "accounts.migrations.0015_passkey_lookup"


def decoy(credential: bytes, key: bytes) -> bytes:
    """The decoy the function must give: HMAC-SHA-256 in counter mode over the credential id."""
    label = b"skiw-decoy-credential-v1"
    blocks = (
        hmac.digest(key, label + i.to_bytes(4, "big") + credential, hashlib.sha256) for i in (1, 2)
    )
    return b"".join(blocks)[:LOOKUP_BLOB_LENGTH]


def agency() -> uuid.UUID:
    return uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])


@pytest.fixture
def cursor() -> Iterator[CursorWrapper]:
    with with_agency(agency()), connection.cursor() as bound:
        yield bound
        transaction.set_rollback(True)


def add_passkey(cursor: CursorWrapper) -> tuple[bytes, CredentialOwner, bytes]:
    """A passkey in use of a new user: its credential id, its owner and its sealed blob."""
    credential, user = os.urandom(16), add_user(cursor)
    sealed = blob.seal_credential(user, agency(), credential)
    add_factor(cursor, user, credential_id=credential, lookup_blob_ct=sealed)
    return credential, CredentialOwner(user, agency()), sealed


def direct(cursor: CursorWrapper, credential: bytes) -> bytes:
    cursor.execute("SELECT guard.auth_lookup_credential(%s)", [credential])
    (found,) = cursor.fetchone()
    return bytes(found)


def owner_lookup(owner: psycopg.Cursor[Any], credential: bytes) -> bytes:
    row = owner.execute("SELECT guard.auth_lookup_credential(%s)", (credential,)).fetchone()
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
        ["bytea"],
        "v",
        True,
    )


def test_the_migration_literals_are_the_model_and_ceremony_bounds() -> None:
    migration = import_module(MIGRATION)
    assert migration.DECOY_LENGTH == LOOKUP_BLOB_LENGTH == blob.OVERHEAD + blob.CREDENTIAL_SIZE
    assert migration.CREDENTIAL_ID_MAX == CREDENTIAL_ID_MAX == passkey.MAX_CREDENTIAL_ID == 1023
    assert migration.SIGN_COUNT_MAX == SIGN_COUNT_MAX == 2**32 - 1


def test_the_owner_reads_only_the_three_lookup_columns_of_user_factor() -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        columns = conn.execute(
            "SELECT a.attname FROM pg_attribute a WHERE a.attrelid = 'user_factor'::regclass"
            " AND a.attnum > 0 AND NOT a.attisdropped"
            " AND has_column_privilege(%s, 'user_factor'::regclass, a.attname, 'SELECT')",
            (LOOKUP,),
        ).fetchall()
        table = conn.execute(
            "SELECT p FROM unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']) p"
            " WHERE has_table_privilege(%s, 'user_factor', p)",
            (LOOKUP,),
        ).fetchall()
    assert {name for (name,) in columns} == {"credential_id", "lookup_blob_ct", "retired_at"}
    assert table == []


def test_a_passkey_in_use_gives_its_blob_and_its_owner(cursor: CursorWrapper) -> None:
    credential, owner, sealed = add_passkey(cursor)
    assert direct(cursor, credential) == sealed
    assert lookup_credential(credential) == owner


def test_an_unknown_id_gives_a_stable_decoy_of_the_blob_length_that_never_opens(
    cursor: CursorWrapper,
) -> None:
    credential = os.urandom(16)
    first = direct(cursor, credential)
    assert len(first) == LOOKUP_BLOB_LENGTH
    assert direct(cursor, credential) == first == decoy(credential, oldest_key())
    assert direct(cursor, os.urandom(16)) != first
    assert direct(cursor, credential[:15]) != first  # the whole id, not a prefix
    assert lookup_credential(credential) is None
    for size in (1, CREDENTIAL_ID_MAX):  # any id length gives the one decoy length
        assert len(direct(cursor, os.urandom(size))) == LOOKUP_BLOB_LENGTH


def test_a_retired_passkey_gives_the_decoy_of_an_unknown_id(cursor: CursorWrapper) -> None:
    credential, user = os.urandom(16), add_user(cursor)
    expected = direct(cursor, credential)
    retired = {"public_key": None, "lookup_blob_ct": None, "retired_at": RETIRED}
    add_factor(cursor, user, credential_id=credential, **retired)
    assert direct(cursor, credential) == expected == decoy(credential, oldest_key())
    assert lookup_credential(credential) is None


def test_a_blob_moved_to_another_passkey_does_not_open(cursor: CursorWrapper) -> None:
    """Plan §4 M3g: `lookup_blob_ct` moved to another row fails its AAD (the credential id)."""
    _, _, sealed = add_passkey(cursor)
    other, _, _ = add_passkey(cursor)
    cursor.execute(
        "UPDATE user_factor SET lookup_blob_ct = %s WHERE credential_id = %s", [sealed, other]
    )
    assert direct(cursor, other) == sealed
    assert lookup_credential(other) is None


def test_decoys_have_no_fixed_leading_bytes(cursor: CursorWrapper) -> None:
    assert len({direct(cursor, os.urandom(16))[:2] for _ in range(32)}) > 1


def test_every_call_writes_one_event_that_is_the_same_for_known_and_unknown(
    cursor: CursorWrapper,
) -> None:
    credential, _, _ = add_passkey(cursor)
    before = events(cursor)
    lookup_credential(credential)
    lookup_credential(os.urandom(16))
    added = [row for key, row in events(cursor).items() if key not in before]
    assert added == [EVENT, EVENT]


def test_a_new_decoy_key_version_changes_no_decoy() -> None:
    """The oldest version is pinned, as for logins (docs/DECISIONS.md "M3e-1b", "M3g-1b")."""
    credential, newer = os.urandom(16), os.urandom(32)
    with as_owner() as owner:
        before = owner_lookup(owner, credential)
        owner.execute(
            "INSERT INTO guard.lookup_decoy_key (version, key) VALUES (999999, %s)", (newer,)
        )
        assert owner_lookup(owner, credential) == before == decoy(credential, oldest_key())
        owner.execute("DELETE FROM guard.lookup_decoy_key WHERE version < 999999")
        assert owner_lookup(owner, credential) == decoy(credential, newer)


@pytest.fixture
def committed_passkey() -> Iterator[bytes]:
    """A passkey committed for the owner's own connection, deleted afterwards (skiw_app holds
    DELETE on user_factor; no step-up names it)."""
    user, credential = committed_user(), os.urandom(16)
    with with_agency(user.agency_id), connection.cursor() as cursor:
        add_factor(cursor, user.id, credential_id=credential)
    try:
        yield credential
    finally:
        with with_agency(user.agency_id), connection.cursor() as cursor:
            cursor.execute("DELETE FROM user_factor WHERE credential_id = %s", [credential])


def test_no_decoy_key_is_an_error_for_known_and_unknown_ids_alike(committed_passkey: bytes) -> None:
    with as_owner() as owner:  # the committed passkey is known to the definer (BYPASSRLS)
        assert owner_lookup(owner, committed_passkey) == bytes(LOOKUP_BLOB_LENGTH)
    for credential in (os.urandom(16), committed_passkey):
        with as_owner() as owner:
            owner.execute("DELETE FROM guard.lookup_decoy_key")
            with pytest.raises(psycopg.errors.RaiseException) as raised:
                owner_lookup(owner, credential)
        assert str(raised.value).startswith("guard.auth_lookup_credential: no lookup_decoy_key")


def test_accounts_0015_reverses_and_reapplies_with_the_challenge_time_kept(
    committed_passkey: bytes,
) -> None:
    """The reverse keeps `last_challenge_at` (a reverse and re-apply must not clear M3g-1d's replay
    guard) and drops the function; the re-apply validates the passkey rules on the kept row."""
    with with_agency(agency()), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE user_factor SET last_challenge_at = %s WHERE credential_id = %s",
            [RETIRED, committed_passkey],
        )
    try:
        migrate("accounts", "0014")
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
            gone = conn.execute("SELECT to_regprocedure(%s)", (FUNCTION,)).fetchone()
        assert gone == (None,)
    finally:
        migrate()
    with with_agency(agency()), connection.cursor() as cursor:
        cursor.execute(
            "SELECT last_challenge_at FROM user_factor WHERE credential_id = %s",
            [committed_passkey],
        )
        assert cursor.fetchall() == [(RETIRED,)]
        assert direct(cursor, committed_passkey) == bytes(LOOKUP_BLOB_LENGTH)
