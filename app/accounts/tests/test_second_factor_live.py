"""The second factor of a login against the real tables as skiw_app (accounts.auth.second_factor;
spec Flow 5.1 (2), D7, AUTH-06; plan M3 §3 M3f, §4 M3f row; PR 128 R1 P2). The route is M3f-3c-2.
The enrolment side of the shared attempt count is in test_factors_live.py."""

import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from functools import partial
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.db import connection
from django.http import HttpRequest
from django.test import RequestFactory

from accounts.auth import blob, factors, password_step, recovery, second_factor, totp
from accounts.auth.password_step import Verified
from accounts.auth.second_factor import Passed, attempt
from accounts.factor_model import UserFactor
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import Clock
from .logins import enrolled, factor_count, unseal

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
LIMIT = settings.SKIW_AUTH_FAILS_PER_ACCOUNT
STEP = 1_000_000  # a fixed step, so no test straddles a 30-second boundary


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


@pytest.fixture(autouse=True)
def at_step(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """totp.accept's clock, in the middle of step STEP; `.step` moves it."""
    now = SimpleNamespace(step=STEP)
    monkeypatch.setattr(
        totp, "time", SimpleNamespace(time=lambda: now.step * totp.PERIOD + totp.PERIOD / 2)
    )
    return now


def signing_in(totp_row: bool = True) -> tuple[AppUser, bytes, list[str]]:
    """An active user with a password, a TOTP factor (secret returned; last accepted step 0) and
    ten recovery codes, as enrolment leaves one."""
    user, _ = enrolled(status="active")
    secret, factor = totp.new_secret(), uuid.uuid4()
    with with_agency(user.agency_id):
        if totp_row:
            UserFactor.objects.create(
                id=factor,
                agency_id=user.agency_id,
                user_id=user.id,
                kind="totp",
                secret_ct=blob.seal_factor_secret(secret, factor, user.id, user.agency_id),
            )
        codes = recovery.generate(user.agency_id, user.id)
    return user, secret, codes


def pending_login(user: AppUser, *, enrol: bool = False) -> HttpRequest:
    request = RequestFactory().get("/")
    request.session = SessionStore()
    password_step.start_pending(request, Verified(user.id, user.agency_id), enrol=enrol)
    return request


def code_at(secret: bytes, step: int) -> str:
    return totp.code(secret, step)


def wrong_for(secret: bytes) -> str:
    valid = {code_at(secret, step) for step in range(STEP - 3, STEP + 4)}
    return next(f"{n:06d}" for n in range(1_000_000) if f"{n:06d}" not in valid)


def stored_step(user: AppUser) -> int:
    with with_agency(user.agency_id):
        return UserFactor.objects.get(user_id=user.id, kind="totp").sign_count


def in_parallel(calls: list[Callable[[], object]]) -> list[object]:
    """Runs every call on its own thread and connection, all released together."""
    results: list[object] = []
    start = threading.Barrier(len(calls))

    def run(call: Callable[[], object]) -> None:
        start.wait()
        try:
            results.append(call())
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(call,)) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_a_right_code_passes_gives_its_attempt_back_and_ends_the_pending_state() -> None:
    user, secret, _ = signing_in()
    request = pending_login(user)
    result = attempt(request, code_at(secret, STEP))
    assert result == Passed(user.id, user.agency_id, "totp")
    assert stored_step(user) == STEP and factor_count(user.id) == 0
    assert not any(key in request.session for key in factors.PENDING_KEYS)
    assert attempt(request, code_at(secret, STEP + 1)) == "unavailable"  # nothing pending now


def test_the_code_of_a_step_already_used_is_refused_and_counted() -> None:
    user, secret, _ = signing_in()
    assert isinstance(attempt(pending_login(user), code_at(secret, STEP)), Passed)
    assert attempt(pending_login(user), code_at(secret, STEP)) == "wrong_code"  # replay
    assert attempt(pending_login(user), code_at(secret, STEP - 1)) == "wrong_code"  # older step
    assert factor_count(user.id) == 2
    assert isinstance(attempt(pending_login(user), code_at(secret, STEP + 1)), Passed)  # later
    assert stored_step(user) == STEP + 1


