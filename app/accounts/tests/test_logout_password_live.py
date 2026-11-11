"""POST /api/auth/logout and POST /api/auth/password against the real tables as skiw_app (spec
AUTH-04, AUTH-06, AUTH-07, AUTH-13 server half; plan M3 §3 M3h; DECISIONS M3h-4). The AUTH-07
tests run on the real clock: the re-issued login time is the app's clock and the marker the
database's, so the `clock` fixture (app time frozen in the past) would revoke the re-issued session
too. Requests come from random IPs, so the per-IP budget never mixes tests."""

import json
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.db import connection
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory

from accounts.auth import blob, password_step, passwords
from accounts.auth.login import AUTH_AT, FACTOR, login
from accounts.auth.revoke import mark
from accounts.session import SessionStore, stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF, ORIGIN, assert_csrf_refused

from . import test_second_factor_live as sign_in
from .conftest import COOKIE, assert_deleted, committed_user, row_deadline
from .logins import PASSWORD, consecutive, enrolled, random_ip, unseal
from .test_action_wrapper_live import markers, put_back, saved_row, signed_in
from .test_auth_throttle_live import events as locked_events
from .test_stepup_route_live import step_up

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of sign_in.STEP
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
NEW = "a new and longer passphrase"
LIMIT = settings.SKIW_AUTH_FAILS_PER_ACCOUNT


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def client(cookie: str) -> Client:
    browser = Client()
    browser.cookies[COOKIE] = cookie
    return browser


def probe(cookie: str, path: str = "/action-probe") -> int:
    return client(cookie).post(path, b"{}", content_type="application/json").status_code


def answer(response: "Response") -> tuple[int, Any]:
    assert response["Cache-Control"] == "no-store"
    return response.status_code, json.loads(response.content)


def logout(browser: Client, body: bytes = b"{}", **extra: Any) -> "Response":
    return browser.post("/api/auth/logout", body, content_type="application/json", **extra)


def change(cookie: str, current: str = PASSWORD, new: str = NEW, raw: bytes | None = None) -> Any:
    body = json.dumps({"current": current, "new": new}) if raw is None else raw
    return client(cookie).post(
        "/api/auth/password", body, content_type="application/json", REMOTE_ADDR=random_ip()
    )


def signs_in(email: str, password: str) -> bool:
    return isinstance(password_step.attempt(email, password, random_ip()), password_step.Verified)


def test_logout_ends_the_session_and_its_row_put_back_stays_refused() -> None:
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    row = saved_row(cookie)
    response = logout(client(cookie))
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "signed_out", {"next", "csrf"})
    assert_deleted(response)
    assert row_deadline(cookie) is None and markers(user) == [stored_key(cookie)]
    assert probe(cookie) == 401
    put_back(row)
    assert probe(cookie) == 401  # the marker, not only the missing row


def test_logout_takes_no_input_and_then_the_session_stays() -> None:
    cookie = signed_in(committed_user(), factor="totp")
    assert answer(logout(client(cookie), b'{"all": true}')) == (400, {"error": "invalid"})
    assert probe(cookie) == 200


def test_logout_rotates_the_csrf_token_and_the_old_one_is_refused() -> None:
    browser = Client(enforce_csrf_checks=True)
    request = RequestFactory().post("/", secure=True)
    request.session = store = SessionStore()
    login(request, committed_user(), factor="totp")
    store.save()
    browser.cookies[settings.SESSION_COOKIE_NAME] = str(store.session_key)
    browser.cookies[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
    old = get_token(request)
    response = logout(browser, secure=True, headers={"Origin": ORIGIN, "X-CSRFToken": old})
    assert response.status_code == 200
    new = json.loads(response.content)["csrf"]

    def send(token: str) -> Any:
        headers = {"Origin": ORIGIN, "X-CSRFToken": token}
        kind = "application/json"
        return browser.post("/csrf-probe", b"{}", content_type=kind, secure=True, headers=headers)

    assert_csrf_refused(send(old), "token-invalid")
    assert send(new).status_code == 200


def test_a_password_change_ends_every_other_session_and_reissues_this_one() -> None:
    user, email = enrolled()
    cookie, other = signed_in(user, factor="totp"), signed_in(user, factor="totp")
    deadline, before = row_deadline(cookie), SessionStore(cookie).load()
    response = change(cookie)
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "changed", {"next", "csrf"})
    fresh = response.cookies[COOKIE].value
    after = SessionStore(fresh).load()
    assert fresh != cookie and row_deadline(fresh) == deadline  # not a new lifetime
    assert after[FACTOR] == "totp" and after[AUTH_AT] > before[AUTH_AT]
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    assert signs_in(email, NEW) and not signs_in(email, PASSWORD)


def test_a_step_up_made_before_the_change_no_longer_counts() -> None:
    user, secret, _ = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    assert step_up(client(cookie), sign_in.code_at(secret, sign_in.STEP)).status_code == 200
    assert probe(cookie, "/stepup-probe") == 200
    fresh = change(cookie).cookies[COOKIE].value
    assert probe(fresh, "/stepup-probe") == 403


def test_wrong_current_passwords_use_the_login_budget_and_change_nothing() -> None:
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")
    for n in range(LIMIT):
        assert answer(change(cookie, current="wrong")) == (401, {"error": "password-wrong"})
        assert consecutive(email) == n + 1
    assert answer(change(cookie)) == (429, {"error": "limited"})  # even the right one
    assert password_step.attempt(email, PASSWORD, random_ip()) == "limited"  # one budget
    assert probe(cookie) == 200 and markers(user) == []


