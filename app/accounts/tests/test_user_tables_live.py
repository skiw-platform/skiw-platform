"""The column rules of the accounts tenant tables (spec §4.1 `app_user`, `user_factor`;
carry-over (b) `session_revocation`; plan M3 §3 M3d-1a, M3d-1b), as skiw_app bound to the
configured agency. Every test runs in one with_agency() transaction that is rolled back:
skiw_app may not delete `app_user` or `session_revocation` rows, so nothing is committed. Each
refusal is pinned to the constraint that gives it."""

import hashlib
import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, connection, transaction
from django.db.backends.utils import CursorWrapper

from accounts.factor_model import UserFactor
from accounts.user_model import LOGIN_BLOB_LENGTH
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

LOOKUP_BLOB_LENGTH = 62
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


def add_factor(cursor: CursorWrapper, user: uuid.UUID, **columns: Any) -> None:
    values: dict[str, Any] = {"id": uuid.uuid4(), "user_id": user, "kind": "totp", **columns}
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
    add_factor(cursor, add_user(cursor), kind=kind)


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
    add_factor(cursor, user, kind="recovery", lookup_blob_ct=b"\0" * LOOKUP_BLOB_LENGTH)
    cursor.execute("SELECT sign_count FROM user_factor WHERE user_id = %s", [user])
    assert cursor.fetchall() == [(0,)]


def test_a_credential_id_belongs_to_one_factor(cursor: CursorWrapper) -> None:
    user, credential = add_user(cursor), os.urandom(16)
    add_factor(cursor, user, kind="passkey", credential_id=credential)
    refusal = refused_by(
        cursor, lambda c: add_factor(c, add_user(c), kind="passkey", credential_id=credential)
    )
    assert refusal == f"{UserFactor._meta.db_table}_credential_id_key"


def test_a_revocation_marks_one_session_or_the_whole_user(cursor: CursorWrapper) -> None:
    user = add_user(cursor)
    for key_hash in (KEY_HASH, None):
        row = add_revocation(cursor, user, key_hash)
        cursor.execute(
            # Django's Now() is STATEMENT_TIMESTAMP(): the insert's own time, not the xact's.
            "SELECT session_key_hash, revoked_at BETWEEN now() AND statement_timestamp()"
            " FROM session_revocation WHERE id = %s",
            [row],
        )
        assert cursor.fetchall() == [(key_hash, True)]


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
