"""The CSRF gate with a logged-in session (plan M3 §3 M3d and §4 M3d row; M2d deviation (b)).

The browser loads the shell, then signs in through `accounts.auth.login()`, which rotates the CSRF
secret (carry-over (h)). There is no login route before M3e, so the fixture does what the login
response will do: it hands the browser the new session cookie and the rotated `__Host-csrftoken`.
Every cookie-auth mutating route then reaches its handler with the new token and is refused by
CSRF without it, with a wrong or cross-site one, and with the token from before the login."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from django.conf import settings
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from pytest_django import DjangoDbBlocker

from accounts.auth.login import login
from accounts.session import SessionStore
from accounts.tests.conftest import committed_user
from tests.test_csrf_gate import (
    CASES_URLCONF,
    COOKIE_MUTATING,
    CROSS_SITE,
    META,
    ORIGIN,
    Pair,
    assert_csrf_refused,
    assert_past_csrf,
    ids,
    send,
)

pytestmark = [pytest.mark.live, pytest.mark.urls(CASES_URLCONF)]


@dataclass(frozen=True)
class SignedIn:
    client: Client
    token: str  # the token login() rotated to, as the login response will return it (M3e)
    before: str  # the token the shell gave before the login


@pytest.fixture
def signed_in(dist: Path, django_db_blocker: DjangoDbBlocker) -> Iterator[SignedIn]:
    with django_db_blocker.unblock():
        client = Client(enforce_csrf_checks=True)
        match = META.search(client.get("/", secure=True).content.decode())
        assert match, "the shell carries no CSRF token"
        request = RequestFactory().post("/", secure=True)
        request.session = store = SessionStore()
        login(request, committed_user(), factor="passkey")
        store.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = str(store.session_key)
        client.cookies[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
        yield SignedIn(client, get_token(request), match.group(1))
        store.delete()


@pytest.mark.parametrize("pair", COOKIE_MUTATING, ids=ids)
def test_a_signed_in_browser_reaches_the_handler_with_the_rotated_token(
    signed_in: SignedIn, pair: Pair
) -> None:
    response = send(
        signed_in.client, pair.method, pair.url, {"Origin": ORIGIN, "X-CSRFToken": signed_in.token}
    )
    assert_past_csrf(response, pair)


# case -> (Origin, which token, the code config.csrf.failure sends)
REFUSALS = {
    "missing": (ORIGIN, None, "token-missing"),
    "wrong": (ORIGIN, "x" * 64, "token-invalid"),
    "cross-site": (CROSS_SITE, "rotated", "origin"),
    "before-login": (ORIGIN, "before", "token-invalid"),
}


@pytest.mark.parametrize("case", REFUSALS)
@pytest.mark.parametrize("pair", COOKIE_MUTATING, ids=ids)
def test_a_signed_in_browser_is_refused_by_csrf(signed_in: SignedIn, pair: Pair, case: str) -> None:
    origin, sent, code = REFUSALS[case]
    headers = {"Origin": origin}
    if sent is not None:
        tokens = {"rotated": signed_in.token, "before": signed_in.before}
        headers["X-CSRFToken"] = tokens.get(sent, sent)
    assert_csrf_refused(send(signed_in.client, pair.method, pair.url, headers), code)
