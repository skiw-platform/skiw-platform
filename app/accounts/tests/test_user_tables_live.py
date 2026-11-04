"""The column rules of the accounts tenant tables (spec §4.1 `app_user`; plan M3 §3 M3d-1a), as
skiw_app bound to the configured agency. Every test runs in one with_agency() transaction that
is rolled back: skiw_app may not delete `app_user` rows, so nothing is committed. Each refusal
is pinned to the constraint that gives it."""

import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, connection, transaction
from django.db.backends.utils import CursorWrapper

from accounts.user_model import LOGIN_BLOB_LENGTH
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]


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
