"""`password_step.attempt`, against the real tables as skiw_app (spec Flow 5.1 (1), AUTH-05,
AUTH-06; plan M3 §3 M3e and §4 M3e row). The route that answers it is M3e-2b."""

import re
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import argon2
import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pytest_django import Settings

from accounts.auth import blob, passwords
from accounts.auth.blob import LoginRecord
from accounts.auth.password_step import Verified, attempt
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import Clock, committed_user
from .logins import (
    FAILING,
    PASSWORD,
    consecutive,
    enrolled,
    failing,
    failures,
    random_ip,
    unknown,
    unseal,
)

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
SQL_VALUE = re.compile(r"'(?:[^']|'')*'|\b\d+\b")


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


@pytest.fixture
def spied(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, list[Any]]]:
    """Records every Argon2 verify (with the parameters of the hash it checks), every Argon2 hash
    and every blob open."""
    seen: dict[str, list[Any]] = {"verify": [], "hash": [], "open": []}
    real_verify, real_hash = argon2.PasswordHasher.verify, argon2.PasswordHasher.hash
    real_open = blob.open_login

    def verify(self: argon2.PasswordHasher, hash: str, password: str) -> bool:
        found = argon2.extract_parameters(hash)
        seen["verify"].append((found.time_cost, found.memory_cost, found.parallelism))
        return real_verify(self, hash, password)

    def hash(self: argon2.PasswordHasher, password: str, **kwargs: Any) -> str:
        seen["hash"].append(self.memory_cost)
        return real_hash(self, password, **kwargs)

    def open_login(sealed: bytes, email: str) -> LoginRecord | None:
        seen["open"].append(len(sealed))
        return real_open(sealed, email)

    monkeypatch.setattr(argon2.PasswordHasher, "verify", verify)
    monkeypatch.setattr(argon2.PasswordHasher, "hash", hash)
    monkeypatch.setattr(blob, "open_login", open_login)
    yield seen


def test_the_right_password_is_verified_and_resets_the_lock_counter() -> None:
    user, email = enrolled()
    ip = random_ip()
    assert attempt(email, "wrong", ip) == "failed" and consecutive(email) == 1
    assert attempt(email.upper(), PASSWORD, ip) == Verified(user.id, user.agency_id)
    assert consecutive(email) == 0  # the windowed counters stay; only the run is reset
    assert failures(email, ip) == 1  # a success writes no failure


@pytest.mark.parametrize("case", FAILING)
def test_every_failure_counts_and_logs_one_failure(case: str) -> None:
    """AUTH-05: known with a wrong password, unknown, invited (no password yet) and disabled with
    the right password are one outcome, with one event and one count each."""
    email, password = failing(case)
    ip = random_ip()
    assert attempt(email, password, ip) == "failed"
    assert failures(email, ip) == 1 and consecutive(email) == 1


def test_the_sixth_attempt_is_limited_without_a_lookup_even_when_it_is_right(
    spied: dict[str, list[Any]],
) -> None:
    _, email = enrolled()
    for address in (email, unknown()):
        for count in range(settings.SKIW_AUTH_FAILS_PER_ACCOUNT):
            assert attempt(address, "wrong", random_ip()) == "failed", count
        for seen in spied.values():
            seen.clear()
        ip = random_ip()
        with CaptureQueriesContext(connection) as queries:
            assert attempt(address, PASSWORD, ip) == "limited"
        assert spied == {"verify": [], "hash": [], "open": []}
        assert len(queries.captured_queries) == 1
        assert failures(address, ip) == 0  # a refusal is not counted again


def test_the_ip_limit_refuses_the_twenty_first_attempt() -> None:
    ip = random_ip()
    for count in range(settings.SKIW_AUTH_FAILS_PER_IP):
        assert attempt(unknown(), "wrong", ip) == "failed", count
    _, email = enrolled()
    assert attempt(email, PASSWORD, ip) == "limited"
    assert isinstance(attempt(email, PASSWORD, random_ip()), Verified)


