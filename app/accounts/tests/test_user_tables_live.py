"""The column rules of the accounts tenant tables (spec §4.1 `app_user`, `user_factor`;
carry-over (b) `session_revocation`; plan M3 §3 M3d-1a, M3d-1b), as skiw_app bound to the
configured agency. Every test runs in one with_agency() transaction that is rolled back:
skiw_app may not delete `app_user` or `session_revocation` rows, so nothing is committed. Each
refusal is pinned to the constraint that gives it."""

import hashlib
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, connection, transaction
from django.db.backends.utils import CursorWrapper

from accounts.factor_model import SIGN_COUNT_MAX, UserFactor
from accounts.user_model import LOGIN_BLOB_LENGTH
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

LOOKUP_BLOB_LENGTH = 60
BLOB = b"\0" * LOOKUP_BLOB_LENGTH
TOTP_SECRET_CT = 48  # accounts.0010: the sealed factor secret
RECOVERY_SECRET_CT = 36  # accounts.0010: 4-byte key version, then the 32-byte HMAC-SHA-256
RETIRED = datetime(2026, 11, 11, tzinfo=UTC)
SECRET_CT = {"totp": TOTP_SECRET_CT, "recovery": RECOVERY_SECRET_CT}
# A stored_key()-shaped value, derived so no high-entropy literal sits in the source.
KEY_HASH = hashlib.sha256(b"session-revocation-test").hexdigest()


@pytest.fixture
def cursor() -> Iterator[CursorWrapper]:
    agency = uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])
    with with_agency(agency), connection.cursor() as bound:
        yield bound
        transaction.set_rollback(True)


def add_user(cursor: CursorWrapper, email: str | None = None, **columns: Any) -> uuid.UUID:
    row = uuid.uuid4()
    values: dict[str, Any] = {
        "id": row,
        "email": email or f"{row}@example.test",
        "display_name": "User",
    }
    values.update(columns)
    names = ", ".join(values)
    cursor.execute(
        f"INSERT INTO app_user (agency_id, {names})"  # noqa: S608 (names are this module's)
        f" VALUES (guard.current_agency(), {', '.join(['%s'] * len(values))})",
        list(values.values()),
    )
    return row


def passkey_columns() -> dict[str, Any]:
    """The columns of a passkey in use (accounts.0015): a fresh credential id, a key, a blob."""
    return {"credential_id": os.urandom(16), "public_key": b"\1" * 77, "lookup_blob_ct": BLOB}


def add_factor(cursor: CursorWrapper, user: uuid.UUID, **columns: Any) -> None:
    """A `kind` row (passkey by default; a passkey gets `passkey_columns()` under `columns`)."""
    kind = columns.setdefault("kind", "passkey")
    values: dict[str, Any] = {"id": uuid.uuid4(), "user_id": user}
    values.update({**passkey_columns(), **columns} if kind == "passkey" else columns)
    cursor.execute(
        f"INSERT INTO user_factor (agency_id, {', '.join(values)})"  # noqa: S608 (as above)
        f" VALUES (guard.current_agency(), {', '.join(['%s'] * len(values))})",
        list(values.values()),
    )


def add_revocation(cursor: CursorWrapper, user: uuid.UUID, key_hash: str | None) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO session_revocation (id, agency_id, user_id, session_key_hash)"
        " VALUES (%s, guard.current_agency(), %s, %s)",
        [row, user, key_hash],
    )
    return row


def refused_by(cursor: CursorWrapper, action: Callable[[CursorWrapper], object]) -> str:
    """Run `action(cursor)` in a savepoint and return the name of the constraint that refused it."""
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        action(cursor)
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.errors.IntegrityError)
    return str(cause.diag.constraint_name)


def test_a_new_user_is_invited_and_has_no_login_blob_yet(cursor: CursorWrapper) -> None:
    user = add_user(cursor)
    cursor.execute(
        "SELECT status, login_blob_ct, last_login_at FROM app_user WHERE id = %s", [user]
    )
    assert cursor.fetchall() == [("invited", None, None)]


def test_email_is_unique_and_matched_without_regard_to_case(cursor: CursorWrapper) -> None:
    user = add_user(cursor, "Adviser@Example.test")
    cursor.execute("SELECT id FROM app_user WHERE email = %s", ["adviser@EXAMPLE.TEST"])
    assert cursor.fetchall() == [(user,)]
    assert refused_by(cursor, lambda c: add_user(c, "ADVISER@example.test")) == "app_user_email_key"


@pytest.mark.parametrize(
    ("table", "constraint", "definition"),
    [
        ("app_user", "app_user_email_key", "UNIQUE (email)"),
        ("user_factor", "user_factor_credential_id_key", "UNIQUE (credential_id)"),
    ],
    ids=["email", "credential-id"],
)
def test_the_pre_tenant_lookup_keys_are_unique_across_agencies(
    cursor: CursorWrapper, table: str, constraint: str, definition: str
) -> None:
    """Spec §4.1 `uq(email)` and `uq(credential_id)` are global: the M3e/M3g lookups resolve them
    before the tenant is known. A per-agency key (`UNIQUE (agency_id, email)`) passes every
    single-agency test, so the catalog shape is pinned (PR 103 review R1 P3 #2)."""
    cursor.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint"
        " WHERE conrelid = %s::regclass AND contype = 'u' AND conname = %s",
        [f"public.{table}", constraint],
    )
    assert cursor.fetchall() == [(constraint, definition)]


