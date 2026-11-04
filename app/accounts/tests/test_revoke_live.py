"""The `session_revocation` primitives (accounts.auth.revoke; plan M3 §3 M3d carry-over (b),
AUTH-07) and the marker login() writes when it rotates an authenticated session. The check runs in
authorized_action (M3d-2b2); here it is called directly, as skiw_app on committed users (kept)."""

import uuid
from datetime import datetime, timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from accounts.auth import revoke
from accounts.auth.login import AUTH_AT
from accounts.revocation_model import SessionRevocation
from accounts.session import SessionStore, stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import committed_user, row_deadline
from .test_login_live import logged_in
from .test_session_hmac_live import started

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]


def revoked(user: AppUser, cookie: str, auth_at: datetime | None = None) -> bool:
    if auth_at is None:
        auth_at = datetime.fromisoformat(SessionStore(cookie)[AUTH_AT])
    with with_agency(user.agency_id):
        return revoke.revoked(user.id, cookie, auth_at)


def markers(user: AppUser) -> list[str | None]:
    with with_agency(user.agency_id):
        rows = SessionRevocation.objects.filter(user_id=user.id).order_by("revoked_at")
        return list(rows.values_list("session_key_hash", flat=True))


@pytest.fixture
def user() -> AppUser:
    return committed_user()


@pytest.mark.parametrize("same_user", [True, False], ids=["same-user", "other-agency-user"])
def test_a_login_over_an_authenticated_session_marks_the_old_key(
    user: AppUser, same_user: bool, agency_b: uuid.UUID
) -> None:
    _, cookie = logged_in(started(), user)
    now = timezone.now()
    after = user if same_user else committed_user(agency=agency_b)
    _, renewed = logged_in(cookie, after)
    assert row_deadline(cookie) is None  # the old row is gone...
    assert markers(user) == [stored_key(cookie)]  # ...and marked under its own user and agency
    assert revoked(user, cookie, now)  # so a copy put back by SQL is still refused
    assert not revoked(after, renewed)


def test_a_login_over_a_session_without_a_login_writes_no_marker(user: AppUser) -> None:
    logged_in(started(), user)
    assert markers(user) == []


def test_a_failed_marker_insert_leaves_the_old_session_alive(
    user: AppUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The insert fails in the database (its key hash breaks the shape CHECK): the transaction
    that would delete the row rolls back, so the old session is exactly as it was."""
    _, cookie = logged_in(started(), user)
    deadline = row_deadline(cookie)
    monkeypatch.setattr(revoke, "stored_key", lambda raw: "not a key hash")
    with pytest.raises(IntegrityError):
        logged_in(cookie, user)
    monkeypatch.undo()
    assert markers(user) == [] and row_deadline(cookie) == deadline
    assert SessionStore(cookie)["probe"]


def test_a_key_marker_revokes_that_session_only(user: AppUser) -> None:
    _, first = logged_in(started(), user)
    _, second = logged_in(started(), user)
    with with_agency(user.agency_id):
        revoke.mark(user.agency_id, user.id, first)
    assert revoked(user, first) and not revoked(user, second)


def test_a_user_wide_marker_revokes_sessions_signed_in_at_or_before_it(user: AppUser) -> None:
    """`revoked_at` (database clock) against `_skiw_auth_at` (web clock): web and db read the one
    host clock, and a tie counts as revoked. The times here come from the marker itself."""
    other = committed_user()
    _, cookie = logged_in(started(), user)
    _, others = logged_in(started(), other)
    revoke.revoke_user(user.agency_id, user.id)
    with with_agency(user.agency_id):
        at = SessionRevocation.objects.get(user_id=user.id, session_key_hash=None).revoked_at
    assert revoked(user, cookie, at - timedelta(minutes=1))
    assert revoked(user, cookie, at)  # the tie
    assert not revoked(user, cookie, at + timedelta(microseconds=1))
    assert not revoked(other, others)  # another user's sessions are untouched
