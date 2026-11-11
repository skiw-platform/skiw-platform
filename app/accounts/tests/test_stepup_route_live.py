"""POST /api/auth/stepup and the test-only `stepup-probe` consumer of `recent()`, against the real
tables as skiw_app (accounts.auth.stepup.verify, second_factor.counted; spec D7, AUTH-06, AUTH-09;
plan M3 §3 M3h; DECISIONS M3h-3). Step-up shares the sign-in's budget, lock run and `sign_count`.
Users and the step-up rows they write are committed and kept (TEN-03: skiw_app deletes neither)."""

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.utils import timezone

from accounts.auth import second_factor, stepup, throttle, wrapper
from accounts.auth.second_factor import Passed, attempt
from accounts.auth.wrapper import authorized_action
from accounts.session import SessionStore, stored_key
from accounts.stepup_model import AuthStepup
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .conftest import COOKIE, Clock
from .logins import factor_count
from .test_action_wrapper_live import signed_in
from .test_factor_lock_live import events as lock_events
from .test_factor_lock_live import markers as lock_markers
from .test_factor_lock_live import run as lock_run

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of step STEP
unsealed = sign_in.unsealed  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
CHANGE, STEP = stepup.FACTOR_CHANGE, sign_in.STEP
LIMIT, WINDOW = sign_in.LIMIT, sign_in.WINDOW


def session(user: AppUser) -> Client:
    client = Client()
    client.cookies[COOKIE] = signed_in(user, factor="totp")
    return client


def step_up(client: Client, code: Any, purpose: Any = CHANGE) -> "Response":
    body = json.dumps({"purpose": purpose, "code": code})
    return client.post("/api/auth/stepup", body, content_type="application/json")


def probe(client: Client) -> int:
    return client.post("/stepup-probe", b"{}", content_type="application/json").status_code


def answer(response: "HttpResponse | Response") -> tuple[int, Any]:
    assert response["Cache-Control"] == "no-store"
    return response.status_code, json.loads(response.content)


def evidence(user: AppUser) -> list[AuthStepup]:
    with with_agency(user.agency_id):
        return list(AuthStepup.objects.filter(user_id=user.id))


def test_a_right_code_steps_up_this_session_only_and_a_wrong_one_records_nothing() -> None:
    user, secret, _ = sign_in.signing_in()
    client, other = session(user), session(user)
    assert probe(client) == 403
    assert answer(step_up(client, sign_in.wrong_for(secret))) == (401, {"error": "code-wrong"})
    assert evidence(user) == [] and factor_count(user.id) == 1
    status, body = answer(step_up(client, sign_in.code_at(secret, STEP)))
    (row,) = evidence(user)
    max_age = timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN)
    assert (status, body) == (
        200,
        {"next": "verified", "until": (row.verified_at + max_age).isoformat()},
    )
    assert row.session_key_hash == stored_key(client.cookies[COOKIE].value)
    assert factor_count(user.id) == 1  # the right code gave its attempt back, the wrong one stays
    assert probe(client) == 200
    assert probe(other) == 403  # another session of the same user


def test_a_code_used_at_sign_in_is_refused_at_step_up_and_the_reverse(at_step: Any) -> None:
    user, secret, _ = sign_in.signing_in()
    client = session(user)
    assert isinstance(attempt(sign_in.pending_login(user), sign_in.code_at(secret, STEP)), Passed)
    assert answer(step_up(client, sign_in.code_at(secret, STEP)))[0] == 401
    at_step.step += 1
    assert answer(step_up(client, sign_in.code_at(secret, STEP + 1)))[0] == 200
    code = sign_in.code_at(secret, STEP + 1)
    assert attempt(sign_in.pending_login(user), code) == "wrong_code"