@pytest.mark.parametrize("status", ["invited", "active", "disabled"])
def test_each_known_status_is_accepted(cursor: CursorWrapper, status: str) -> None:
    add_user(cursor, status=status)


def test_an_unknown_status_is_refused(cursor: CursorWrapper) -> None:
    assert refused_by(cursor, lambda c: add_user(c, status="locked")) == "app_user_status_known"


@pytest.mark.parametrize(
    "size", [LOGIN_BLOB_LENGTH - 1, LOGIN_BLOB_LENGTH + 1], ids=["short", "long"]
)
def test_the_login_blob_has_exactly_the_sealed_length(cursor: CursorWrapper, size: int) -> None:
    add_user(cursor, login_blob_ct=b"\0" * LOGIN_BLOB_LENGTH)
    refusal = refused_by(cursor, lambda c: add_user(c, login_blob_ct=b"\0" * size))
    assert refusal == "app_user_login_blob_ct_length"


@pytest.mark.parametrize("kind", ["passkey", "totp", "recovery"])
def test_each_known_factor_kind_is_accepted(cursor: CursorWrapper, kind: str) -> None:
    secret = b"\0" * SECRET_CT[kind] if kind in SECRET_CT else None
    add_factor(cursor, add_user(cursor), kind=kind, secret_ct=secret)


@pytest.mark.parametrize(
    ("kind", "secret"),
    [
        ("totp", None),
        ("totp", b"\0" * (TOTP_SECRET_CT - 1)),
        ("totp", b"\0" * (TOTP_SECRET_CT + 1)),
        ("totp", b"\0" * RECOVERY_SECRET_CT),
        ("recovery", None),
        ("recovery", b"\0" * 32),
        ("recovery", b"\0" * (RECOVERY_SECRET_CT - 1)),
        ("recovery", b"\0" * (RECOVERY_SECRET_CT + 1)),
        ("recovery", b"\0" * TOTP_SECRET_CT),
    ],
)
def test_a_totp_or_recovery_secret_has_exactly_its_length(
    cursor: CursorWrapper, kind: str, secret: bytes | None
) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_factor(c, user, kind=kind, secret_ct=secret))
    assert refusal == f"user_factor_{kind}_secret_ct_length"


@pytest.mark.parametrize("kind", ["passkey", "totp"])
def test_a_retired_factor_holds_no_secret(cursor: CursorWrapper, kind: str) -> None:
    """accounts.0014 (DECISIONS M3h-6): a retired TOTP is exempt from its length rule."""
    retired = {"secret_ct": None, "public_key": None, "lookup_blob_ct": None, "retired_at": RETIRED}
    add_factor(cursor, add_user(cursor), kind=kind, **retired)


@pytest.mark.parametrize(
    ("columns", "constraint"),
    [
        ({"kind": "totp", "secret_ct": b"\0" * TOTP_SECRET_CT}, "user_factor_retired_no_secret"),
        ({"kind": "passkey", "lookup_blob_ct": None}, "user_factor_retired_no_secret"),
        ({"kind": "passkey", "public_key": None}, "user_factor_retired_no_secret"),
        ({"kind": "recovery", "secret_ct": None}, "user_factor_recovery_secret_ct_length"),
        (
            {"kind": "recovery", "secret_ct": b"\0" * RECOVERY_SECRET_CT},
            "user_factor_retired_no_secret",
        ),
    ],
    ids=["totp-secret", "passkey-key", "passkey-lookup", "recovery-none", "recovery-mac"],
)
def test_a_retired_factor_with_secret_material_or_a_retired_recovery_code_is_refused(
    cursor: CursorWrapper, columns: dict[str, object], constraint: str
) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_factor(c, user, retired_at=RETIRED, **columns))
    assert refusal == constraint


@pytest.mark.parametrize(
    ("columns", "constraint"),
    [
        ({"kind": "sms"}, "user_factor_kind_known"),
        ({"sign_count": -1}, "user_factor_sign_count_gte_0"),
        ({"lookup_blob_ct": b"\0" * (LOOKUP_BLOB_LENGTH - 1)}, "user_factor_lookup_blob_ct_length"),
        ({"lookup_blob_ct": b"\0" * (LOOKUP_BLOB_LENGTH + 1)}, "user_factor_lookup_blob_ct_length"),
    ],
    ids=["kind", "sign-count", "lookup-blob-short", "lookup-blob-long"],
)
def test_a_factor_outside_the_column_rules_is_refused(
    cursor: CursorWrapper, columns: dict[str, object], constraint: str
) -> None:
    user = add_user(cursor)
    assert refused_by(cursor, lambda c: add_factor(c, user, **columns)) == constraint


