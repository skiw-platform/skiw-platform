"""POST /api/auth/enrol, the enrolment link's password over HTTP, against the real tables as
skiw_app (spec AUTH-08, AUTH-05, Flow 5.1 (4), FE-32; plan M3 §3 M3e, §4 M3e row "enrolment link:
works once, expired, tampered, reused"). What `enrol.redeem` accepts is tested in
test_enrol_live.py (M3e-3a); these tests cover the answers, the session and the CSRF token."""

import json
import unicodedata
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.auth import blob, password_step, passwords, wrapper
from accounts.auth.login import USER, login
from accounts.auth.revoke import revoked
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import META, ORIGIN, assert_csrf_refused

from .conftest import Clock, committed_user
from .logins import PASSWORD, random_ip, unseal
from .test_enrol_live import invited, later, row, sealed

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
URL = "/api/auth/enrol"
SESSION, CSRF = settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME
FAILED = b'{"error": "enrol-failed"}'


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def post(client: Client, token: str, password: str, **extra: Any) -> HttpResponse:
    response = client.post(
        URL,
        json.dumps({"token": token, "password": password}),
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=random_ip(),
        **extra,
    )
    assert isinstance(response, HttpResponse)
    return response


def comparable(response: HttpResponse) -> tuple[int, bytes, dict[str, str]]:
    """Status, body and headers, without the per-response CSP nonce (plan §4 M3e row)."""
    headers = {k: v for k, v in response.headers.items() if k != "Content-Security-Policy"}
    return response.status_code, response.content, headers


def reference() -> HttpResponse:
    return post(Client(), "not a token", PASSWORD)


def assert_refused(response: HttpResponse) -> None:
    """AUTH-05: one answer for every refusal, no cookie."""
    assert comparable(response) == comparable(reference())
    assert response.status_code == 401 and response.content == FAILED
    assert response["Cache-Control"] == "no-store"
    assert SESSION not in response.cookies and CSRF not in response.cookies


def session_of(response: HttpResponse) -> dict[str, Any]:
    return SessionStore(response.cookies[SESSION].value).load()


@pytest.fixture
def browser(dist: Path) -> tuple[Client, str]:
    """A browser that loaded the shell: the CSRF cookie in its jar, the token from the page."""
    client = Client(enforce_csrf_checks=True)
    match = META.search(client.get("/", secure=True).content.decode())
    assert match, "the shell carries no CSRF token"
    return client, match.group(1)


def test_a_link_sets_the_password_and_leaves_only_a_pending_enrolment(
    browser: tuple[Client, str], clock: Clock
) -> None:
    client, before = browser
    email, token = invited()
    user = row(email)
    response = post(client, token, PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    body = json.loads(response.content)
    assert body.keys() == {"next", "csrf"} and body["next"] == "enrol_factor"
    assert body["csrf"] != before and len(body["csrf"]) == 64  # masked, as get_token() gives it
    assert response.cookies[CSRF].value
    until = clock.now + timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN)
    assert session_of(response) == {
        password_step.PENDING_USER: str(user.id),
        password_step.PENDING_AGENCY: str(user.agency_id),
        password_step.PENDING_AT: clock.now.isoformat(timespec="microseconds"),
        password_step.PENDING_UNTIL: until.isoformat(timespec="microseconds"),
        password_step.PENDING_ENROL: True,
    }
    store = SessionStore(response.cookies[SESSION].value)
    store.load()
    assert wrapper._signed(store) is None  # pending is not signed in
    record = blob.open_login(sealed(email), email)
    assert record is not None and passwords.verify(record.password_hash, PASSWORD)
    assert row(email).status == "invited"  # the first second factor activates (M3f, M3g)


