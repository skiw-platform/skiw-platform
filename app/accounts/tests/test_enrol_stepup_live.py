"""Finishing enrolment counts as a fresh `factor.change` step-up for the new session, and for
nothing else (DECISIONS M3g-2s-1; spec D7, AUTH-09). Enrolment over HTTP, then the passkey add
routes, against the real tables as skiw_app. Users, factors and step-up rows are committed and
kept; the passkeys a test adds are deleted after it (no step-up names one)."""

import json
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.utils import timezone

from accounts import views
from accounts.auth import stepup, totp
from accounts.factor_model import UserFactor
from accounts.session import SessionStore, stored_key
from accounts.stepup_model import AuthStepup
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF, META, ORIGIN

from . import test_passkey_change_live as change
from .authenticator import SoftAuthenticator, unb64url
from .logins import PASSWORD, random_ip
from .test_action_wrapper_live import signed_in
from .test_enrol_factor_route_live import CONFIRM, SESSION, begun, current, enrolling, send
from .test_enrol_live import row
from .test_enrol_route_live import browser as browser_fixture
from .test_enrol_route_live import unsealed as unsealed_fixture
from .test_logout_password_live import answer

browser = browser_fixture
unsealed = unsealed_fixture  # autouse
no_passkey_kept = change.no_passkey_kept  # autouse
relying_party = change.relying_party  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
OTHER = "test.other"  # a second purpose, listed only by the test that needs it


def enrolled_in(started: tuple[Client, str]) -> tuple[AppUser, bytes, str]:
    """An invited user enrolled over HTTP: the user, the TOTP secret and the session cookie the
    confirmation left."""
    client, token, email = enrolling(started)
    secret = begun(client, token)
    response = send(client, CONFIRM, token, {"code": current(secret)})
    assert response.status_code == 200 and json.loads(response.content)["next"] == "signed_in"
    return row(email), secret, client.cookies[SESSION].value


def stepups(user: AppUser) -> list[AuthStepup]:
    with with_agency(user.agency_id):
        return list(AuthStepup.objects.filter(user_id=user.id))


def the_totp(user: AppUser) -> uuid.UUID:
    with with_agency(user.agency_id):
        return UserFactor.objects.get(user_id=user.id, kind="totp").id


def session_request(cookie: str) -> HttpRequest:
    request = RequestFactory().post("/")
    request.session = SessionStore(cookie)
    return request


def added(cookie: str) -> int:
    """The status of adding a passkey, begin then confirm, with no code typed."""
    status, body = answer(change.begin(cookie))
    if status != 200:
        return status
    challenge = unb64url(body["options"]["challenge"])
    return change.confirm(cookie, SoftAuthenticator().register(challenge)).status_code


def test_right_after_enrolment_a_passkey_is_added_without_a_code(
    browser: tuple[Client, str],
) -> None:
    user, _, cookie = enrolled_in(browser)
    [evidence] = stepups(user)
    assert evidence.session_key_hash == stored_key(cookie)  # the new key, not the pending one
    assert evidence.purpose == stepup.FACTOR_CHANGE
    assert added(cookie) == 200 and len(change.passkeys(user)) == 1


def test_the_evidence_mac_names_the_new_totp(browser: tuple[Client, str]) -> None:
    user, _, _ = enrolled_in(browser)
    [evidence] = stepups(user)
    assert evidence.factor_id == the_totp(user) and stepup._genuine(evidence)
    evidence.factor_id = uuid.uuid4()
    assert not stepup._genuine(evidence)


def test_another_session_of_the_user_still_needs_a_step_up(browser: tuple[Client, str]) -> None:
    user, _, _ = enrolled_in(browser)
    other = signed_in(user, factor="totp")
    assert answer(change.begin(other)) == change.STEPUP
    assert change.passkeys(user) == []


def test_the_evidence_lapses_after_the_step_up_age(
    browser: tuple[Client, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _, cookie = enrolled_in(browser)
    later = timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN, seconds=1)
    monkeypatch.setattr(stepup, "timezone", SimpleNamespace(now=lambda: timezone.now() + later))
    assert answer(change.begin(cookie)) == change.STEPUP
    assert change.passkeys(user) == []


def test_the_evidence_counts_for_no_other_purpose(
    browser: tuple[Client, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    listed = frozenset({stepup.FACTOR_CHANGE, OTHER})
    monkeypatch.setattr(stepup, "PURPOSES", listed)
    monkeypatch.setattr(views, "PURPOSES", listed)
    user, _, cookie = enrolled_in(browser)
    assert [e.purpose for e in stepups(user)] == [stepup.FACTOR_CHANGE]
    with with_agency(user.agency_id):
        assert stepup.recent(session_request(cookie), OTHER) is None
        assert stepup.recent(session_request(cookie), stepup.FACTOR_CHANGE) is not None


def test_a_plain_sign_in_with_a_code_records_no_step_up(browser: tuple[Client, str]) -> None:
    user, secret, _ = enrolled_in(browser)
    client = Client(enforce_csrf_checks=True)
    match = META.search(client.get("/", secure=True).content.decode())
    assert match
    headers = {"Origin": ORIGIN, "X-CSRFToken": match.group(1)}
    password = client.post(
        "/api/auth/login",
        json.dumps({"email": user.email, "password": PASSWORD}),
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=random_ip(),
        headers=headers,
    )
    assert password.status_code == 200
    headers["X-CSRFToken"] = json.loads(password.content)["csrf"]
    code = totp.code(secret, totp.step_at(time.time()) + 1)  # the enrolling step is spent
    signed = send(client, "/api/auth/second-factor", headers["X-CSRFToken"], {"code": code})
    assert signed.status_code == 200 and json.loads(signed.content)["next"] == "signed_in"
    cookie = client.cookies[SESSION].value
    assert [e.session_key_hash for e in stepups(user)] != [stored_key(cookie)]
    assert len(stepups(user)) == 1  # the enrolment's only
    assert answer(change.begin(cookie)) == change.STEPUP


def test_a_fault_writing_the_evidence_rolls_the_enrolment_back(
    browser: tuple[Client, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The evidence is written in the transaction that saves the TOTP and activates the user."""
    client, token, email = enrolling(browser)
    secret = begun(client, token)

    def fail(_: AuthStepup) -> bytes:
        raise RuntimeError("the evidence could not be signed")

    monkeypatch.setattr(stepup, "evidence", fail)
    with pytest.raises(RuntimeError):
        send(client, CONFIRM, token, {"code": current(secret)})
    user = row(email)
    assert user.status == "invited" and stepups(user) == []
    with with_agency(user.agency_id):
        assert not UserFactor.objects.filter(user_id=user.id).exists()
    monkeypatch.undo()
    assert send(client, CONFIRM, token, {"code": current(secret)}).status_code == 200
    assert row(email).status == "active" and len(stepups(user)) == 1
