"""Removing a TOTP (POST /api/auth/factors/totp/remove) and regenerating recovery codes
(POST /api/auth/factors/recovery) against the real tables as skiw_app (accounts.auth.factor_change;
spec D7, AUTH-07, AUTH-09; plan M3 §3 M3h; DECISIONS M3h-6). A removed factor is retired, never
deleted, and no lookup uses it. The AUTH-07 tests run on the real clock (see
test_logout_password_live). Users, factors, step-ups and markers are committed and kept."""

import base64
import contextlib
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from django.db import connection

from accounts.auth import blob, factor_change, recovery, stepup, totp
from accounts.auth.second_factor import Passed, attempt
from accounts.factor_model import UserFactor
from accounts.session import stored_key
from accounts.stepup_model import AuthStepup
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF, ORIGIN

from . import test_second_factor_live as sign_in
from .conftest import COOKIE, row_deadline
from .logins import factor_count
from .test_action_wrapper_live import markers, signed_in
from .test_factor_change_live import begun, stepped_up
from .test_factor_change_live import confirm as confirm_add
from .test_logout_password_live import answer, assert_rotated, client, csrf_browser, probe
from .test_stepup_route_live import signed_request, step_up

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of sign_in.STEP
unsealed = sign_in.unsealed  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
STEP, CHANGE = sign_in.STEP, stepup.FACTOR_CHANGE
MANAGE = Path(__file__).resolve().parents[2] / "manage.py"


def remove(cookie: str, factor: object) -> "Response":
    body = json.dumps({"id": str(factor)})
    return client(cookie).post(
        "/api/auth/factors/totp/remove", body, content_type="application/json"
    )


def regenerate(cookie: str) -> "Response":
    return client(cookie).post("/api/auth/factors/recovery", b"{}", content_type="application/json")


def add_totp(user: AppUser) -> tuple[uuid.UUID, bytes]:
    """A second TOTP factor for `user`, as an add leaves one (last step 0)."""
    secret, factor = totp.new_secret(), uuid.uuid4()
    sealed = blob.seal_factor_secret(secret, factor, user.id, user.agency_id)
    with with_agency(user.agency_id):
        UserFactor.objects.create(
            id=factor, agency_id=user.agency_id, user_id=user.id, kind="totp", secret_ct=sealed
        )
    return factor, secret


def row(factor: uuid.UUID, user: AppUser) -> UserFactor:
    with with_agency(user.agency_id):
        return UserFactor.objects.get(id=factor)


def in_use(user: AppUser) -> set[uuid.UUID]:
    with with_agency(user.agency_id):
        own = UserFactor.objects.filter(user_id=user.id, kind="totp", retired_at__isnull=True)
        return set(own.values_list("id", flat=True))


def first_totp(user: AppUser) -> uuid.UUID:
    [factor] = in_use(user)
    return factor


def listed(cookie: str) -> Any:
    return answer(client(cookie).get("/api/auth/factors"))[1]


def test_the_last_totp_is_refused_and_stays_in_use() -> None:
    user, secret, cookie = stepped_up()
    factor = first_totp(user)
    assert answer(remove(cookie, factor)) == (409, {"error": "last-factor"})
    kept = row(factor, user)
    assert kept.retired_at is None and kept.secret_ct is not None
    assert markers(user) == [] and probe(cookie) == 200
    passed = attempt(sign_in.pending_login(user), sign_in.code_at(secret, STEP + 1))
    assert passed == Passed(user.id, user.agency_id, "totp")


def test_removing_the_stepped_up_totp_retires_it_ends_other_sessions_and_reissues_this_one() -> (
    None
):
    user, _, cookie = stepped_up()
    old = first_totp(user)
    new, new_secret = add_totp(user)
    other, deadline = signed_in(user, factor="totp"), row_deadline(cookie)
    [proof] = _evidence(user)
    assert proof.factor_id == old
    response = remove(cookie, old)
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "removed", {"next", "csrf"})
    fresh = response.cookies[COOKIE].value
    assert fresh != cookie and row_deadline(fresh) == deadline  # re-issued, not a new lifetime
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    retired = row(old, user)
    assert retired.retired_at is not None and retired.secret_ct is None
    [kept] = _evidence(user)  # the evidence row stays, names the retired factor, and verifies
    assert kept.factor_id == old and stepup._genuine(kept)
    assert probe(fresh, "/stepup-probe") == 403  # the new key has no step-up
    assert listed(fresh)["totp"] == [{"id": str(new)}]
    passed = attempt(sign_in.pending_login(user), sign_in.code_at(new_secret, STEP))
    assert passed == Passed(user.id, user.agency_id, "totp")


