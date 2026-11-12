"""GET /api/auth/session against the real tables as skiw_app (DECISIONS M3i-0): the state the
page starts from, by the wrapper's own checks and the pending helpers, read-only (no write, no
idle clock move) and one body for every signed-out case (AUTH-05)."""

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from accounts.auth.login import SEEN_AT
from accounts.auth.revoke import mark, revoke_user
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .conftest import COOKIE, Clock, assert_deleted, committed_user
from .test_action_wrapper_live import idle, markers, set_factor, signed_in
from .test_session_hmac_live import data_of

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
WRITES = ("INSERT", "UPDATE", "DELETE")


def state(cookie: str | None, clears: bool = False) -> tuple[str, Any]:
    """The answer's state, after checking what every answer shares; the response for more. No
    write, except that `clears` (a pending state that cannot be used) empties the session row, as
    factors.pending does for the second-factor and enrolment routes."""
    browser = Client()
    if cookie is not None:
        browser.cookies[COOKIE] = cookie
    with CaptureQueriesContext(connection) as queries:
        response = browser.get("/api/auth/session")
    writes = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(WRITES)]
    if clears:
        assert len(writes) == 1 and writes[0].startswith('UPDATE "django_session"')
        assert cookie is not None and SessionStore(cookie).load() == {}
    else:
        assert writes == []
    body = json.loads(response.content)
    assert (response.status_code, response["Cache-Control"]) == (200, "no-store")
    assert set(body) == {"state", "csrf"} and body["csrf"]
    return body["state"], response


def pending(enrol: bool) -> tuple[AppUser, str]:
    user = committed_user(status="invited" if enrol else "active")
    request = sign_in.pending_login(user, enrol=enrol)
    request.session.save()
    return user, str(request.session.session_key)


def set_status(user: AppUser, status: str) -> None:
    with with_agency(user.agency_id):
        AppUser.objects.filter(id=user.id).update(status=status)


def test_anonymous_is_signed_out_with_no_query_and_no_session_cookie() -> None:
    with CaptureQueriesContext(connection) as queries:
        answer, response = state(None)
    assert answer == "signed_out" and len(queries) == 0
    assert COOKIE not in response.cookies


@pytest.mark.parametrize("enrol", [False, True], ids=["login", "enrolment"])
def test_a_live_pending_state_names_its_screen(enrol: bool) -> None:
    _, cookie = pending(enrol)
    assert state(cookie)[0] == ("enrol_factor" if enrol else "second_factor")


def test_a_completed_login_is_signed_in_and_names_nobody() -> None:
    user = committed_user()
    answer, response = state(signed_in(user, factor="totp"))
    assert answer == "signed_in" and str(user.id) not in response.content.decode()
    assert user.email not in response.content.decode()


def test_polling_never_moves_the_idle_clock_or_keeps_a_session_alive(clock: Clock) -> None:
    cookie = signed_in(committed_user(), factor="totp")
    before, seen = data_of(cookie), SessionStore(cookie)[SEEN_AT]
    for _ in range(3):
        clock.advance(idle() / 3 - timedelta(microseconds=1))
        assert state(cookie)[0] == "signed_in"
    assert data_of(cookie) == before and SessionStore(cookie)[SEEN_AT] == seen
    clock.advance(timedelta(microseconds=3))
    assert state(cookie)[0] == "signed_out"


def idle_out(clock: Clock) -> str:
    cookie = signed_in(committed_user(), factor="totp")
    clock.advance(idle())
    return cookie


def past_deadline(clock: Clock) -> str:
    """At the deadline with an idle clock half a limit old, so only the deadline refuses."""
    cookie = signed_in(committed_user(), factor="totp")
    clock.advance(timedelta(hours=settings.SKIW_SESSION_ABSOLUTE_H) - idle() / 2)
    store = SessionStore(cookie)
    store[SEEN_AT] = clock.now.isoformat(timespec="microseconds")
    store.save()
    clock.advance(idle() / 2)
    return cookie


def revoked_key(clock: Clock) -> str:
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    with with_agency(user.agency_id):
        mark(user.agency_id, user.id, cookie)
    return cookie


def revoked_user(clock: Clock) -> str:
    """The real clock's marker after a login on the frozen one (taken just before)."""
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    revoke_user(user.agency_id, user.id)
    return cookie


def not_active(clock: Clock) -> str:
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    set_status(user, "disabled")
    return cookie


def no_factor(clock: Clock) -> str:
    cookie = signed_in(committed_user(), factor="totp")
    set_factor(cookie, None)
    return cookie


def pending_expired(clock: Clock) -> str:
    cookie = pending(enrol=False)[1]
    clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN))
    return cookie


def pending_changed(clock: Clock) -> str:
    """A credential change after the password step (M3h-5) ends the pending login."""
    user, cookie = pending(enrol=False)
    revoke_user(user.agency_id, user.id)
    return cookie


SIGNED_OUT: dict[str, Callable[[Clock], str | None]] = {
    "garbage": lambda clock: "x" * 32,
    "malformed": lambda clock: "not a session key",
    "idle": idle_out,
    "absolute-deadline": past_deadline,
    "revoked-key": revoked_key,
    "revoked-user": revoked_user,
    "not-active": not_active,
    "no-second-factor": no_factor,
    "pending-expired": pending_expired,
    "pending-ended-by-a-change": pending_changed,
}


@pytest.mark.parametrize("case", SIGNED_OUT)
def test_every_failing_session_gets_the_one_signed_out_answer(case: str, clock: Clock) -> None:
    """Same status, same keys and no write whatever the reason, apart from clearing a pending
    state that cannot be used."""
    cookie = SIGNED_OUT[case](clock)
    answer, response = state(cookie, clears=case.startswith("pending"))
    assert answer == "signed_out"
    if case in ("garbage", "malformed", "absolute-deadline"):  # no row: the cookie goes
        assert_deleted(response)


def test_a_refused_session_is_left_for_the_wrapper_to_end(clock: Clock) -> None:
    """No marker and no flush here; the next wrapped call writes them as before."""
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    clock.advance(idle())
    assert state(cookie)[0] == "signed_out" and markers(user) == []
    browser = Client()
    browser.cookies[COOKIE] = cookie
    assert browser.post("/action-probe", b"{}", content_type="application/json").status_code == 401
    assert len(markers(user)) == 1


def test_a_user_made_active_again_is_signed_in_again() -> None:
    """The route reads the status on every call; it caches nothing."""
    user = committed_user()
    cookie = signed_in(user, factor="totp")
    set_status(user, "disabled")
    assert state(cookie)[0] == "signed_out"
    set_status(user, "active")
    assert state(cookie)[0] == "signed_in"
