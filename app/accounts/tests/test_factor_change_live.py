"""GET /api/auth/factors and adding a TOTP (POST /api/auth/factors/totp, then /confirm) against
the real tables as skiw_app (accounts.auth.factor_change; spec D7, AUTH-06, AUTH-07, AUTH-09;
plan M3 §3 M3h; DECISIONS M3h-5). The AUTH-07 tests run on the real clock (see
test_logout_password_live). Users, factors and markers are committed and kept."""

import base64
import json
import threading
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from django.db import connection
from django.test import RequestFactory

from accounts.auth import blob, factor_change, factors, recovery, second_factor, totp
from accounts.auth.login import FACTOR
from accounts.auth.revoke import mark
from accounts.auth.second_factor import Passed, attempt
from accounts.factor_model import UserFactor
from accounts.session import SessionStore, stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .conftest import COOKIE, assert_deleted, row_deadline
from .logins import factor_count
from .test_action_wrapper_live import markers, signed_in
from .test_factor_lock_live import run as lock_run
from .test_logout_password_live import answer, client, probe, wait_for_a_lock_waiter
from .test_stepup_route_live import step_up

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of sign_in.STEP
unsealed = sign_in.unsealed  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
STEP, LIMIT = sign_in.STEP, sign_in.LIMIT


def begin(cookie: str) -> "Response":
    return client(cookie).post("/api/auth/factors/totp", b"{}", content_type="application/json")


def confirm(cookie: str, code: Any) -> "Response":
    body = json.dumps({"code": code})
    return client(cookie).post(
        "/api/auth/factors/totp/confirm", body, content_type="application/json"
    )


def stepped_up() -> tuple[AppUser, bytes, str]:
    """A signed-in user with a TOTP factor, stepped up for `factor.change` in that session."""
    user, secret, _ = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    assert step_up(client(cookie), sign_in.code_at(secret, STEP)).status_code == 200
    return user, secret, cookie


def begun(cookie: str) -> bytes:
    status, body = answer(begin(cookie))
    assert status == 200 and body.keys() == {"secret", "uri"}
    return base64.b32decode(body["secret"])


def totps(user: AppUser) -> list[UserFactor]:
    with with_agency(user.agency_id):
        return list(UserFactor.objects.filter(user_id=user.id, kind="totp").order_by("sign_count"))


def test_without_a_step_up_neither_begin_nor_confirm_adds_anything() -> None:
    user, _, _ = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    assert answer(begin(cookie)) == (403, {"error": "stepup-required"})
    assert factor_change.ADD_TOTP not in SessionStore(cookie).load()
    request = RequestFactory().post("/")  # a secret begun earlier, its step-up since expired
    request.session = store = SessionStore(cookie)
    new = base64.b32decode(factors.seal_new(request, factor_change.ADD_TOTP, user).secret)
    store.save()
    assert answer(confirm(cookie, sign_in.code_at(new, STEP))) == (
        403,
        {"error": "stepup-required"},
    )
    assert len(totps(user)) == 1 and factor_count(user.id) == 0 and markers(user) == []
    assert probe(cookie) == 200


def test_a_right_code_adds_the_factor_ends_other_sessions_and_reissues_this_one(
    at_step: Any,
) -> None:
    user, _, cookie = stepped_up()
    other, deadline = signed_in(user, factor="totp"), row_deadline(cookie)
    new = begun(cookie)
    response = confirm(cookie, sign_in.code_at(new, STEP))
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "added", {"next", "factor_id", "csrf"})
    fresh = response.cookies[COOKIE].value
    assert fresh != cookie and row_deadline(fresh) == deadline  # re-issued, not a new lifetime
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    after = SessionStore(fresh).load()
    assert after[FACTOR] == "totp" and factor_change.ADD_TOTP not in after
    _, added = totps(user)
    assert (str(added.id), added.sign_count) == (body["factor_id"], STEP)
    assert attempt(sign_in.pending_login(user), sign_in.code_at(new, STEP)) == "wrong_code"
    at_step.step += 1
    passed = attempt(sign_in.pending_login(user), sign_in.code_at(new, STEP + 1))
    assert passed == Passed(user.id, user.agency_id, "totp")
    assert answer(confirm(fresh, sign_in.code_at(new, STEP + 1))) == (409, {"error": "no-pending"})


