"""The passkey challenge is single use (accounts.auth.passkey.take_challenge on SessionStore.take;
plan M3 §4 M3g). Real session rows, as skiw_app: a second store on the same cookie stands for a
parallel request that loaded the session before the first one took the challenge."""

import threading
import uuid
from datetime import timedelta

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpRequest
from django.test import RequestFactory

from accounts.auth import passkey
from accounts.session import SessionStore

from .authenticator import ORIGIN, RP_ID
from .conftest import Clock

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

USER = uuid.uuid4()


@pytest.fixture(autouse=True)
def relying_party(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", RP_ID)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", ORIGIN)


def on(key: str | None) -> HttpRequest:
    request = RequestFactory().post("/")
    request.session = SessionStore(key)
    return request


def begun(purpose: passkey.Purpose = "login") -> tuple[str, bytes]:
    """A saved session holding a challenge; its cookie and the challenge value."""
    request = on(None)
    if purpose == "register":
        options = passkey.begin_registration(request, USER, "a@example.test", [])
    else:
        options = passkey.begin_assertion(request, purpose, USER, [])
    request.session.save()
    value = passkey._unb64url(options["challenge"])
    assert value is not None
    return str(request.session.session_key), value


@pytest.mark.parametrize("purpose", ["register", "login", "stepup"])
def test_a_challenge_is_taken_once(purpose: passkey.Purpose) -> None:
    key, value = begun(purpose)
    request = on(key)
    taken = passkey.take_challenge(request, purpose, USER)
    assert taken is not None and taken.value == value
    assert passkey.CHALLENGE not in request.session
    assert passkey.take_challenge(on(key), purpose, USER) is None


def test_a_request_that_loaded_it_first_cannot_take_it_again() -> None:
    key, _ = begun()
    stale = on(key)
    assert passkey.CHALLENGE in stale.session  # loaded before the take below
    assert passkey.take_challenge(on(key), "login", USER) is not None
    assert passkey.take_challenge(stale, "login", USER) is None


def test_parallel_takes_give_it_to_one() -> None:
    key, _ = begun()
    requests = [on(key) for _ in range(4)]
    for request in requests:
        assert passkey.CHALLENGE in request.session
    results: list[object] = []
    barrier = threading.Barrier(len(requests))

    def take(request: HttpRequest) -> None:
        barrier.wait()
        try:
            results.append(passkey.take_challenge(request, "login", USER))
        finally:
            connection.close()

    threads = [threading.Thread(target=take, args=(r,)) for r in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(r is not None for r in results) == 1


@pytest.mark.parametrize(
    ("purpose", "user"),
    [("stepup", USER), ("register", USER), ("login", uuid.uuid4())],
    ids=["other-purpose", "registration", "other-user"],
)
def test_a_mismatch_is_refused_and_still_consumed(
    purpose: passkey.Purpose, user: uuid.UUID
) -> None:
    key, _ = begun("login")
    assert passkey.take_challenge(on(key), purpose, user) is None
    assert passkey.take_challenge(on(key), "login", USER) is None


def test_an_expired_challenge_is_refused_and_consumed(clock: Clock) -> None:
    key, _ = begun()
    clock.advance(timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN))
    assert passkey.take_challenge(on(key), "login", USER) is None
    clock.advance(-timedelta(minutes=1))
    assert passkey.take_challenge(on(key), "login", USER) is None


def test_a_malformed_record_is_refused() -> None:
    request = on(None)
    request.session[passkey.CHALLENGE] = {"purpose": "login", "user": str(USER), "value": "x"}
    request.session.save()
    assert passkey.take_challenge(on(request.session.session_key), "login", USER) is None


def test_no_session_row_is_no_challenge() -> None:
    assert passkey.take_challenge(on(None), "login", USER) is None


def test_take_refuses_to_run_inside_a_transaction() -> None:
    key, _ = begun()
    with transaction.atomic(), pytest.raises(RuntimeError, match="outside a transaction"):
        passkey.take_challenge(on(key), "login", USER)
    assert passkey.take_challenge(on(key), "login", USER) is not None


def test_take_keeps_the_rest_of_the_session() -> None:
    request = on(None)
    passkey.begin_assertion(request, "login", USER, [])
    request.session["other"] = "kept"
    request.session.save()
    key = str(request.session.session_key)
    assert passkey.take_challenge(on(key), "login", USER) is not None
    again = SessionStore(key)
    assert again["other"] == "kept" and passkey.CHALLENGE not in again