def _evidence(user: AppUser) -> list[AuthStepup]:
    with with_agency(user.agency_id):
        return list(AuthStepup.objects.filter(user_id=user.id))


def test_a_retired_totp_signs_in_steps_up_and_is_removed_never(at_step: Any) -> None:
    user, old_secret, cookie = stepped_up()
    old = first_totp(user)
    new, new_secret = add_totp(user)
    fresh = remove(cookie, old).cookies[COOKIE].value
    at_step.step += 1
    code = sign_in.code_at(old_secret, STEP + 1)
    assert attempt(sign_in.pending_login(user), code) == "wrong_code"
    assert answer(step_up(client(fresh), code)) == (401, {"error": "code-wrong"})
    request = signed_request(user)
    with with_agency(user.agency_id), pytest.raises(ValueError, match="not retired"):
        stepup.record(request, old, CHANGE)
    assert step_up(client(fresh), sign_in.code_at(new_secret, STEP + 1)).status_code == 200
    assert answer(remove(fresh, old)) == (404, {"error": "not-found"})
    assert answer(remove(fresh, new)) == (409, {"error": "last-factor"})  # retired rows don't count
    assert in_use(user) == {new} and row(new, user).secret_ct is not None


def test_a_totp_retired_after_it_was_read_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """match_totp's conditional update: a remove that commits between the read and the use."""
    user, secret, _ = sign_in.signing_in()
    factor, real = first_totp(user), blob.open_factor_secret

    def retired_meanwhile(*args: Any) -> bytes | None:
        opened = real(*args)
        UserFactor.objects.filter(id=factor).update(retired_at="2026-11-11T00:00Z", secret_ct=None)
        return opened

    monkeypatch.setattr(blob, "open_factor_secret", retired_meanwhile)
    assert attempt(sign_in.pending_login(user), sign_in.code_at(secret, STEP)) == "wrong_code"
    assert row(factor, user).sign_count == 0


@pytest.mark.parametrize("whose", ["neighbour", "recovery", "unknown"])
def test_an_id_that_is_not_one_of_the_users_totps_is_404_and_changes_nothing(whose: str) -> None:
    user, _, cookie = stepped_up()
    add_totp(user)
    neighbour, _, _ = sign_in.signing_in()
    with with_agency(user.agency_id):
        recovery_row = UserFactor.objects.filter(user_id=user.id, kind="recovery").first()
    assert recovery_row is not None
    target = {
        "neighbour": first_totp(neighbour),
        "recovery": recovery_row.id,
        "unknown": uuid.uuid4(),
    }[whose]
    assert answer(remove(cookie, target)) == (404, {"error": "not-found"})
    assert len(in_use(user)) == 2 and len(in_use(neighbour)) == 1
    assert listed(cookie)["recovery_left"] == recovery.COUNT
    assert markers(user) == [] and probe(cookie) == 200


@pytest.mark.parametrize("route", ["remove", "regenerate"])
def test_without_a_step_up_neither_changes_anything(route: str) -> None:
    user, _, codes = sign_in.signing_in()
    second, _ = add_totp(user)
    cookie = signed_in(user, factor="totp")
    response = remove(cookie, second) if route == "remove" else regenerate(cookie)
    assert answer(response) == (403, {"error": "stepup-required"})
    assert len(in_use(user)) == 2 and markers(user) == [] and probe(cookie) == 200
    with with_agency(user.agency_id):
        assert recovery.consume(user.id, codes[0])  # the old codes still work


@pytest.mark.parametrize(
    "raw",
    [b"{}", b'{"id": "not-a-uuid"}', b'{"id": 1}', b'{"id": null}', b"[]"],
)
def test_a_body_that_names_no_factor_is_400(raw: bytes) -> None:
    user, _, cookie = stepped_up()
    add_totp(user)
    path = "/api/auth/factors/totp/remove"
    response = client(cookie).post(path, raw, content_type="application/json")
    assert answer(response) == (400, {"error": "invalid"})
    assert len(in_use(user)) == 2


