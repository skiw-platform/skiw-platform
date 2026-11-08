"""POST /api/auth/second-factor over HTTP, against the real tables as skiw_app (spec Flow 5.1 (2),
D7, AUTH-05, AUTH-06, AUTH-07; plan M3 §3 M3f). What `second_factor.attempt` does is tested in
test_second_factor_live.py; these tests cover the answers, the CSRF token, the session a right code
leaves, and (PR 129 R1 P2) that the session passes `authorized_action`. They run under
tests.csrf_urls, which adds the `action-probe` route."""

import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import Client

from accounts import views
from accounts.auth import factors, wrapper
from accounts.auth.login import FACTOR
from accounts.factor_model import UserFactor
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF, META

from .conftest import Clock
from .logins import PASSWORD, factor_count, random_ip, unseal
from .test_enrol_factor_route_live import current, send, stored_session, wrong_for
from .test_enrol_factor_route_live import enrolling as enrolling_browser
from .test_enrol_route_live import browser as browser_fixture
from .test_factor_lock_live import markers as lock_markers
from .test_second_factor_live import signing_in

browser = browser_fixture
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
LIMIT, WINDOW = (
    settings.SKIW_AUTH_FAILS_PER_ACCOUNT,
    timedelta(minutes=settings.SKIW_AUTH_WINDOW_MIN),
)
LOGIN, SECOND, PROBE = "/api/auth/login", "/api/auth/second-factor", "/action-probe"
EXPIRED, LIMITED = {"error": "login-expired"}, {"error": "limited"}
NOT_A_CODE = "WRONGWRONGWRONG0"  # 16 symbols: read as a recovery code, and never one


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def fresh_browser() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    match = META.search(client.get("/", secure=True).content.decode())
    assert match, "the shell carries no CSRF token"
    return client, match.group(1)


def password_step(started: tuple[Client, str], email: str) -> tuple[Client, str]:
    """The password step over HTTP: the client and the CSRF token its answer returned."""
    client, token = started
    response = send(
        client, LOGIN, token, {"email": email, "password": PASSWORD}, REMOTE_ADDR=random_ip()
    )
    assert response.status_code == 200 and json.loads(response.content)["next"] == "second_factor"
    return client, json.loads(response.content)["csrf"]


def probe(client: Client, token: str) -> int:
    return send(client, PROBE, token).status_code


def body(response: HttpResponse) -> Any:
    return json.loads(response.content)


def test_a_right_authenticator_code_signs_in_and_the_session_passes_the_action_check(
    browser: tuple[Client, str],
) -> None:
    """PR 129 R1 P2 for the sign-in route: the session `login()` leaves is not refused by
    `authorized_action`."""
    user, secret, _ = signing_in()
    client, token = password_step(browser, user.email)
    assert probe(client, token) == 401  # pending is not a sign-in
    response = send(client, SECOND, token, {"code": current(secret)})
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    answer = body(response)
    assert answer.keys() == {"next", "csrf"} and answer["next"] == "signed_in"
    assert answer["csrf"] != token
    session = stored_session(client)
    signed = wrapper._signed(session)
    assert signed is not None and signed.user_id == user.id and session[FACTOR] == "totp"
    assert not any(key in session for key in factors.PENDING_KEYS)
    assert probe(client, answer["csrf"]) == 200


def test_a_recovery_code_signs_in_once_and_other_sessions_stay_signed_in(
    browser: tuple[Client, str],
) -> None:
    """AUTH-07: a recovery code is used up, but using one writes no revocation marker, so the
    user's other session is not signed out."""
    user, secret, codes = signing_in()
    first, first_token = password_step(browser, user.email)
    first_token = body(send(first, SECOND, first_token, {"code": current(secret)}))["csrf"]
    second, second_token = password_step(fresh_browser(), user.email)
    response = send(second, SECOND, second_token, {"code": codes[0].lower().replace("-", " ")})
    assert response.status_code == 200 and stored_session(second)[FACTOR] == "recovery"
    assert probe(second, body(response)["csrf"]) == 200
    assert probe(first, first_token) == 200  # not signed out by the other sign-in
    third, third_token = password_step(fresh_browser(), user.email)
    spent = send(third, SECOND, third_token, {"code": codes[0]})
    assert spent.status_code == 401 and body(spent) == {"error": "code-wrong"}


