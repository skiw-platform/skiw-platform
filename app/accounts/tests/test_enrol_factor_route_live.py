"""POST /api/auth/enrol/totp and /api/auth/enrol/totp/confirm over HTTP, against the real tables as
skiw_app (spec Flow 5.1 (4), D7, AUTH-06, AUTH-07; plan M3 §3 M3f). What `factors` does is tested in
test_factors_live.py (M3f-3b-1); these tests cover the answers, the CSRF token, the session the
confirmation leaves (a completed login) and the expiry rule."""

import base64
import json
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import Client
from pytest_django import Settings

from accounts.auth import enrol, factors, password_step, throttle, totp, wrapper
from accounts.auth.login import FACTOR
from accounts.auth.password_step import Verified, attempt
from accounts.session import SessionStore
from tests.test_csrf_gate import META, ORIGIN

from .conftest import Clock
from .logins import PASSWORD, enrolled, random_ip, unseal
from .test_enrol_live import invited, row
from .test_enrol_route_live import browser as browser_fixture
from .test_enrol_route_live import post
from .test_factors_live import state

browser = browser_fixture
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
BEGIN, CONFIRM = "/api/auth/enrol/totp", "/api/auth/enrol/totp/confirm"
SESSION = settings.SESSION_COOKIE_NAME
EXPIRED = {"error": "enrol-expired"}


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def send(client: Client, path: str, token: str, body: Any = None, **extra: Any) -> HttpResponse:
    response = client.post(
        path,
        json.dumps({} if body is None else body),
        content_type="application/json",
        secure=True,
        headers={"Origin": ORIGIN, "X-CSRFToken": token},
        **extra,
    )
    assert isinstance(response, HttpResponse)
    return response