def test_two_parallel_step_ups_with_one_code_pass_once() -> None:
    user, secret, _ = sign_in.signing_in()
    calls: list[Callable[[], object]] = [
        partial(step_up, session(user), sign_in.code_at(secret, STEP)) for _ in range(2)
    ]
    results = sign_in.in_parallel(calls)
    assert sorted(r.status_code for r in results if isinstance(r, HttpResponse)) == [200, 401]
    assert len(evidence(user)) == 1


def test_step_up_and_sign_in_share_one_budget() -> None:
    user, secret, _ = sign_in.signing_in()
    client = session(user)
    for _ in range(LIMIT - 2):
        assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == "wrong_code"
    for _ in range(2):
        assert answer(step_up(client, sign_in.wrong_for(secret)))[0] == 401
    assert answer(step_up(client, sign_in.code_at(secret, STEP))) == (429, {"error": "limited"})
    assert attempt(sign_in.pending_login(user), sign_in.code_at(secret, STEP)) == "limited"
    assert sign_in.stored_step(user) == 0 and evidence(user) == []


def test_wrong_step_up_codes_feed_the_lock_shared_with_sign_in(clock: Clock) -> None:
    after = settings.SKIW_AUTH_LOCK_AFTER
    user, secret, _ = sign_in.signing_in()
    client = session(user)
    for n in range(after):  # sign-in and step-up alternately, across windows
        if factor_count(user.id) >= LIMIT:
            clock.advance(WINDOW)
        if n % 2:
            assert answer(step_up(client, sign_in.wrong_for(secret)))[0] == 401
        else:
            assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == "wrong_code"
    ip = throttle.client_ip(RequestFactory().get("/"))
    assert lock_markers(user.id) == 1 and lock_events(user.email, ip) == [{"consecutive": after}]
    clock.advance(WINDOW)  # a fresh budget, but the lock holds for both
    assert attempt(sign_in.pending_login(user), sign_in.code_at(secret, STEP)) == "limited"
    assert answer(step_up(client, sign_in.code_at(secret, STEP)))[0] == 429


def test_a_right_step_up_ends_the_run_of_wrong_codes() -> None:
    user, secret, _ = sign_in.signing_in()
    for _ in range(3):
        assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == "wrong_code"
    assert lock_run(user.id) == 3
    assert answer(step_up(session(user), sign_in.code_at(secret, STEP)))[0] == 200
    assert lock_run(user.id) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"code": "recovery"},  # a recovery code: never step-up
        {"code": "12345"},
        {"code": "1234567"},
        {"code": "١٢٣٤٥٦"},  # six digits, not ASCII
        {"purpose": "export"},  # the right code, a purpose PURPOSES does not list
        {"purpose": ["factor.change"]},
        {"code": 123456},
        {"code": None},
        {"extra": "x"},
    ],
)
def test_a_body_that_cannot_be_a_step_up_is_400_and_counts_nothing(
    body: Mapping[str, Any],
) -> None:
    user, secret, codes = sign_in.signing_in()
    sent = {"purpose": CHANGE, "code": sign_in.code_at(secret, STEP), **body}
    if sent["code"] == "recovery":
        sent["code"] = codes[0]
    response = session(user).post(
        "/api/auth/stepup", json.dumps(sent), content_type="application/json"
    )
    assert answer(response) == (400, {"error": "invalid"})
    assert factor_count(user.id) == 0 and sign_in.stored_step(user) == 0 and evidence(user) == []


def test_a_fault_writing_the_evidence_rolls_the_code_back_and_gives_the_attempt_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, secret, _ = sign_in.signing_in()
    client = session(user)

    def fail(*_: object) -> stepup.StepUp:
        raise RuntimeError("the insert failed")

    with monkeypatch.context() as patch:
        patch.setattr(stepup, "record", fail)
        with pytest.raises(RuntimeError):
            step_up(client, sign_in.code_at(secret, STEP))
    assert factor_count(user.id) == 0 and sign_in.stored_step(user) == 0
    assert lock_run(user.id) == 0 and evidence(user) == []
    assert answer(step_up(client, sign_in.code_at(secret, STEP)))[0] == 200  # the code still works