def test_wrong_codes_are_counted_without_feeding_the_lock_then_limited() -> None:
    user, _, cookie = stepped_up()
    new = begun(cookie)
    for n in range(LIMIT):
        assert answer(confirm(cookie, sign_in.wrong_for(new))) == (401, {"error": "code-wrong"})
        assert (factor_count(user.id), lock_run(user.id)) == (n + 1, 0)
    assert answer(confirm(cookie, sign_in.code_at(new, STEP))) == (429, {"error": "limited"})
    assert len(totps(user)) == 1 and markers(user) == [] and probe(cookie) == 200


def test_a_fault_after_a_wrong_code_keeps_the_count_and_leaves_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR 139 R2 P3: `counted(feeds_lock=False)`'s fault branch."""
    user, _, cookie = stepped_up()
    new = begun(cookie)
    monkeypatch.setattr(second_factor, "with_agency", sign_in.failing_commit)
    with pytest.raises(RuntimeError):
        confirm(cookie, sign_in.wrong_for(new))
    assert (factor_count(user.id), lock_run(user.id)) == (1, 0)


@pytest.mark.parametrize("code", ["12345", "١٢٣٤٥٦", 123456, None])
def test_a_code_that_cannot_be_one_is_400_and_counts_nothing(code: Any) -> None:
    user, _, cookie = stepped_up()
    begun(cookie)
    assert answer(confirm(cookie, code)) == (400, {"error": "invalid"})
    assert factor_count(user.id) == 0 and len(totps(user)) == 1


def test_nothing_begun_is_409_and_counts_nothing() -> None:
    user, _, cookie = stepped_up()
    assert answer(confirm(cookie, "123456")) == (409, {"error": "no-pending"})
    assert factor_count(user.id) == 0


def test_a_begun_secret_that_does_not_open_is_409_and_counts_nothing() -> None:
    """PR 142 R1 P3 #1: a sealed secret bound to another factor id is not a guess."""
    user, _, cookie = stepped_up()
    secret = totp.new_secret()
    sealed = blob.seal_factor_secret(secret, uuid.uuid4(), user.id, user.agency_id)
    store = SessionStore(cookie)
    store[factor_change.ADD_TOTP] = {
        "id": str(uuid.uuid4()),
        "ct": base64.b64encode(sealed).decode(),
    }
    store.save()
    assert answer(confirm(cookie, sign_in.code_at(secret, STEP))) == (409, {"error": "no-pending"})
    assert factor_count(user.id) == 0 and len(totps(user)) == 1 and markers(user) == []
    assert probe(cookie) == 200


def test_the_list_shows_only_the_users_own_totps_and_recovery_count() -> None:
    user, _, codes = sign_in.signing_in()
    neighbour, _, _ = sign_in.signing_in()  # the same (deployment) agency: RLS does not split them
    assert neighbour.agency_id == user.agency_id
    [own] = totps(user)
    cookie = signed_in(user, factor="totp")
    listed = {"totp": [{"id": str(own.id)}], "passkey": [], "recovery_left": len(codes)}
    assert answer(client(cookie).get("/api/auth/factors")) == (200, listed)
    with with_agency(user.agency_id):
        assert recovery.consume(user.id, codes[0])
    assert answer(client(cookie).get("/api/auth/factors"))[1]["recovery_left"] == len(codes) - 1


def test_a_confirm_waiting_on_hold_sees_a_marker_committed_meanwhile_and_adds_nothing() -> None:
    """The resurrection race (DECISIONS M3h-4) for adding a TOTP: only `hold` stops this session
    adding a factor and re-issuing itself past another change's user-wide marker."""
    user, _, cookie = stepped_up()
    new = begun(cookie)
    results: list[Any] = []

    def session_b() -> None:
        try:
            results.append(confirm(cookie, sign_in.code_at(new, STEP)))
        finally:
            connection.close()

    b = threading.Thread(target=session_b)
    with with_agency(user.agency_id):  # another session's credential change
        AppUser.objects.select_for_update().filter(id=user.id).first()
        b.start()
        wait_for_a_lock_waiter()
        mark(user.agency_id, user.id, None)
    b.join(timeout=30)
    [response] = results
    assert answer(response) == (401, {"error": "signed-out"})
    assert_deleted(response)
    assert len(totps(user)) == 1 and factor_count(user.id) == 0 and probe(cookie) == 401