def test_a_factor_takes_the_sealed_lookup_blob_and_counts_from_zero(cursor: CursorWrapper) -> None:
    user = add_user(cursor)
    add_factor(cursor, user, kind="passkey")
    cursor.execute(
        "SELECT sign_count, last_challenge_at FROM user_factor WHERE user_id = %s", [user]
    )
    assert cursor.fetchall() == [(0, None)]


def test_a_passkey_at_the_bounds_is_accepted(cursor: CursorWrapper) -> None:
    """accounts.0015: 1 and 1 023 byte credential ids (passkey.MAX_CREDENTIAL_ID), the largest
    32-bit count, a challenge time; retired, a passkey keeps only its credential id."""
    user = add_user(cursor)
    add_factor(cursor, user, credential_id=os.urandom(1), sign_count=SIGN_COUNT_MAX)
    add_factor(cursor, user, credential_id=os.urandom(1023), last_challenge_at=RETIRED)
    add_factor(cursor, user, public_key=None, lookup_blob_ct=None, retired_at=RETIRED)


@pytest.mark.parametrize(
    ("columns", "constraint"),
    [
        ({"credential_id": None}, "user_factor_passkey_shape"),
        ({"credential_id": b""}, "user_factor_passkey_shape"),
        ({"credential_id": b"\1" * 1024}, "user_factor_passkey_shape"),
        ({"secret_ct": b"\0" * TOTP_SECRET_CT}, "user_factor_passkey_shape"),
        ({"sign_count": SIGN_COUNT_MAX + 1}, "user_factor_passkey_shape"),
        ({"public_key": None}, "user_factor_passkey_in_use"),
        ({"lookup_blob_ct": None}, "user_factor_passkey_in_use"),
        (
            {
                "credential_id": None,
                "retired_at": RETIRED,
                "public_key": None,
                "lookup_blob_ct": None,
            },
            "user_factor_passkey_shape",
        ),
    ],
    ids=["no-id", "empty-id", "long-id", "secret", "count", "no-key", "no-blob", "retired-no-id"],
)
def test_a_passkey_outside_its_rules_is_refused(
    cursor: CursorWrapper, columns: dict[str, object], constraint: str
) -> None:
    user = add_user(cursor)
    assert refused_by(cursor, lambda c: add_factor(c, user, **columns)) == constraint


@pytest.mark.parametrize("kind", ["totp", "recovery"])
@pytest.mark.parametrize(
    "column", ["credential_id", "public_key", "lookup_blob_ct", "last_challenge_at"]
)
def test_only_a_passkey_holds_passkey_columns(
    cursor: CursorWrapper, kind: str, column: str
) -> None:
    value = RETIRED if column == "last_challenge_at" else passkey_columns()[column]
    secret = b"\0" * SECRET_CT[kind]
    user = add_user(cursor)
    refusal = refused_by(
        cursor, lambda c: add_factor(c, user, kind=kind, secret_ct=secret, **{column: value})
    )
    assert refusal == "user_factor_passkey_only_columns"


def test_a_retired_passkeys_credential_id_cannot_come_back(cursor: CursorWrapper) -> None:
    """The global key keeps a retired id: registering it again is refused (M3g-1c, PR 154 P3 #2)."""
    user, credential = add_user(cursor), os.urandom(16)
    retired = {"public_key": None, "lookup_blob_ct": None, "retired_at": RETIRED}
    add_factor(cursor, user, credential_id=credential, **retired)
    refusal = refused_by(cursor, lambda c: add_factor(c, user, credential_id=credential))
    assert refusal == "user_factor_credential_id_key"


def test_a_credential_id_belongs_to_one_factor(cursor: CursorWrapper) -> None:
    user, credential = add_user(cursor), os.urandom(16)
    add_factor(cursor, user, kind="passkey", credential_id=credential)
    refusal = refused_by(
        cursor, lambda c: add_factor(c, add_user(c), kind="passkey", credential_id=credential)
    )
    assert refusal == f"{UserFactor._meta.db_table}_credential_id_key"


def test_a_revocation_marks_one_session_or_the_whole_user(cursor: CursorWrapper) -> None:
    """`revoked_at` is the insert's own statement time, not the transaction's start (PR 104 R1):
    after a sleep in the same transaction it is later than now(). The user-wide check counts a
    session signed in at or before it as revoked, so a later time only revokes more."""
    user = add_user(cursor)
    for key_hash in (KEY_HASH, None):
        cursor.execute("SELECT pg_sleep(0.01)")
        row = add_revocation(cursor, user, key_hash)
        cursor.execute(
            "SELECT session_key_hash, revoked_at > now(), revoked_at < statement_timestamp()"
            " FROM session_revocation WHERE id = %s",
            [row],
        )
        assert cursor.fetchall() == [(key_hash, True, True)]


@pytest.mark.parametrize(
    "key_hash",
    [KEY_HASH.upper(), KEY_HASH[:-1], "g" + KEY_HASH[1:]],
    ids=["upper-case", "short", "not-hex"],  # a longer one is cut off by varchar(64) first
)
def test_a_session_key_hash_must_be_lower_case_sha256_hex(
    cursor: CursorWrapper, key_hash: str
) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_revocation(c, user, key_hash))
    assert refusal == "session_revocation_key_hash_shape"
