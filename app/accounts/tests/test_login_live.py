"""`accounts.auth.login.login()` on the real session store (plan M3 §3 M3d; carry-overs (d) and
(i)). A user object is enough for a login over a session that holds none; a login over an
authenticated session writes a marker, which needs the committed user."""

import uuid
from datetime import timedelta

import pytest
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.test import RequestFactory

from accounts.auth.login import AGENCY, AUTH_AT, FACTOR, SEEN_AT, USER, login
from accounts.session import SessionStore
from accounts.user_model import AppUser

from .conftest import Clock, absolute, committed_user, row_deadline
from .test_session_hmac_live import assert_rejected, data_of, get, set_data, started

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]


def a_user() -> AppUser:
    return AppUser(id=uuid.uuid4(), agency_id=uuid.uuid4(), email="u@example.test")


def logged_in(cookie: str, user: AppUser, factor: str = "passkey") -> tuple[HttpRequest, str]:
    """login() as the next request's view would call it: a fresh store for the cookie."""
    request = RequestFactory().get("/")
    request.session = SessionStore(cookie)
    login(request, user, factor=factor)
    request.session.save()
    return request, str(request.session.session_key)


def test_login_renews_the_row_and_a_fresh_store_reads_it(
    clock: Clock, security_log: pytest.LogCaptureFixture
) -> None:
    """Carry-over (d) through login(): new key, new deadline, the old row gone, and the next
    request's store verifies the MAC over both."""
    cookie = started()
    clock.advance(timedelta(hours=11))
    user = a_user()
    _, key = logged_in(cookie, user, "totp")
    assert key != cookie and row_deadline(cookie) is None
    fresh = SessionStore(key)
    stamp = clock.now.isoformat(timespec="microseconds")
    assert {name: fresh[name] for name in (USER, AGENCY, AUTH_AT, SEEN_AT, FACTOR)} == {
        USER: str(user.id),
        AGENCY: str(user.agency_id),
        AUTH_AT: stamp,
        SEEN_AT: stamp,
        FACTOR: "totp",
    }
    assert fresh.get_expiry_date() == row_deadline(key) == clock.now + absolute()
    assert not [r for r in security_log.records if r.name.startswith("django.security")]


def test_login_rotates_the_csrf_token() -> None:
    request = RequestFactory().get("/")
    request.session = SessionStore(started())
    get_token(request)
    before = request.META["CSRF_COOKIE"]
    login(request, a_user(), factor="passkey")
    assert request.META["CSRF_COOKIE"] != before
    assert request.META["CSRF_COOKIE_NEEDS_UPDATE"] is True


def test_the_same_users_session_keeps_its_data_and_another_users_is_flushed() -> None:
    user, other = committed_user(), committed_user()
    _, key = logged_in(started(), user)
    _, again = logged_in(key, user)
    assert again != key and SessionStore(again).get("probe")  # rotated, data kept
    _, switched = logged_in(again, other)
    assert row_deadline(again) is None
    store = SessionStore(switched)
    assert store[USER] == str(other.id) and "probe" not in store


@pytest.mark.parametrize("factor", ["password", "", "PASSKEY"])
def test_an_unknown_second_factor_is_refused(factor: str) -> None:
    request = RequestFactory().get("/")
    request.session = SessionStore(started())
    with pytest.raises(ValueError, match="unknown second factor"):
        login(request, a_user(), factor=factor)
    assert USER not in request.session


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("name", [USER, AGENCY])
def test_a_row_whose_user_or_agency_was_edited_is_rejected(name: str, asynchronous: bool) -> None:
    """Carry-over (i), TEN-11: SQL with SECRET_KEY can re-sign Django's blob, but not the
    tenant_source_key MAC over it, so the edited row loads as no session (logged out)."""
    _, key = logged_in(started(), a_user())
    assert get("/read", key).content == b"set"  # positive control: the genuine row verifies
    version, mac, blob = data_of(key).split(":", 2)
    store = SessionStore()
    data = store.decode(blob)
    data[name] = str(uuid.uuid4())
    set_data(key, f"{version}:{mac}:{store.encode(data)}")
    assert_rejected(key, asynchronous)
