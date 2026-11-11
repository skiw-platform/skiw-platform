"""POST /api/auth/login, the password step over HTTP, against the real tables as skiw_app (spec
Flow 5.1 (0)-(1), AUTH-05, FE-32; plan M3 §3 M3e, §4 M3e row, carry-over (h)). What
`password_step.attempt` counts and logs is tested in test_password_step_live.py (M3e-2a); these
tests cover the answers, the session and the CSRF token."""

import json
import statistics
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.auth import password_step, wrapper
from accounts.auth.login import USER, login
from accounts.auth.revoke import revoked
from accounts.session import SessionStore
from tenancy.binding import with_agency
from tests.test_csrf_gate import META, ORIGIN, assert_csrf_refused

from .conftest import Clock, absolute, committed_user, row_deadline
from .logins import FAILING, PASSWORD, consecutive, enrolled, failing, random_ip, unknown, unseal

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
URL = "/api/auth/login"
SESSION, CSRF = settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME
FAILED = b'{"error": "login-failed"}'
LIMITED = b'{"error": "limited"}'
BAND_MS, BAND_SHARE = 15.0, 0.15  # plan §4 M3e row [A]; a change needs review


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def post(client: Client, email: str, password: str, ip: str, **extra: Any) -> HttpResponse:
    response = client.post(
        URL,
        json.dumps({"email": email, "password": password}),
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=ip,
        **extra,
    )
    assert isinstance(response, HttpResponse)
    return response


def comparable(response: HttpResponse) -> tuple[int, bytes, dict[str, str]]:
    """Status, body and headers, without the per-response CSP nonce (plan §4 M3e row)."""
    headers = {k: v for k, v in response.headers.items() if k != "Content-Security-Policy"}
    return response.status_code, response.content, headers


def session_of(response: HttpResponse) -> dict[str, Any]:
    return SessionStore(response.cookies[SESSION].value).load()


@pytest.fixture
def browser(dist: Path) -> tuple[Client, str]:
    """A browser that loaded the shell: the CSRF cookie in its jar, the token from the page."""
    client = Client(enforce_csrf_checks=True)
    match = META.search(client.get("/", secure=True).content.decode())
    assert match, "the shell carries no CSRF token"
    return client, match.group(1)


def test_the_right_password_leaves_only_a_pending_state(
    browser: tuple[Client, str], clock: Clock
) -> None:
    client, before = browser
    user, email = enrolled()
    headers = {"Origin": ORIGIN, "X-CSRFToken": before}
    response = post(client, email.upper(), PASSWORD, random_ip(), headers=headers)
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    body = json.loads(response.content)
    assert body.keys() == {"next", "csrf"} and body["next"] == "second_factor"
    assert body["csrf"] != before and len(body["csrf"]) == 64  # masked, as get_token() gives it
    assert response.cookies[CSRF].value
    until = clock.now + timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN)
    assert session_of(response) == {
        password_step.PENDING_USER: str(user.id),
        password_step.PENDING_AGENCY: str(user.agency_id),
        password_step.PENDING_AT: clock.now.isoformat(timespec="microseconds"),
        password_step.PENDING_UNTIL: until.isoformat(timespec="microseconds"),
    }
    store = SessionStore(response.cookies[SESSION].value)
    store.load()
    assert wrapper._signed(store) is None  # pending is not signed in


def test_a_second_password_step_starts_a_new_session_with_its_own_lifetime(clock: Clock) -> None:
    """The pending session is a new one each time: nothing, the deadline included, is carried
    from a session that is not signed in (a pending one here)."""
    client, (_, email) = Client(), enrolled()
    first = post(client, email, PASSWORD, random_ip()).cookies[SESSION].value
    assert row_deadline(first) == clock.now + absolute()
    clock.advance(timedelta(minutes=3))
    second = post(client, email, PASSWORD, random_ip()).cookies[SESSION].value
    assert second != first and SessionStore(first).load() == {}
    assert row_deadline(second) == clock.now + absolute()