@pytest.mark.parametrize(("offset", "accepted"), [(-2, False), (-1, True), (1, True), (2, False)])
def test_one_step_either_side_is_accepted_and_two_are_not(offset: int, accepted: bool) -> None:
    user, secret, _ = signing_in()
    result = attempt(pending_login(user), code_at(secret, STEP + offset))
    assert result == (Passed(user.id, user.agency_id, "totp") if accepted else "wrong_code")


def test_parallel_submissions_of_one_code_pass_once() -> None:
    user, secret, _ = signing_in()
    code = code_at(secret, STEP)
    requests = [pending_login(user) for _ in range(LIMIT)]  # no more than the budget
    results = in_parallel([partial(attempt, r, code) for r in requests])
    assert results.count("wrong_code") == LIMIT - 1
    assert len([r for r in results if isinstance(r, Passed)]) == 1
    assert stored_step(user) == STEP and factor_count(user.id) == LIMIT - 1


def test_a_recovery_code_passes_once_in_any_spelling() -> None:
    user, _, codes = signing_in()
    spelled = codes[0].lower().replace("-", " ")
    assert attempt(pending_login(user), spelled) == Passed(user.id, user.agency_id, "recovery")
    assert attempt(pending_login(user), codes[0]) == "wrong_code"  # used
    assert isinstance(attempt(pending_login(user), codes[1]), Passed)  # another is untouched
    assert factor_count(user.id) == 1
    with with_agency(user.agency_id):
        assert UserFactor.objects.filter(user_id=user.id, kind="recovery").count() == 8


def test_two_parallel_uses_of_a_recovery_code_pass_once() -> None:
    user, _, codes = signing_in()
    requests = [pending_login(user) for _ in range(4)]
    results = in_parallel([partial(attempt, r, codes[3]) for r in requests])
    assert len([r for r in results if isinstance(r, Passed)]) == 1
    assert results.count("wrong_code") == 3


@pytest.mark.parametrize("candidate", ["", "12345", "1234567", "abcdef", "١٢٣٤٥٦", "x" * 5000])
def test_anything_that_is_not_a_code_is_wrong_and_counted(candidate: str) -> None:
    user, _, _ = signing_in()
    assert attempt(pending_login(user), candidate) == "wrong_code"
    assert factor_count(user.id) == 1


def test_a_user_with_no_totp_factor_does_the_same_work_and_cannot_pass_with_a_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _, codes = signing_in(totp_row=False)
    used: list[bytes] = []
    real = totp.accept

    def spy(secret: bytes, candidate: str, last: int, now: float | None = None) -> int | None:
        used.append(secret)
        return real(secret, candidate, last, now)

    monkeypatch.setattr(totp, "accept", spy)
    zeros = code_at(bytes(totp.SECRET_BYTES), STEP)  # what the throwaway secret would accept
    assert attempt(pending_login(user), zeros) == "wrong_code"
    assert used == [bytes(totp.SECRET_BYTES)] and factor_count(user.id) == 1
    assert isinstance(attempt(pending_login(user), codes[0]), Passed)  # recovery still works


def test_only_a_pending_login_can_attempt_and_nothing_is_counted_otherwise() -> None:
    user, secret, _ = signing_in()
    code = code_at(secret, STEP)
    empty = RequestFactory().get("/")
    empty.session = SessionStore()
    assert attempt(empty, code) == "unavailable"
    assert attempt(pending_login(user, enrol=True), code) == "unavailable"  # an enrolment
    assert factor_count(user.id) == 0 and stored_step(user) == 0


def test_an_expired_pending_login_is_unavailable(clock: Clock) -> None:
    user, secret, _ = signing_in()
    request = pending_login(user)
    clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN, seconds=1))
    assert attempt(request, code_at(secret, STEP)) == "unavailable"
    assert factor_count(user.id) == 0 and stored_step(user) == 0


@pytest.mark.parametrize("status", ["disabled", "invited"])
def test_a_user_who_is_no_longer_active_is_unavailable_and_nothing_changes(status: str) -> None:
    user, secret, codes = signing_in()
    request = pending_login(user)
    with with_agency(user.agency_id):
        AppUser.objects.filter(id=user.id).update(status=status)
    assert attempt(request, code_at(secret, STEP)) == "unavailable"
    assert attempt(pending_login(user), codes[0]) == "unavailable"
    assert factor_count(user.id) == 0 and stored_step(user) == 0
    with with_agency(user.agency_id):
        assert UserFactor.objects.filter(user_id=user.id, kind="recovery").count() == 10