@pytest.mark.parametrize("case", ["none", "enrolment", "expired", "inactive"])
def test_every_pending_state_failure_is_the_one_expired_answer_with_no_new_cookie(
    browser: tuple[Client, str], clock: Clock, case: str
) -> None:
    """AUTH-05: nothing tells a holder of a session why it has no usable login."""
    user, secret, _ = signing_in()
    if case == "none":
        client, token = browser
    elif case == "enrolment":
        client, token, _ = enrolling_browser(browser)
    else:
        client, token = password_step(browser, user.email)
    if case == "expired":
        clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN, seconds=1))
    if case == "inactive":
        with with_agency(user.agency_id):
            type(user).objects.filter(id=user.id).update(status="disabled")
    response = send(client, SECOND, token, {"code": current(secret)})
    assert response.status_code == 401 and body(response) == EXPIRED
    if case != "expired":  # an expired pending state is cleared out of the caller's own session
        assert settings.SESSION_COOKIE_NAME not in response.cookies
    assert factor_count(user.id) == 0


def test_wrong_codes_are_refused_counted_and_end_in_limited(browser: tuple[Client, str]) -> None:
    user, secret, _ = signing_in()
    client, token = password_step(browser, user.email)
    for _ in range(LIMIT):
        response = send(client, SECOND, token, {"code": wrong_for(secret)})
        assert response.status_code == 401 and body(response) == {"error": "code-wrong"}
    response = send(client, SECOND, token, {"code": current(secret)})
    assert response.status_code == 429 and body(response) == LIMITED
    assert factor_count(user.id) == LIMIT and probe(client, token) == 401


def test_a_locked_user_gets_the_limited_answer_even_with_the_right_code(
    browser: tuple[Client, str], clock: Clock
) -> None:
    """PR 133 review: the lock end to end. Ten wrong codes (authenticator and recovery codes
    alternately) across two budget windows lock the user; in a fresh window, with a fresh budget,
    the right code gets the same 429 `limited` answer as an exhausted budget."""
    user, secret, _ = signing_in()
    client, token = browser
    for n in range(settings.SKIW_AUTH_LOCK_AFTER):
        if n % LIMIT == 0:
            if n:
                clock.advance(WINDOW)
            client, token = password_step((client, token), user.email)
        code = wrong_for(secret) if n % 2 == 0 else NOT_A_CODE
        response = send(client, SECOND, token, {"code": code})
        assert response.status_code == 401 and body(response) == {"error": "code-wrong"}
    assert lock_markers(user.id) == 1
    clock.advance(WINDOW)
    client, token = password_step((client, token), user.email)
    response = send(client, SECOND, token, {"code": current(secret)})
    assert response.status_code == 429 and body(response) == LIMITED
    assert factor_count(user.id) == 0 and probe(client, token) == 401  # the lock, not the budget


@pytest.mark.parametrize("sent", [None, {}, {"code": 123456}, {"code": None}, {"code": ["1"]}])
def test_a_body_without_a_text_code_is_invalid_and_counts_nothing(
    browser: tuple[Client, str], sent: Any
) -> None:
    user, _, _ = signing_in()
    client, token = password_step(browser, user.email)
    response = send(client, SECOND, token, sent)
    assert response.status_code == 400 and body(response) == {"error": "invalid"}
    assert factor_count(user.id) == 0
    other = client.post(
        SECOND,
        "code=123456",
        content_type="text/plain",
        secure=True,
        headers={"Origin": "https://testserver", "X-CSRFToken": token},
    )
    assert other.status_code == 400


def test_a_form_post_signs_in_like_json(browser: tuple[Client, str]) -> None:
    user, secret, _ = signing_in()
    client, token = password_step(browser, user.email)
    response = client.post(
        SECOND,
        f"code={current(secret)}",
        content_type="application/x-www-form-urlencoded",
        secure=True,
        headers={"Origin": "https://testserver", "X-CSRFToken": token},
    )
    assert (
        response.status_code == 200 and probe(client, json.loads(response.content)["csrf"]) == 200
    )


def test_a_failure_in_login_after_the_attempt_spends_the_code(
    browser: tuple[Client, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR 132 R1 P3, accepted and pinned: the code is spent and nothing restores it (restoring a
    code would reopen replay). The 500 saves no session, so the stored pending login is untouched
    and the user can try another code."""
    user, _, codes = signing_in()
    client, token = password_step(browser, user.email)

    def fail(*_: object, **__: object) -> None:
        raise RuntimeError("the session write failed")

    with monkeypatch.context() as patch:
        patch.setattr(views, "login", fail)
        with pytest.raises(RuntimeError):
            send(client, SECOND, token, {"code": codes[0]})
    with with_agency(user.agency_id):
        assert UserFactor.objects.filter(user_id=user.id, kind="recovery").count() == 9
    spent = send(client, SECOND, token, {"code": codes[0]})
    assert spent.status_code == 401 and body(spent) == {"error": "code-wrong"}
    assert send(client, SECOND, token, {"code": codes[1]}).status_code == 200
