"""The per-user second-factor attempt count against the real tables as skiw_app
(accounts.auth.throttle.factor_reserve / factor_release; spec Flow 5.1, AUTH-06; plan M3 §3 M3f;
PR 128 R1 P2). The count is taken before a code is checked, in one statement, so parallel guesses
cannot pass the limit. Driven here through the enrolment's `confirm_totp`; the sign-in second factor
(M3f-3c-1b) uses the same two functions."""

import threading
from collections.abc import Callable, Iterator
from datetime import timedelta
from functools import partial

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.http import HttpRequest
from django.test import RequestFactory

from accounts.auth import factors, password_step, throttle
from accounts.auth.password_step import Verified
from accounts.session import SessionStore
from accounts.user_model import AppUser

from .conftest import Clock
from .logins import factor_count, unseal
from .test_factors_live import begun, current, enrolling, state, wrong_for

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
LIMIT = settings.SKIW_AUTH_FAILS_PER_ACCOUNT


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def sessions(count: int) -> tuple[AppUser, bytes, list[HttpRequest]]:
    """One enrolling user in `count` browsers, each holding the same unconfirmed secret."""
    user, first = enrolling()
    _, secret = begun(first)
    requests = [first]
    for _ in range(count - 1):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        password_step.start_pending(request, Verified(user.id, user.agency_id), enrol=True)
        request.session[factors.PENDING_TOTP] = dict(first.session[factors.PENDING_TOTP])
        requests.append(request)
    return user, secret, requests


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


def test_parallel_wrong_codes_cannot_pass_the_limit() -> None:
    """PR 128 R1 P2: K > limit concurrent guesses for one user. The attempt is counted before the
    code is checked, so exactly LIMIT are checked and the rest are limited."""
    user, secret, requests = sessions(3 * LIMIT)
    guess = wrong_for(secret)
    results = in_parallel([partial(factors.confirm_totp, r, guess) for r in requests])
    assert results.count("wrong_code") == LIMIT
    assert results.count("limited") == 2 * LIMIT
    assert factor_count(user.id) == LIMIT and state(user) == ("invited", [])


def test_parallel_guesses_around_the_right_code_still_stay_within_the_limit() -> None:
    user, secret, requests = sessions(2 * LIMIT)
    codes = [current(secret)] + [wrong_for(secret)] * (2 * LIMIT - 1)
    results = in_parallel(
        [partial(factors.confirm_totp, r, c) for r, c in zip(requests, codes, strict=True)]
    )
    assert results.count("wrong_code") <= LIMIT
    assert len([r for r in results if isinstance(r, factors.Enrolled)]) <= 1
    assert state(user)[0] in ("invited", "active")


def test_parallel_reservations_are_let_through_up_to_the_limit_and_no_further() -> None:
    user, _, _ = sessions(1)
    results = in_parallel([partial(throttle.factor_reserve, user.id) for _ in range(4 * LIMIT)])
    assert len([r for r in results if r is not None]) == LIMIT
    assert factor_count(user.id) == LIMIT  # a refused reservation changes nothing


def test_the_right_code_gives_its_attempt_back_and_the_wrong_ones_stay_counted() -> None:
    user, request = enrolling()
    _, secret = begun(request)
    for _ in range(LIMIT - 1):
        assert factors.confirm_totp(request, wrong_for(secret)) == "wrong_code"
    assert isinstance(factors.confirm_totp(request, current(secret)), factors.Enrolled)
    assert factor_count(user.id) == LIMIT - 1


def test_a_fault_gives_the_attempt_back(monkeypatch: pytest.MonkeyPatch) -> None:
    user, request = enrolling()
    _, secret = begun(request)

    def fail(*_: object) -> list[str]:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(factors, "_commit", fail)
    with pytest.raises(RuntimeError):
        factors.confirm_totp(request, current(secret))
    assert factor_count(user.id) == 0


def test_a_release_gives_back_to_the_window_it_counted_in(clock: Clock) -> None:
    user, _, _ = sessions(1)
    old = throttle.factor_reserve(user.id)
    assert old is not None and factor_count(user.id) == 1
    clock.advance(timedelta(minutes=settings.SKIW_AUTH_WINDOW_MIN))
    assert throttle.factor_reserve(user.id) is not None and factor_count(user.id) == 1
    throttle.factor_release(old)  # the old window, not this one
    assert factor_count(user.id) == 1
    clock.advance(-timedelta(minutes=settings.SKIW_AUTH_WINDOW_MIN))
    assert factor_count(user.id) == 0  # the old window is back to zero
    throttle.factor_release(old)  # never below zero
    assert factor_count(user.id) == 0


def test_counting_inside_a_transaction_is_refused() -> None:
    """A rolled-back transaction would take the count with it and a guess would go uncounted."""
    user, _, _ = sessions(1)
    with pytest.raises(TransactionManagementError), transaction.atomic():
        throttle.factor_reserve(user.id)
    assert factor_count(user.id) == 0