def test_ten_consecutive_failures_lock_the_account_past_the_window(clock: Clock) -> None:
    _, email = enrolled()
    for _ in range(2):
        for count in range(settings.SKIW_AUTH_FAILS_PER_ACCOUNT):
            assert attempt(email, "wrong", random_ip()) == "failed", count
        clock.advance(timedelta(minutes=settings.SKIW_AUTH_WINDOW_MIN))
    assert consecutive(email) == settings.SKIW_AUTH_LOCK_AFTER
    assert attempt(email, PASSWORD, random_ip()) == "limited"  # a new window, still locked
    clock.advance(timedelta(minutes=settings.SKIW_AUTH_LOCK_MIN))
    assert isinstance(attempt(email, PASSWORD, random_ip()), Verified)


def shapes(queries: CaptureQueriesContext) -> list[str]:
    return [SQL_VALUE.sub("?", query["sql"]) for query in queries.captured_queries]


def test_known_and_unknown_do_the_same_work(spied: dict[str, list[Any]]) -> None:
    """Plan §4 M3e row, timing (1) structural: one Argon2 verify with the same parameters, no
    Argon2 hash, one blob open of one length, and the same statements in the same order on every
    failure path that does not get past the password."""
    _, email = enrolled()
    runs = {}
    for case, address in [
        ("known-wrong", email),
        ("unknown", unknown()),
        ("invited", committed_user(status="invited").email),
    ]:
        for seen in spied.values():
            seen.clear()
        with CaptureQueriesContext(connection) as queries:
            assert attempt(address, "wrong", random_ip()) == "failed"
        runs[case] = ({k: list(v) for k, v in spied.items()}, shapes(queries))
    reference = runs["known-wrong"]
    assert reference[0] == {
        "verify": [(3, 65_536, 1)],
        "hash": [],  # the dummy hash was made at start-up
        "open": [blob.LOGIN_SIZE + blob.OVERHEAD],
    }
    assert runs["unknown"] == reference and runs["invited"] == reference


def sealed_of(user: AppUser) -> bytes:
    with with_agency(user.agency_id):
        value = AppUser.objects.get(id=user.id).login_blob_ct
    assert value is not None
    return bytes(value)


def stored_cost(user: AppUser) -> int:
    record = blob.open_login(sealed_of(user), user.email)
    assert record is not None
    return argon2.extract_parameters(record.password_hash).time_cost


def test_a_hash_with_older_parameters_is_remade_at_the_next_sign_in(settings: Settings) -> None:
    """PR 112 R1 P3 #1: after a parameter change, a stored hash costs the old amount until its
    user signs in, and the current amount after; the dummy always costs the current amount."""
    user, email = enrolled()
    disabled, disabled_email = enrolled(status="disabled")
    assert stored_cost(user) == settings.SKIW_ARGON2_TIME_COST
    settings.SKIW_ARGON2_TIME_COST += 1
    assert attempt(email, "wrong", random_ip()) == "failed"
    assert attempt(disabled_email, PASSWORD, random_ip()) == "failed"
    assert stored_cost(user) == stored_cost(disabled) == settings.SKIW_ARGON2_TIME_COST - 1
    assert attempt(email, PASSWORD, random_ip()) == Verified(user.id, user.agency_id)
    assert stored_cost(user) == settings.SKIW_ARGON2_TIME_COST
    assert attempt(email, PASSWORD, random_ip()) == Verified(user.id, user.agency_id)


def test_a_current_hash_is_left_as_it_is() -> None:
    user, email = enrolled()
    before = sealed_of(user)
    assert attempt(email, PASSWORD, random_ip()) == Verified(user.id, user.agency_id)
    assert sealed_of(user) == before


def test_a_password_set_during_the_sign_in_is_not_overwritten(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, email = enrolled()
    settings.SKIW_ARGON2_TIME_COST += 1
    replaced = blob.seal_login(
        blob.LoginRecord(user.id, user.agency_id, passwords.hash_password("set meanwhile")), email
    )
    real = passwords.needs_rehash

    def meanwhile(encoded: str) -> bool:
        AppUser.objects.filter(id=user.id).update(login_blob_ct=replaced)
        return real(encoded)

    monkeypatch.setattr(passwords, "needs_rehash", meanwhile)
    assert attempt(email, PASSWORD, random_ip()) == Verified(user.id, user.agency_id)
    assert sealed_of(user) == replaced