def test_wrong_codes_end_in_limited_even_for_the_right_code_and_not_for_another_user() -> None:
    user, secret, codes = signing_in()
    other, other_secret, _ = signing_in()
    for _ in range(LIMIT):
        assert attempt(pending_login(user), wrong_for(secret)) == "wrong_code"
    assert attempt(pending_login(user), code_at(secret, STEP)) == "limited"
    assert attempt(pending_login(user), codes[0]) == "limited"  # one budget for both kinds
    assert factor_count(user.id) == LIMIT and stored_step(user) == 0
    assert isinstance(attempt(pending_login(other), code_at(other_secret, STEP)), Passed)
    with connection.cursor() as cursor:  # the key is an HMAC, never the user id
        cursor.execute("SELECT count(*) FROM auth_throttle WHERE key_hmac = %s", [user.id.bytes])
        assert cursor.fetchone() == (0,)


def test_a_success_does_not_use_up_the_budget(at_step: SimpleNamespace) -> None:
    user, secret, _ = signing_in()
    for step in range(STEP, STEP + 3 * LIMIT):  # far more sign-ins than the limit
        at_step.step = step
        assert isinstance(attempt(pending_login(user), code_at(secret, step)), Passed)
    assert factor_count(user.id) == 0


def test_the_wrong_codes_before_a_success_stay_counted() -> None:
    user, secret, _ = signing_in()
    for _ in range(LIMIT - 1):
        attempt(pending_login(user), wrong_for(secret))
    assert isinstance(attempt(pending_login(user), code_at(secret, STEP)), Passed)
    assert factor_count(user.id) == LIMIT - 1
    assert attempt(pending_login(user), wrong_for(secret)) == "wrong_code"
    assert attempt(pending_login(user), wrong_for(secret)) == "limited"


def test_parallel_wrong_codes_cannot_pass_the_limit() -> None:
    """PR 128 R1 P2: K > limit concurrent guesses for one user. The count is taken before the code
    is checked, so exactly LIMIT are checked and the rest are limited, not LIMIT + parallelism."""
    user, secret, _ = signing_in()
    guess = wrong_for(secret)
    requests = [pending_login(user) for _ in range(3 * LIMIT)]
    results = in_parallel([partial(attempt, r, guess) for r in requests])
    assert results.count("wrong_code") == LIMIT
    assert results.count("limited") == 2 * LIMIT
    assert factor_count(user.id) == LIMIT


def test_a_fault_gives_the_attempt_back(monkeypatch: pytest.MonkeyPatch) -> None:
    user, _, codes = signing_in()
    request = pending_login(user)

    def fail(*_: object) -> bool:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(recovery, "consume", fail)
    with pytest.raises(RuntimeError):
        attempt(request, codes[0])
    assert factor_count(user.id) == 0 and password_step.PENDING_USER in request.session
    monkeypatch.undo()
    assert isinstance(attempt(request, codes[0]), Passed)


@contextmanager
def failing_commit(agency_id: uuid.UUID) -> Iterator[None]:
    """with_agency, whose transaction fails when it is left: after the code was compared."""
    with with_agency(agency_id):
        yield
        raise RuntimeError("the commit failed")


def test_a_fault_after_a_wrong_comparison_keeps_the_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR 130 R1 P3: a failure an attacker can provoke after the comparison must not hand the
    guess back (they would see 500 and an uncounted guess)."""
    user, secret, _ = signing_in()
    monkeypatch.setattr(second_factor, "with_agency", failing_commit)
    for n in range(1, LIMIT + 1):
        with pytest.raises(RuntimeError):
            attempt(pending_login(user), wrong_for(secret))
        assert factor_count(user.id) == n
    assert attempt(pending_login(user), wrong_for(secret)) == "limited"  # all five stayed counted
    assert factor_count(user.id) == LIMIT


def test_a_fault_after_the_right_code_rolls_it_back_and_gives_the_attempt_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, secret, _ = signing_in()
    request = pending_login(user)
    with monkeypatch.context() as patch:
        patch.setattr(second_factor, "with_agency", failing_commit)
        with pytest.raises(RuntimeError):
            attempt(request, code_at(secret, STEP))
    assert factor_count(user.id) == 0 and stored_step(user) == 0
    assert isinstance(attempt(request, code_at(secret, STEP)), Passed)  # the code was not used