def enrolling(started: tuple[Client, str]) -> tuple[Client, str, str]:
    """A browser that followed an enrolment link and set its password: the client, the CSRF token
    the answer returned and the user's email."""
    client, before = started
    email, link = invited()
    response = post(client, link, PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    assert response.status_code == 200
    return client, json.loads(response.content)["csrf"], email


def begun(client: Client, token: str) -> bytes:
    response = send(client, BEGIN, token)
    assert response.status_code == 200
    return base64.b32decode(json.loads(response.content)["secret"])


def current(secret: bytes) -> str:
    return totp.code(secret, totp.step_at(time.time()))


def wrong_for(secret: bytes) -> str:
    now = totp.step_at(time.time())
    valid = {totp.code(secret, step) for step in range(now - 3, now + 4)}
    return next(f"{n:06d}" for n in range(1_000_000) if f"{n:06d}" not in valid)


def stored_session(client: Client) -> SessionStore:
    store = SessionStore(client.cookies[SESSION].value)
    store.load()
    return store


def test_the_whole_enrolment_ends_in_a_signed_in_session_and_ten_codes(
    browser: tuple[Client, str],
) -> None:
    client, token, email = enrolling(browser)
    begin = send(client, BEGIN, token)
    assert begin.status_code == 200 and begin["Cache-Control"] == "no-store"
    shown = json.loads(begin.content)
    assert shown.keys() == {"secret", "uri"} and shown["uri"].startswith("otpauth://totp/SKIW%20")
    response = send(client, CONFIRM, token, {"code": current(base64.b32decode(shown["secret"]))})
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    body = json.loads(response.content)
    assert body.keys() == {"next", "recovery_codes", "csrf"} and body["next"] == "signed_in"
    assert len(set(body["recovery_codes"])) == 10 and body["csrf"] != token
    session = stored_session(client)
    signed = wrapper._signed(session)
    assert signed is not None and signed.user_id == row(email).id and session[FACTOR] == "totp"
    assert not any(key in session for key in factors.PENDING_KEYS)
    assert state(row(email))[0] == "active"
    assert isinstance(attempt(email, PASSWORD, random_ip()), Verified)
    again = send(client, BEGIN, body["csrf"])  # a signed-in session is not an enrolment
    assert again.status_code == 401 and json.loads(again.content) == EXPIRED


def test_without_an_enrolment_session_both_routes_answer_expired_and_set_no_cookie(
    browser: tuple[Client, str],
) -> None:
    client, token = browser
    for path, body in ((BEGIN, None), (CONFIRM, {"code": "123456"})):
        response = send(client, path, token, body)
        assert response.status_code == 401 and json.loads(response.content) == EXPIRED
        assert SESSION not in response.cookies


def test_a_login_pending_session_is_not_an_enrolment(browser: tuple[Client, str]) -> None:
    client, token = browser
    _, email = enrolled(status="active")
    login = client.post(
        "/api/auth/login",
        json.dumps({"email": email, "password": PASSWORD}),
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=random_ip(),
        headers={"Origin": ORIGIN, "X-CSRFToken": token},
    )
    assert login.status_code == 200
    fresh = json.loads(login.content)["csrf"]
    assert send(client, BEGIN, fresh).status_code == 401
    assert send(client, CONFIRM, fresh, {"code": "123456"}).status_code == 401


def test_wrong_codes_are_refused_counted_and_end_in_limited(
    browser: tuple[Client, str],
) -> None:
    client, token, email = enrolling(browser)
    secret = begun(client, token)
    for _ in range(settings.SKIW_AUTH_FAILS_PER_ACCOUNT):
        response = send(client, CONFIRM, token, {"code": wrong_for(secret)})
        assert response.status_code == 401 and json.loads(response.content) == {
            "error": "code-wrong"
        }
    response = send(client, CONFIRM, token, {"code": current(secret)})
    assert response.status_code == 429 and json.loads(response.content) == {"error": "limited"}
    assert state(row(email)) == ("invited", [])
    assert throttle.factor_blocked(row(email).id)


@pytest.mark.parametrize("body", [None, {}, {"code": 123456}, {"code": None}, {"code": ["1"]}])
def test_a_confirm_body_without_a_text_code_is_invalid_and_counts_nothing(
    browser: tuple[Client, str], body: Any
) -> None:
    client, token, email = enrolling(browser)
    begun(client, token)
    response = send(client, CONFIRM, token, body)
    assert response.status_code == 400 and json.loads(response.content) == {"error": "invalid"}
    assert not throttle.factor_blocked(row(email).id) and state(row(email))[0] == "invited"
    other = client.post(
        CONFIRM,
        "code=123456",
        content_type="text/plain",
        secure=True,
        headers={"Origin": ORIGIN, "X-CSRFToken": token},
    )
    assert other.status_code == 400


def test_a_form_post_confirms_like_json(browser: tuple[Client, str]) -> None:
    client, token, email = enrolling(browser)
    secret = begun(client, token)
    response = client.post(
        CONFIRM,
        f"code={current(secret)}",
        content_type="application/x-www-form-urlencoded",
        secure=True,
        headers={"Origin": ORIGIN, "X-CSRFToken": token},
    )
    assert response.status_code == 200 and state(row(email))[0] == "active"


def test_a_second_begin_replaces_the_secret_and_only_the_latest_confirms(
    browser: tuple[Client, str],
) -> None:
    client, token, email = enrolling(browser)
    first, second = begun(client, token), begun(client, token)
    assert first != second
    refused = send(client, CONFIRM, token, {"code": wrong_for(second)})
    assert refused.status_code == 401
    assert send(client, CONFIRM, token, {"code": current(second)}).status_code == 200
    assert state(row(email))[0] == "active"


def test_the_enrolment_window_ends_and_a_new_link_starts_again(
    browser: tuple[Client, str], clock: Clock
) -> None:
    client, token, email = enrolling(browser)
    secret = begun(client, token)
    clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN, seconds=1))
    for path, body in ((BEGIN, None), (CONFIRM, {"code": current(secret)})):
        response = send(client, path, token, body)
        assert response.status_code == 401 and json.loads(response.content) == EXPIRED
    assert state(row(email)) == ("invited", [])  # the password is set; the user is still invited
    assert attempt(email, PASSWORD, random_ip()) == "failed"
    fresh = Client(
        enforce_csrf_checks=True
    )  # a new link from the operator (runbook "Enrol a user")
    link = enrol.invite(email, "New User")
    shell = fresh.get("/", secure=True).content.decode()
    match = META.search(shell)
    assert match
    response = post(
        fresh, link, PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": match.group(1)}
    )
    new_token = json.loads(response.content)["csrf"]
    assert (
        send(fresh, CONFIRM, new_token, {"code": current(begun(fresh, new_token))}).status_code
        == 200
    )


def test_the_pending_state_is_the_one_the_password_route_left(
    browser: tuple[Client, str], settings: Settings
) -> None:
    client, token, _ = enrolling(browser)
    session = stored_session(client)
    assert session[password_step.PENDING_ENROL] is True and factors.PENDING_TOTP not in session
    begun(client, token)
    assert factors.PENDING_TOTP in stored_session(client)
