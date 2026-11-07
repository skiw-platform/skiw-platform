"""Enrolling the first second factor, TOTP, against the real tables as skiw_app (accounts.auth.
factors; spec Flow 5.1 (4), D7, AUTH-06, AUTH-07; plan M3 §3 M3f, §4 M3f row "a user with no
enrolled TOTP is not active and cannot reach client data"). The routes are M3f-3b-2; the second
factor at sign-in is M3f-3c."""

import base64
import time
from collections.abc import Iterator
from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from accounts.auth import blob, factors, password_step, recovery, throttle, totp, wrapper
from accounts.auth.password_step import Verified, attempt
from accounts.auth.revoke import revoked
from accounts.factor_model import UserFactor
from accounts.revocation_model import SessionRevocation
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import Clock
from .logins import PASSWORD, enrolled, random_ip, unseal

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def enrolling() -> tuple[AppUser, HttpRequest]:
    """An `invited` user with a password and the pending state the enrolment link leaves."""
    user, _ = enrolled(status="invited")
    request = RequestFactory().get("/")
    request.session = SessionStore()
    password_step.start_pending(request, Verified(user.id, user.agency_id), enrol=True)
    return user, request


def begun(request: HttpRequest) -> tuple[factors.Setup, bytes]:
    setup = factors.begin_totp(request)
    assert setup is not None
    return setup, base64.b32decode(setup.secret)


def current(secret: bytes) -> str:
    return totp.code(secret, totp.step_at(time.time()))


def wrong_for(secret: bytes) -> str:
    """A code that is not valid at any step the skew accepts."""
    now = totp.step_at(time.time())
    valid = {totp.code(secret, step) for step in range(now - 3, now + 4)}
    return next(f"{n:06d}" for n in range(1_000_000) if f"{n:06d}" not in valid)


def state(user: AppUser) -> tuple[str, list[UserFactor]]:
    with with_agency(user.agency_id):
        status = AppUser.objects.get(id=user.id).status
        return status, list(UserFactor.objects.filter(user_id=user.id))


def markers(user: AppUser) -> int:
    with with_agency(user.agency_id):
        return SessionRevocation.objects.filter(user_id=user.id, session_key_hash=None).count()


def test_begin_gives_the_secret_and_a_key_uri_and_seals_the_session_copy() -> None:
    user, request = enrolling()
    setup, secret = begun(request)
    assert len(secret) == totp.SECRET_BYTES and len(setup.secret) == 32
    uri = urlsplit(setup.uri)
    assert uri.scheme == "otpauth" and uri.netloc == "totp"
    assert unquote(uri.path) == f"/SKIW Assistant:{user.email}"
    query = parse_qs(uri.query)
    assert query["secret"] == [setup.secret] and query["issuer"] == ["SKIW Assistant"]
    assert "+" not in setup.uri and "%20" in setup.uri
    kept = request.session[factors.PENDING_TOTP]
    sealed = base64.b64decode(kept["ct"])
    assert (
        len(sealed) == 48
        and secret not in sealed
        and setup.secret not in str(dict(request.session))
    )
    assert state(user) == ("invited", [])  # nothing is stored until the first code is right
    assert secret.hex() not in repr(setup) and setup.secret not in repr(setup)


def test_a_right_code_enrols_the_factor_activates_the_user_and_issues_recovery_codes() -> None:
    user, request = enrolling()
    _, secret = begun(request)
    code = current(secret)
    result = factors.confirm_totp(request, code)
    assert isinstance(result, factors.Enrolled) and result.user_id == user.id
    status, rows = state(user)
    (row,) = [r for r in rows if r.kind == "totp"]
    assert status == "active" and len(rows) == 1 + recovery.COUNT
    assert (
        blob.open_factor_secret(bytes(row.secret_ct or b""), row.id, user.id, user.agency_id)
        == secret
    )
    assert row.sign_count == totp.accept(secret, code, 0)  # the code that enrolled is spent
    assert totp.accept(secret, code, row.sign_count) is None
    assert len(result.codes) == recovery.COUNT and result.codes[0] not in repr(result)
    with with_agency(user.agency_id):
        assert recovery.consume(user.id, result.codes[0]) is True
    for key in factors.PENDING_KEYS:  # login() keeps pending keys, so none may be left to it
        assert key not in request.session


def test_enrolling_revokes_the_users_earlier_sessions_and_not_the_next_one() -> None:
    user, request = enrolling()
    before = timezone.now() - timedelta(seconds=1)
    _, secret = begun(request)
    assert markers(user) == 0
    assert isinstance(factors.confirm_totp(request, current(secret)), factors.Enrolled)
    assert markers(user) == 1
    with with_agency(user.agency_id):
        assert revoked(user.id, "any-key", before) is True
        assert revoked(user.id, "any-key", timezone.now() + timedelta(seconds=1)) is False