def test_two_parallel_removes_of_the_two_totps_leave_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each session holds its own step-up; both read the factors before either retires, unless
    `hold` makes the second wait (then it sees the first's marker and is signed out)."""
    user, _, a = stepped_up()
    first = first_totp(user)
    second, second_secret = add_totp(user)
    b = signed_in(user, factor="totp")
    assert step_up(client(b), sign_in.code_at(second_secret, STEP)).status_code == 200
    both_read, real = threading.Barrier(2, timeout=3), factor_change._totps

    def read_then_wait(signed: Any) -> list[uuid.UUID]:
        ids = real(signed)
        # Broken when the other request waits on the row lock (or was refused).
        with contextlib.suppress(threading.BrokenBarrierError):
            both_read.wait()
        return ids

    monkeypatch.setattr(factor_change, "_totps", read_then_wait)
    results: list[int] = []

    def run(cookie: str, factor: uuid.UUID) -> None:
        try:
            results.append(remove(cookie, factor).status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=args) for args in ((a, first), (b, second))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(results) == [200, 401] and len(in_use(user)) == 1


def test_regenerate_replaces_the_codes_ends_other_sessions_and_reissues_this_one() -> None:
    user, secret, old_codes = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    assert step_up(client(cookie), sign_in.code_at(secret, STEP)).status_code == 200
    other, deadline = signed_in(user, factor="totp"), row_deadline(cookie)
    response = regenerate(cookie)
    status, body = answer(response)
    keys = {"next", "recovery_codes", "csrf"}
    assert (status, body["next"], set(body)) == (200, "regenerated", keys)
    codes = body["recovery_codes"]
    assert len(set(codes)) == recovery.COUNT
    fresh = response.cookies[COOKIE].value
    assert fresh != cookie and row_deadline(fresh) == deadline
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    with with_agency(user.agency_id):
        assert not any(recovery.consume(user.id, code) for code in old_codes)
        assert recovery.consume(user.id, codes[0]) and not recovery.consume(user.id, codes[0])
    assert listed(fresh)["recovery_left"] == recovery.COUNT - 1


CHANGES = ["add", "remove", "regenerate"]


def change(kind: str, user: AppUser, cookie: str) -> "Response":
    """One credential change of `kind` by a stepped-up session of `user`."""
    if kind == "add":
        return confirm_add(cookie, sign_in.code_at(begun(cookie), STEP))
    if kind == "remove":
        return remove(cookie, add_totp(user)[0])
    return regenerate(cookie)


@pytest.mark.parametrize("kind", CHANGES)
def test_each_change_ends_a_login_waiting_for_its_second_factor(kind: str) -> None:
    """PR 142 R1 P3 #2.2: the user-wide marker of every factor change ends a pending login."""
    user, secret, cookie = stepped_up()
    waiting = sign_in.pending_login(user)
    assert change(kind, user, cookie).status_code == 200
    assert attempt(waiting, sign_in.code_at(secret, STEP + 1)) == "unavailable"
    assert factor_count(user.id) == 0


@pytest.mark.parametrize("kind", CHANGES)
def test_each_change_rotates_the_csrf_token_and_the_old_one_is_refused(kind: str) -> None:
    """PR 142 R1 P3 #2.1: the `csrf` a change answers passes the gate; the old token does not."""
    user, secret, _ = sign_in.signing_in()
    browser, old = csrf_browser(user)
    headers = {"Origin": ORIGIN, "X-CSRFToken": old}

    def post(path: str, body: object) -> "Response":
        data = json.dumps(body)
        kind_ = "application/json"
        return browser.post(path, data, content_type=kind_, secure=True, headers=headers)

    proof = post("/api/auth/stepup", {"purpose": CHANGE, "code": sign_in.code_at(secret, STEP)})
    assert proof.status_code == 200
    if kind == "add":
        new = base64.b32decode(json.loads(post("/api/auth/factors/totp", {}).content)["secret"])
        response = post("/api/auth/factors/totp/confirm", {"code": sign_in.code_at(new, STEP)})
    elif kind == "remove":
        response = post("/api/auth/factors/totp/remove", {"id": str(add_totp(user)[0])})
    else:
        response = post("/api/auth/factors/recovery", {})
    assert_rotated(browser, response, old)


def migrate(*target: str) -> None:
    env = {**os.environ, "DATABASE_URL": os.environ["MIGRATION_DATABASE_URL"]}
    command = [sys.executable, str(MANAGE), "migrate", *target]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_accounts_0014_reverses_and_reapplies_with_a_retired_factor_kept() -> None:
    """skiw_migrator cannot see tenant rows, so the reverse keeps the column and its values and
    puts the 0010 rule back NOT VALID; the re-apply validates both rules again."""
    user, _, cookie = stepped_up()
    old = first_totp(user)
    add_totp(user)
    assert remove(cookie, old).status_code == 200
    try:
        migrate("accounts", "0013")
    finally:
        migrate()
    retired = row(old, user)
    assert retired.retired_at is not None and retired.secret_ct is None
