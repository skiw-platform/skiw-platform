"""The second-factor soft-lock and its alert against the real tables as skiw_app (spec Flow 5.1
"Failures", AUTH-06; plan M3 §3 M3f; PR 130 R1 P2). The primitives only: `factor_failed`,
`factor_reset` and the lock check in `factor_reserve`. `second_factor.attempt` (M3f-3c-1c) calls
them. skiw_app cannot delete throttle rows or events, so every test uses a fresh user, email and
IP; the clock is frozen (conftest `clock`)."""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from accounts.auth import throttle

from .conftest import Clock
from .logins import factor_count, random_ip

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
AFTER = settings.SKIW_AUTH_LOCK_AFTER
LOCK = timedelta(minutes=settings.SKIW_AUTH_LOCK_MIN)
WINDOW = timedelta(minutes=settings.SKIW_AUTH_WINDOW_MIN)


@pytest.fixture
def who() -> tuple[uuid.UUID, str, str]:
    return uuid.uuid4(), f"{uuid.uuid4().hex}@Example.test", random_ip()


def key(user: uuid.UUID) -> bytes:
    return throttle._hmac(throttle.FACTOR_LOCK, str(user))


def run(user: uuid.UUID) -> int:
    """The user's consecutive wrong codes, the counter the lock counts."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(sum(count), 0) FROM auth_throttle"
            " WHERE key_hmac = %s AND window_start = %s",
            [key(user), throttle.RUN],
        )
        return int(cursor.fetchone()[0])


def markers(user: uuid.UUID) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM auth_throttle WHERE key_hmac = %s AND window_start > %s",
            [key(user), throttle.RUN],
        )
        return int(cursor.fetchone()[0])


def events(email: str, ip: str) -> list[dict[str, int]]:
    k = throttle.keys(email, ip)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT details_json FROM security_event WHERE kind = 'factor.locked'"
            " AND email_hmac = %s AND ip_hmac = %s",
            [k.account, k.ip],
        )
        return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in cursor]


def fail(who: tuple[uuid.UUID, str, str], times: int = 1) -> None:
    for _ in range(times):
        throttle.factor_failed(*who)


def test_the_lock_comes_at_the_lock_after_th_wrong_code_with_an_alert_and_ends_after_lock_min(
    clock: Clock, who: tuple[uuid.UUID, str, str], security_log: pytest.LogCaptureFixture
) -> None:
    user, email, ip = who
    fail(who, AFTER - 1)
    assert markers(user) == 0 and events(email, ip) == []
    reservation = throttle.factor_reserve(user)  # still free
    assert reservation is not None
    throttle.factor_release(reservation)
    fail(who)
    assert markers(user) == 1 and events(email, ip) == [{"consecutive": AFTER}]
    assert [r.getMessage() for r in security_log.records if "soft-locked" in r.getMessage()] == [
        f"second factor soft-locked after {AFTER} consecutive wrong codes"
    ]
    assert str(user) not in security_log.text and email not in security_log.text
    assert throttle.factor_reserve(user) is None and factor_count(user) == 0  # nothing changed
    clock.advance(WINDOW)  # a fresh budget window does not lift it
    assert throttle.factor_reserve(user) is None and factor_count(user) == 0
    clock.advance(LOCK - WINDOW - timedelta(seconds=1))
    assert throttle.factor_reserve(user) is None  # one second before LOCK_MIN
    clock.advance(timedelta(seconds=1))
    assert throttle.factor_reserve(user) is not None  # LOCK_MIN after the marker


def test_the_run_is_consecutive_across_windows(
    clock: Clock, who: tuple[uuid.UUID, str, str]
) -> None:
    user, email, ip = who
    for _ in range(AFTER):
        fail(who)
        clock.advance(WINDOW)  # the budget windows move on, the run does not
    assert markers(user) == 1 and events(email, ip) == [{"consecutive": AFTER}]


def test_a_verified_code_ends_the_run(who: tuple[uuid.UUID, str, str]) -> None:
    user, email, ip = who
    fail(who, AFTER - 1)
    assert run(user) == AFTER - 1
    throttle.factor_reset(user)
    assert run(user) == 0
    fail(who)
    assert run(user) == 1 and markers(user) == 0 and events(email, ip) == []


def test_the_lock_is_one_users_and_separate_from_the_password_lock(
    clock: Clock, who: tuple[uuid.UUID, str, str]
) -> None:
    user, email, ip = who
    fail(who, AFTER)
    other = uuid.uuid4()
    assert throttle.factor_reserve(user) is None and throttle.factor_reserve(other) is not None
    assert throttle.blocked(email, ip) is None  # the password step is not locked by it
    throttle.reset_on_success(email)  # nor cleared by a verified password
    assert run(user) == AFTER and throttle.factor_reserve(user) is None


def test_the_alert_names_the_account_and_ip_by_hmac_only(
    clock: Clock, who: tuple[uuid.UUID, str, str]
) -> None:
    _, email, ip = who
    fail(who, AFTER)
    k = throttle.keys(email, ip)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT email_hmac, ip_hmac, details_json::text FROM security_event"
            " WHERE kind = 'factor.locked' AND email_hmac = %s",
            [k.account],
        )
        ((email_hmac, ip_hmac, details),) = cursor.fetchall()
    assert (bytes(email_hmac), bytes(ip_hmac)) == (k.account, k.ip)
    assert json.loads(details) == {"consecutive": AFTER}
    assert email not in details and ip not in details


def test_parallel_wrong_codes_lose_no_count_and_lock_each_time_once(
    clock: Clock, who: tuple[uuid.UUID, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SKIW_AUTH_LOCK_AFTER", 3)
    user, email, ip = who
    start = threading.Barrier(8)

    def one(_: int) -> None:
        try:
            start.wait()
            throttle.factor_failed(user, email, ip)
        finally:
            connection.close()

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(one, range(8)))
    assert run(user) == 8 and markers(user) == 1  # one frozen instant: one marker row
    assert sorted(event["consecutive"] for event in events(email, ip)) == [3, 6]


def test_the_run_is_written_outside_transactions_only(who: tuple[uuid.UUID, str, str]) -> None:
    """PR 131 R1 P3: inside a caller's transaction a rollback would take the run, the marker and
    the event with it, and wrong codes would never reach the lock."""
    user, email, ip = who
    fail(who, AFTER - 1)
    with pytest.raises(TransactionManagementError), transaction.atomic():
        throttle.factor_failed(user, email, ip)
    with pytest.raises(TransactionManagementError), transaction.atomic():
        throttle.factor_reset(user)
    assert run(user) == AFTER - 1 and markers(user) == 0 and events(email, ip) == []
