"""Throttle counters, windows and the soft-lock against the real tables as skiw_app (spec Flow 5.1,
AUTH-06; plan M3c §4). skiw_app cannot delete these rows, so every test uses a fresh email and IP
and rows from earlier runs stay; the clock is frozen (conftest `clock`)."""

import ipaddress
import json
import re
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.auth.throttle import RUN, blocked, keys, record_failure, reset_on_success

from .conftest import Clock

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
WINDOW, LOCK = timedelta(minutes=15), timedelta(minutes=30)  # SKIW_AUTH_WINDOW_MIN, _LOCK_MIN


def window_of(now: datetime) -> datetime:
    """The fixed window holding `now`, worked out here rather than by the code under test."""
    size = WINDOW // timedelta(seconds=1)
    return datetime.fromtimestamp(int(now.timestamp()) // size * size, UTC)


def random_ip() -> str:
    return str(ipaddress.IPv6Address(secrets.token_bytes(16)))


@pytest.fixture
def who() -> tuple[str, str]:
    return f"{uuid.uuid4().hex}@Example.test", random_ip()


def count(key: bytes, start: datetime | None) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(sum(count), 0) FROM auth_throttle"
            " WHERE key_hmac = %s AND (window_start = %s OR %s IS NULL AND window_start > %s)",
            [key, start, start, RUN],
        )
        return int(cursor.fetchone()[0])


def events(email: str) -> list[dict[str, int]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT details_json FROM security_event WHERE kind = 'account.locked'"
            " AND email_hmac = %s",
            [keys(email, "").account],
        )
        return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in cursor]


def fail(email: str, ip: str, clock: Clock, times: int) -> None:
    """Failures the way M3e makes them: a limited attempt is refused, so it waits a window."""
    for _ in range(times):
        if blocked(email, ip) == "account":
            clock.advance(WINDOW)
        assert blocked(email, ip) is None
        record_failure(email, ip)


def test_twenty_parallel_failures_count_twenty(clock: Clock, who: tuple[str, str]) -> None:
    email, ip = who
    start = threading.Barrier(20)

    def one(_: int) -> None:
        try:
            start.wait()
            record_failure(email, ip)
        finally:
            connection.close()

    with ThreadPoolExecutor(20) as pool:
        list(pool.map(one, range(20)))
    k, window = keys(email, ip), window_of(clock.now)
    assert (count(k.account, window), count(k.ip, window), count(k.lock, RUN)) == (20, 20, 20)
    assert count(k.lock, None) == 2  # locks at 10 and 20, one frozen instant: one marker row
    assert sorted(event["consecutive"] for event in events(email)) == [10, 20]


def test_account_and_ip_limits_roll_over_with_the_window(
    clock: Clock, who: tuple[str, str]
) -> None:
    email, ip = who
    end = window_of(clock.now) + WINDOW
    end += WINDOW * (int(end.timestamp()) // 900 % 2 == 0)  # odd: no 30-min window ends here
    clock.now = end - timedelta(seconds=1)
    for n in range(5):
        assert blocked(email, ip) is None, n
        record_failure(email, ip)
    assert blocked(email, ip) == "account"  # the 6th attempt is limited
    clock.advance(timedelta(seconds=1))  # the next window starts
    assert blocked(email, ip) is None
    for n in range(19):
        record_failure(f"{n}{email}", ip)
    assert blocked(f"new{email}", ip) is None
    record_failure(f"19{email}", ip)
    assert blocked(f"new{email}", ip) == "ip"  # the 21st attempt from one IP is limited


def test_lock_after_ten_consecutive_for_thirty_minutes(
    clock: Clock, who: tuple[str, str], security_log: pytest.LogCaptureFixture
) -> None:
    email, ip = who
    fail(email, ip, clock, 9)
    assert events(email) == [] and count(keys(email, ip).lock, None) == 0
    fail(email, ip, clock, 1)
    assert blocked(email, ip) == "lock" and events(email) == [{"consecutive": 10}]
    assert [r.getMessage() for r in security_log.records] == [
        "account soft-locked after 10 consecutive failed logins"
    ]
    clock.advance(LOCK - timedelta(seconds=1))
    assert blocked(email, ip) == blocked(email, random_ip()) == "lock"  # from any IP
    clock.advance(timedelta(seconds=1))
    assert blocked(email, ip) is None


def test_success_resets_the_consecutive_count(clock: Clock, who: tuple[str, str]) -> None:
    email, ip = who
    fail(email, ip, clock, 9)
    reset_on_success(email.upper())
    fail(email, ip, clock, 9)
    assert count(keys(email, ip).lock, RUN) == 9 and blocked(email, ip) != "lock"
    fail(email, ip, clock, 1)
    assert blocked(email, ip) == "lock"


def shapes(email: str, ip: str, clock: Clock) -> tuple[list[str], list[object]]:
    """Statement shapes (literals removed) and outcomes of ten failures and the checks between."""
    outcomes: list[object] = []
    with CaptureQueriesContext(connection) as captured:
        for _ in range(10):
            outcomes.append(blocked(email, ip))
            if outcomes[-1] == "account":
                clock.advance(WINDOW)
            record_failure(email, ip)
        outcomes.append(blocked(email, ip))
    literal = re.compile(r"'(?:[^']|'')*'(::\w+)?|\b\d+\b")
    return [literal.sub("?", q["sql"]) for q in captured.captured_queries], outcomes


def test_an_unknown_email_is_limited_and_locked_like_a_known_one(clock: Clock) -> None:
    known = f"{uuid.uuid4().hex}@example.test"
    record_failure(known, random_ip())
    reset_on_success(known)  # a real account: it has signed in before
    clock.advance(WINDOW)
    unknown, start = f"no-such-{uuid.uuid4().hex}@example.test", clock.now
    known_run = shapes(known, random_ip(), clock)
    clock.now = start
    assert shapes(unknown, random_ip(), clock) == known_run
    assert known_run[1][-1] == "lock"


def test_no_raw_email_or_ip_in_any_row_or_sql_parameter(clock: Clock, who: tuple[str, str]) -> None:
    email, ip = who
    with CaptureQueriesContext(connection) as captured:
        fail(email, ip, clock, 10)
        blocked(email, ip)
        reset_on_success(email)
    text = "\n".join(q["sql"] for q in captured.captured_queries).lower()
    for raw in (email.lower(), email.split("@")[0], ip, ipaddress.ip_address(ip).exploded):
        assert raw.lower() not in text
    assert "insert into security_event" in text and "on conflict" in text
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM security_event WHERE email_hmac = %s", [keys(email, ip).account]
        )
        row = " ".join(str(value) for value in cursor.fetchone()).lower()
    assert email.split("@")[0] not in row and ip not in row