def test_a_fault_after_a_wrong_code_keeps_the_count_and_feeds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, secret, _ = sign_in.signing_in()
    monkeypatch.setattr(second_factor, "with_agency", sign_in.failing_commit)
    with pytest.raises(RuntimeError):
        step_up(session(user), sign_in.wrong_for(secret))
    assert factor_count(user.id) == 1 and lock_run(user.id) == 1


def signed_request(user: AppUser) -> HttpRequest:
    request = RequestFactory().post("/", b"{}", content_type="application/json")
    request.session = SessionStore(signed_in(user, factor="totp"))
    return request


def test_a_user_no_longer_active_is_unavailable_and_nothing_is_counted() -> None:
    user, secret, _ = sign_in.signing_in()
    request = signed_request(user)
    assert isinstance(request.session, SessionStore)
    signed = wrapper._signed(request.session)
    assert signed is not None
    with with_agency(user.agency_id):
        AppUser.objects.filter(id=user.id).update(status="disabled")
    assert stepup.verify(request, signed, CHANGE, sign_in.code_at(secret, STEP)) == "unavailable"
    assert factor_count(user.id) == 0 and evidence(user) == []


@pytest.mark.parametrize("own", [False, True])
def test_an_own_transaction_handler_runs_after_the_checks_outside_any_transaction(
    own: bool,
) -> None:
    seen: list[tuple[bool, uuid.UUID]] = []

    @authorized_action(schema=dict, permission="test.own", own_transaction=own)
    def handler(request: HttpRequest, signed: wrapper.Signed, data: object) -> HttpResponse:
        seen.append((connection.in_atomic_block, signed.user_id))
        return HttpResponse()

    user, _, _ = sign_in.signing_in()
    assert vars(handler)["skiw_action"] == "test.own"
    assert handler(signed_request(user)).status_code == 200
    assert seen == [(not own, user.id)]
    with with_agency(user.agency_id):
        AppUser.objects.filter(id=user.id).update(status="disabled")
    refused = handler(signed_request(user))
    assert answer(refused) == (401, {"error": "signed-out"}) and len(seen) == 1


def test_without_a_session_step_up_is_the_wrappers_no_store_401() -> None:
    assert answer(step_up(Client(), "123456")) == (401, {"error": "signed-out"})


def test_verify_refuses_an_unknown_purpose_before_judging_the_code() -> None:
    user, secret, _ = sign_in.signing_in()
    now = timezone.now()
    who = wrapper.Signed(user.id, user.agency_id, "totp", now, now)
    request = sign_in.pending_login(user)
    for code in ("not a code", sign_in.code_at(secret, STEP)):
        with pytest.raises(ValueError, match="unknown step-up purpose"):
            stepup.verify(request, who, "export", code)
    assert factor_count(user.id) == 0 and sign_in.stored_step(user) == 0


def test_a_check_that_does_not_feed_the_lock_still_counts_and_neither_feeds_nor_ends_the_run() -> (
    None
):
    user, secret, _ = sign_in.signing_in()
    for _ in range(2):
        assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == "wrong_code"
    request = sign_in.pending_login(user)
    agency, wrong = user.agency_id, sign_in.wrong_for(secret)
    right = sign_in.code_at(secret, STEP)

    def codes(candidate: str) -> Callable[[AppUser], bool]:
        return lambda u: second_factor.match_totp(u, candidate) is not None

    assert second_factor.counted(request, user.id, agency, codes(wrong), feeds_lock=False) == (
        "wrong_code"
    )
    assert (factor_count(user.id), lock_run(user.id)) == (3, 2)  # counted, run unchanged
    assert second_factor.counted(request, user.id, agency, codes(right), feeds_lock=False) == "ok"
    assert (factor_count(user.id), lock_run(user.id)) == (3, 2)  # given back, run not ended