def test_a_failure_part_way_rolls_everything_back(monkeypatch: pytest.MonkeyPatch) -> None:
    user, request = enrolling()
    _, secret = begun(request)

    def fail(*_: object) -> list[str]:
        raise RuntimeError("recovery codes could not be made")

    monkeypatch.setattr(recovery, "generate", fail)
    with pytest.raises(RuntimeError):
        factors.confirm_totp(request, current(secret))
    assert state(user) == ("invited", []) and markers(user) == 0
    assert factors.PENDING_TOTP in request.session  # still pending: the user can try again
    monkeypatch.undo()
    assert isinstance(factors.confirm_totp(request, current(secret)), factors.Enrolled)


def test_wrong_codes_enrol_nothing_and_are_counted_until_the_user_is_limited() -> None:
    user, request = enrolling()
    _, secret = begun(request)
    other, _ = enrolling()
    for _ in range(settings.SKIW_AUTH_FAILS_PER_ACCOUNT):
        assert factors.confirm_totp(request, wrong_for(secret)) == "wrong_code"
    assert factors.confirm_totp(request, current(secret)) == "limited"  # even the right one
    assert state(user) == ("invited", [])
    assert not throttle.factor_blocked(other.id)  # another user is not counted
    with connection.cursor() as cursor:  # the key is an HMAC, never the user id
        cursor.execute("SELECT count(*) FROM auth_throttle WHERE key_hmac = %s", [user.id.bytes])
        assert cursor.fetchone() == (0,)


def test_no_enrolment_state_means_unavailable_and_counts_nothing() -> None:
    user, request = enrolling()
    assert factors.confirm_totp(request, "123456") == "unavailable"  # begin_totp not called
    login_user, _ = enrolled(status="invited")  # only the enrol mark can let it begin
    login_request = RequestFactory().get("/")
    login_request.session = SessionStore()
    password_step.start_pending(login_request, Verified(login_user.id, login_user.agency_id))
    assert factors.begin_totp(login_request) is None  # a login's pending state is not an enrolment
    assert factors.confirm_totp(login_request, "123456") == "unavailable"
    empty = RequestFactory().get("/")
    empty.session = SessionStore()
    assert factors.confirm_totp(empty, "123456") == "unavailable"
    assert factors.begin_totp(empty) is None
    assert not throttle.factor_blocked(user.id)


def test_an_expired_or_malformed_pending_state_is_cleared(clock: Clock) -> None:
    _, request = enrolling()
    _, secret = begun(request)
    clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN, seconds=1))
    assert factors.pending(request) is None
    assert factors.confirm_totp(request, current(secret)) == "unavailable"
    assert not any(key in request.session for key in factors.PENDING_KEYS)
    _, request = enrolling()
    request.session[password_step.PENDING_UNTIL] = "not a time"
    assert factors.pending(request) is None and password_step.PENDING_USER not in request.session


def test_a_second_confirmation_of_the_same_secret_is_refused() -> None:
    user, first = enrolling()
    _, secret = begun(first)
    second = RequestFactory().get("/")
    second.session = SessionStore()
    second.session.update(dict(first.session.items()))  # the same pending state, as a second tab
    assert isinstance(factors.confirm_totp(first, current(secret)), factors.Enrolled)
    assert factors.confirm_totp(second, current(secret)) == "unavailable"
    assert state(user)[0] == "active" and len(state(user)[1]) == 1 + recovery.COUNT
    assert factors.begin_totp(second) is None  # the user is no longer `invited`


def test_a_user_without_an_enrolled_factor_is_not_active_and_reaches_no_data() -> None:
    user, request = enrolling()
    ip = random_ip()
    assert attempt(user.email, PASSWORD, ip) == "failed"  # the password alone signs nobody in
    store = request.session
    assert (
        isinstance(store, SessionStore) and wrapper._signed(store) is None
    )  # a pending state is not a session

    @wrapper.authorized_action(schema=lambda body: body, permission="test.read")
    def data(request: HttpRequest, signed: wrapper.Signed, body: object) -> HttpResponse:
        return HttpResponse("client data")

    pending_request = RequestFactory().get("/")
    pending_request.session = store
    assert data(pending_request).status_code == 401
    _, secret = begun(request)
    assert isinstance(factors.confirm_totp(request, current(secret)), factors.Enrolled)
    assert attempt(user.email, PASSWORD, ip) == Verified(user.id, user.agency_id)


def test_a_login_pending_state_cannot_confirm_even_with_a_secret_in_the_session() -> None:
    user, request = enrolling()
    _, secret = begun(request)
    del request.session[password_step.PENDING_ENROL]  # now the shape of a login's pending state
    assert factors.confirm_totp(request, current(secret)) == "unavailable"
    assert state(user) == ("invited", [])