def test_the_returned_token_passes_csrf_and_the_one_from_before_does_not(
    browser: tuple[Client, str],
) -> None:
    client, before = browser
    _, token = invited()
    signed = post(client, token, PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    assert signed.status_code == 200
    _, other = invited()
    old = post(client, other, PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": before})
    assert_csrf_refused(old, "token-invalid")
    fresh = json.loads(signed.content)["csrf"]
    new = post(client, "not a token", PASSWORD, headers={"Origin": ORIGIN, "X-CSRFToken": fresh})
    assert new.status_code == 401 and new.content == FAILED


def test_a_link_works_once() -> None:
    email, token = invited()
    assert post(Client(), token, PASSWORD).status_code == 200
    first = sealed(email)
    assert_refused(post(Client(), token, "a different password"))
    assert sealed(email) == first


def test_an_expired_link_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    email, token = invited()
    later(monkeypatch, settings.SKIW_ENROL_LINK_MIN * 60 + 1)
    assert_refused(post(Client(), token, PASSWORD))
    assert row(email).login_blob_ct is None


def test_a_tampered_link_is_refused() -> None:
    email, token = invited()
    value, _, signature = token.rpartition(":")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    assert_refused(post(Client(), f"{value}:{flipped}", PASSWORD))
    assert row(email).login_blob_ct is None


def test_a_link_for_a_user_no_longer_invited_is_refused() -> None:
    email, token = invited()
    agency, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    with with_agency(agency):
        AppUser.objects.filter(email=email).update(status="disabled")
    assert_refused(post(Client(), token, PASSWORD))


@pytest.mark.parametrize("length", [settings.SKIW_PW_MIN_LENGTH - 1, 1])
def test_a_short_password_is_refused_and_the_link_still_works(length: int) -> None:
    """Owner 2026-11-05: at least 12 characters. The refusal is the same answer as any other and
    writes nothing, so the user can try again with the same link."""
    email, token = invited()
    assert_refused(post(Client(), token, "p" * length))
    assert row(email).login_blob_ct is None
    exact = "p" * settings.SKIW_PW_MIN_LENGTH
    assert post(Client(), token, exact).status_code == 200
    record = blob.open_login(sealed(email), email)
    assert record is not None and passwords.verify(record.password_hash, exact)


def test_a_form_post_works_like_json() -> None:
    _, token = invited()
    response = Client().post(
        URL,
        urlencode({"token": token, "password": PASSWORD}),
        content_type="application/x-www-form-urlencoded",
        secure=True,
    )
    assert response.status_code == 200 and json.loads(response.content)["next"] == "enrol_factor"


@pytest.mark.parametrize(
    "body, content_type",
    [
        (b"not json", "application/json"),
        (b"\xff", "application/json"),
        (b"[]", "application/json"),
        (b'{"token": "t"}', "application/json"),
        (b'{"token": 1, "password": "correct horse battery"}', "application/json"),
        (b'{"token": "t", "password": ["correct horse battery"]}', "application/json"),
        (b'{"token": "", "password": ""}', "application/json"),
        (b"token=t", "application/x-www-form-urlencoded"),
        (b'{"token": "t", "password": "correct horse battery"}', "text/plain"),
    ],
)
def test_a_malformed_body_gets_the_failure_answer_and_touches_no_row(
    body: bytes, content_type: str
) -> None:
    expected = comparable(reference())
    with CaptureQueriesContext(connection) as queries:
        response = Client().post(URL, body, content_type=content_type, secure=True)
    assert isinstance(response, HttpResponse)
    assert comparable(response) == expected
    assert queries.captured_queries == []


@pytest.mark.parametrize("password", [["p"] * 12, 123456789012, None])
def test_a_good_link_with_a_password_that_is_not_a_string_is_refused(password: object) -> None:
    email, token = invited()
    response = Client().post(
        URL,
        json.dumps({"token": token, "password": password}),
        content_type="application/json",
        secure=True,
    )
    assert isinstance(response, HttpResponse)
    assert_refused(response)
    assert row(email).login_blob_ct is None


def test_a_good_link_with_a_lone_surrogate_in_the_password_is_refused() -> None:
    """JSON allows "\\ud800"; UTF-8 does not, so Argon2 would raise and answer 500 (UNI-03)."""
    email, token = invited()
    assert_refused(post(Client(), token, PASSWORD + "\ud800"))
    assert row(email).login_blob_ct is None


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_a_password_set_in_one_unicode_form_verifies_in_the_other(
    form: Literal["NFC", "NFD"],
) -> None:
    """PR 115 R1 P3 #1: an NFC device enrols, an NFD one signs in, or the other way round."""
    email, token = invited()
    password = unicodedata.normalize(form, "caf\u00e9 cr\u00e8me br\u00fbl\u00e9e")
    assert post(Client(), token, password).status_code == 200
    record = blob.open_login(sealed(email), email)
    assert record is not None
    other = unicodedata.normalize("NFD" if form == "NFC" else "NFC", password)
    assert other != password and passwords.verify(record.password_hash, other)


def test_the_minimum_is_counted_after_normalising() -> None:
    """Twelve NFD code points that are six characters after NFKC are refused; twelve characters
    that NFD spells in 24 code points are not short."""
    email, token = invited()
    assert_refused(post(Client(), token, unicodedata.normalize("NFD", "\u00e9" * 6)))
    assert row(email).login_blob_ct is None
    assert post(Client(), token, unicodedata.normalize("NFD", "\u00e9" * 12)).status_code == 200


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
    _, token = invited()
    response = post(client, token, PASSWORD)
    assert response.status_code == 200
    assert response.cookies[SESSION].value != old and USER not in session_of(response)
    assert SessionStore(old).load() == {}
    with with_agency(signer.agency_id):
        assert revoked(signer.id, old, timezone.now())


def test_a_refusal_leaves_a_signed_in_session_alone() -> None:
    signer = committed_user()
    request = RequestFactory().post("/", secure=True)
    request.session = store = SessionStore()
    login(request, signer, factor="passkey")
    store.save()
    client = Client()
    client.cookies[SESSION] = str(store.session_key)
    assert post(client, "not a token", PASSWORD).status_code == 401
    assert SessionStore(str(store.session_key)).load()[USER] == str(signer.id)