def test_the_returned_token_passes_csrf_and_the_one_from_before_does_not(
    browser: tuple[Client, str],
) -> None:
    client, before = browser
    _, email = enrolled()
    ip = random_ip()
    signed = post(client, email, PASSWORD, ip, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    token = json.loads(signed.content)["csrf"]
    old = post(client, email, PASSWORD, ip, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    assert_csrf_refused(old, "token-invalid")
    new = post(client, unknown(), PASSWORD, ip, headers={"Origin": ORIGIN, "X-CSRFToken": token})
    assert new.status_code == 401 and new.content == FAILED


def test_a_form_post_works_like_json() -> None:
    _, email = enrolled()
    response = Client().post(
        URL,
        urlencode({"email": email, "password": PASSWORD}),
        content_type="application/x-www-form-urlencoded",
        secure=True,
        REMOTE_ADDR=random_ip(),
    )
    assert response.status_code == 200 and json.loads(response.content)["next"] == "second_factor"


@pytest.mark.parametrize("case", FAILING)
def test_every_failure_gets_the_same_answer_byte_for_byte(case: str) -> None:
    """AUTH-05: known with a wrong password, unknown, invited (no password yet) and disabled with
    the right password: the same status, body and headers, and no cookie."""
    reference = post(Client(), enrolled()[1], "wrong", random_ip())
    email, password = failing(case)
    response = post(Client(), email, password, random_ip())
    assert comparable(response) == comparable(reference)
    assert response.status_code == 401 and response.content == FAILED
    assert response["Cache-Control"] == "no-store"
    assert SESSION not in response.cookies and CSRF not in response.cookies
    assert consecutive(email) == 1  # the view counted it


@pytest.mark.parametrize(
    "body, content_type",
    [
        (b"not json", "application/json"),
        (b"\xff", "application/json"),
        (b"[]", "application/json"),
        (b'{"email": "a@example.test"}', "application/json"),
        (b'{"email": 1, "password": "x"}', "application/json"),
        (b'{"email": "", "password": "x"}', "application/json"),
        (b'{"email": "a@example.test", "password": ""}', "application/json"),
        (json.dumps({"email": "a" * 255, "password": "x"}).encode(), "application/json"),
        (b'{"email": "a\\u0000@example.test", "password": "x"}', "application/json"),
        (b'{"email": "a\\ud800@example.test", "password": "x"}', "application/json"),
        (b'{"email": "a@example.test", "password": "x\\udfff"}', "application/json"),
        (b"email=a%40example.test", "application/x-www-form-urlencoded"),
        (b'{"email": "a@example.test", "password": "x"}', "text/plain"),
    ],
)
def test_a_malformed_body_gets_the_failure_answer_and_touches_no_row(
    body: bytes, content_type: str
) -> None:
    reference = post(Client(), unknown(), "wrong", random_ip())
    with CaptureQueriesContext(connection) as queries:
        response = Client().post(URL, body, content_type=content_type, secure=True)
    assert isinstance(response, HttpResponse)
    assert comparable(response) == comparable(reference)
    assert queries.captured_queries == []


def test_the_longest_address_is_not_malformed() -> None:
    address = unknown().rjust(254, "a")  # fresh each run: the throttle rows stay
    assert len(address) == 254
    with CaptureQueriesContext(connection) as queries:
        assert post(Client(), address, "wrong", random_ip()).content == FAILED
    assert queries.captured_queries  # it reached the throttle and the lookup


def test_a_limited_answer_is_the_same_for_known_and_unknown() -> None:
    _, email = enrolled()
    missing = unknown()
    for count in range(settings.SKIW_AUTH_FAILS_PER_ACCOUNT):
        assert post(Client(), email, "wrong", random_ip()).content == FAILED, count
        assert post(Client(), missing, "wrong", random_ip()).content == FAILED, count
    known = post(Client(), email, PASSWORD, random_ip())
    absent = post(Client(), missing, PASSWORD, random_ip())
    assert comparable(known) == comparable(absent)
    assert known.status_code == 429 and known.content == LIMITED
    assert known["Cache-Control"] == "no-store" and SESSION not in known.cookies


def test_a_signed_in_session_is_retired_before_the_pending_one_starts() -> None:
    """A rotation of an authenticated session leaves a marker (plan M3 §3 M3d), here too."""
    signer = committed_user()
    request = RequestFactory().post("/", secure=True)
    request.session = store = SessionStore()
    login(request, signer, factor="passkey")
    store.save()
    old = str(store.session_key)
    client = Client()
    client.cookies[SESSION] = old
    _, email = enrolled()
    response = post(client, email, PASSWORD, random_ip())
    assert response.status_code == 200
    assert response.cookies[SESSION].value != old and USER not in session_of(response)
    assert SessionStore(old).load() == {}
    with with_agency(signer.agency_id):
        assert revoked(signer.id, old, timezone.now())


def test_a_failure_leaves_a_signed_in_session_alone() -> None:
    signer = committed_user()
    request = RequestFactory().post("/", secure=True)
    request.session = store = SessionStore()
    login(request, signer, factor="passkey")
    store.save()
    client = Client()
    client.cookies[SESSION] = str(store.session_key)
    assert post(client, unknown(), PASSWORD, random_ip()).status_code == 401
    assert SessionStore(str(store.session_key)).load()[USER] == str(signer.id)


def elapsed_ms(email: str, password: str) -> float:
    client, ip = Client(), random_ip()
    start = time.perf_counter()
    response = post(client, email, password, ip)
    took = (time.perf_counter() - start) * 1000
    assert response.status_code == 401
    return took


def test_known_and_unknown_answer_within_one_timing_band() -> None:
    """Plan §4 M3e row, timing (2) statistical, at the real T5 parameters: every request has its
    own account and IP keys, so no limit is reached. 5 warm-up calls, then 20 interleaved pairs of
    a known email with a wrong password and an unknown email; the medians must lie within
    max(15 ms, 15 %). No retries."""
    known = [enrolled()[1] for _ in range(23)]
    for email in known[:3]:
        elapsed_ms(email, "wrong")
    for _ in range(2):
        elapsed_ms(unknown(), "wrong")
    pairs = [(elapsed_ms(email, "wrong"), elapsed_ms(unknown(), "wrong")) for email in known[3:]]
    a = statistics.median(k for k, _ in pairs)
    b = statistics.median(u for _, u in pairs)
    assert abs(a - b) <= max(BAND_MS, BAND_SHARE * min(a, b)), (a, b)