def test_ten_wrong_in_a_row_lock_the_login_and_raise_the_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SKIW_AUTH_FAILS_PER_ACCOUNT", 100)  # the lock, not the budget
    after = settings.SKIW_AUTH_LOCK_AFTER
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")
    for _ in range(after):
        assert answer(change(cookie, current="wrong"))[0] == 401
    assert locked_events(email) == [{"consecutive": after}]
    assert answer(change(cookie))[0] == 429 and not signs_in(email, PASSWORD)


@pytest.mark.parametrize("case", ["right", "wrong", "foreign"])
def test_each_attempt_costs_one_argon2_verify(case: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blob that names another user is judged by the dummy, never by its own hash."""
    user, email = enrolled()
    if case == "foreign":
        record = blob.LoginRecord(uuid.uuid4(), user.agency_id, passwords.hash_password(PASSWORD))
        with with_agency(user.agency_id):
            AppUser.objects.filter(id=user.id).update(login_blob_ct=blob.seal_login(record, email))
    calls: list[str] = []

    def counting(name: str) -> Callable[..., object]:
        real = getattr(passwords, name)

        def counted(*args: str) -> object:
            calls.append(name)
            return real(*args)

        return counted

    for name in ("verify", "dummy_verify"):
        monkeypatch.setattr(passwords, name, counting(name))
    cookie = signed_in(user, factor="totp")
    status = change(cookie, current="wrong" if case == "wrong" else PASSWORD).status_code
    assert (status, calls) == {
        "right": (200, ["verify"]),
        "wrong": (401, ["verify"]),
        "foreign": (401, ["dummy_verify", "verify"]),  # the one verify is of the dummy hash
    }[case]


def test_a_short_new_password_is_refused_before_any_count_or_argon2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")

    def no_argon2(*args: object) -> None:
        raise AssertionError("Argon2 ran")

    for name in ("verify", "dummy_verify", "hash_password"):
        monkeypatch.setattr(passwords, name, no_argon2)
    short = "x" * (settings.SKIW_PW_MIN_LENGTH - 1)
    assert answer(change(cookie, new=short)) == (400, {"error": "password-short"})
    assert consecutive(email) == 0 and probe(cookie) == 200


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        json.dumps({"current": PASSWORD}).encode(),
        json.dumps({"current": PASSWORD, "new": NEW, "agency_id": str(uuid.uuid4())}).encode(),
        json.dumps({"current": 1, "new": NEW}).encode(),
        json.dumps({"current": PASSWORD, "new": NEW + "\x00"}).encode(),
        b'{"current": "\\ud800", "new": "a new and longer passphrase"}',
        b"[]",
        b"not json",
    ],
)
def test_a_malformed_body_is_400_and_counts_nothing(raw: bytes) -> None:
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")
    assert answer(change(cookie, raw=raw)) == (400, {"error": "invalid"})
    assert consecutive(email) == 0 and signs_in(email, PASSWORD)


def test_a_password_set_meanwhile_wins_and_nothing_is_revoked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")
    real = passwords.hash_password

    def racing(password: str) -> str:  # another request changes the password first
        record = blob.LoginRecord(user.id, user.agency_id, real("set meanwhile, elsewhere"))
        with with_agency(user.agency_id):
            AppUser.objects.filter(id=user.id).update(login_blob_ct=blob.seal_login(record, email))
        return real(password)

    monkeypatch.setattr(passwords, "hash_password", racing)
    assert answer(change(cookie)) == (409, {"error": "changed"})
    assert probe(cookie) == 200 and markers(user) == []
    assert signs_in(email, "set meanwhile, elsewhere") and not signs_in(email, NEW)


def wait_for_a_lock_waiter() -> None:
    """The barrier: returns once another skiw_app backend waits on a lock."""
    deadline = time.monotonic() + 10
    with connection.cursor() as cursor:
        while time.monotonic() < deadline:
            cursor.execute("SELECT pg_stat_clear_snapshot()")  # else one snapshot per transaction
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                " AND usename = current_user AND pid <> pg_backend_pid()"
            )
            if cursor.fetchone()[0]:
                return
            time.sleep(0.01)
    raise AssertionError("the password change never waited on the user's row")


def test_a_change_waiting_on_hold_sees_a_marker_committed_meanwhile_and_is_not_reissued() -> None:
    """The resurrection race (DECISIONS M3h-4): B passed the wrapper before A's user-wide marker,
    so only `hold` stops B re-issuing itself past it."""
    user, email = enrolled()
    cookie = signed_in(user, factor="totp")
    results: list[Any] = []

    def session_b() -> None:
        try:
            results.append(change(cookie))
        finally:
            connection.close()

    b = threading.Thread(target=session_b)
    with with_agency(user.agency_id):  # session A's credential change
        AppUser.objects.select_for_update().filter(id=user.id).first()
        b.start()
        wait_for_a_lock_waiter()
        mark(user.agency_id, user.id, None)
    b.join(timeout=30)
    [response] = results
    assert answer(response) == (401, {"error": "signed-out"})
    assert_deleted(response)
    assert probe(cookie) == 401 and markers(user) == [None]
    assert signs_in(email, PASSWORD) and not signs_in(email, NEW)
