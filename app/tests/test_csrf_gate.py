"""The CSRF gate (spec T6 "Django CSRF on all mutating routes", A.19; plan M2d; owner Q4 (a)).

A behaviour test over a mechanically complete inventory, not a `csrf_exempt` scan. The inventory
is every URL pattern with the methods and auth kind route() recorded on it (config.routes); the
fixtures say only how to build a request. The cases run on tests.csrf_urls, which is config.urls
plus two test-only cookie-auth POST routes, one a plain view and one an `authorized_action`. Here
the browser has no session; test_csrf_gate_live.py runs the mutating cases signed in.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.http.response import HttpResponseBase
from django.test import Client
from django.urls import NoReverseMatch, URLPattern, URLResolver, resolve, reverse

from config.routes import UNSAFE_METHODS, route
from tests.csrf_fixtures import FIXTURES

URLCONFS = ("config.urls", "tests.csrf_urls")
CASES_URLCONF = "tests.csrf_urls"
ORIGIN = "https://testserver"  # the test client's host, over HTTPS as behind Caddy
CROSS_SITE = "https://evil.example"
META = re.compile(r'<meta name="csrf-token" content="([A-Za-z0-9]{64})">')
# Reviewed bearer or API-token routes (no cookie): (route name, method) -> reason and the PR whose
# reviewer signed it off. Starts empty.
TOKEN_AUTH_ROUTES: dict[tuple[str, str], str] = {}


@dataclass(frozen=True)
class Pair:
    name: str
    method: str
    auth: str
    url: str
    methods: frozenset[str]
    wrapped: bool  # an authorized_action handler, which answers 401 without a login


def walk(entries: Sequence[Any], prefix: str = "") -> Iterator[tuple[str, URLPattern]]:
    for entry in entries:
        if isinstance(entry, URLResolver):
            namespace = f"{prefix}{entry.namespace}:" if entry.namespace else prefix
            yield from walk(entry.url_patterns, namespace)
        else:
            yield (f"{prefix}{entry.name}" if entry.name else ""), entry


def inventory(urlconf: str) -> tuple[list[Pair], list[str]]:
    pairs: list[Pair] = []
    problems: list[str] = []
    for name, pattern in walk(import_module(urlconf).urlpatterns):
        methods = getattr(pattern.callback, "skiw_methods", None)
        if methods is None or not name:
            # django-ninja views are csrf_exempt with no skiw_methods: the PR that adds ninja
            # extends this gate first (docs/DECISIONS.md, M2d).
            problems.append(f"{pattern.pattern}: not mounted by config.routes.route()")
            continue
        fixture = FIXTURES.get(name)
        if fixture is None:
            problems.append(f"{name}: no fixture in tests/csrf_fixtures.py")
            continue
        try:
            url = reverse(name, urlconf=urlconf, kwargs=fixture.path_kwargs)
        except NoReverseMatch:
            problems.append(f"{name}: its fixture does not resolve the path parameters")
            continue
        if resolve(url, urlconf).func is not pattern.callback:
            problems.append(f"{name}: its fixture URL reaches another pattern")
        auth = vars(pattern.callback)["skiw_auth"]
        for method in sorted(methods):
            if any((p.name, p.method) == (name, method) for p in pairs):
                problems.append(f"{name} {method}: registered twice")
            token_auth = method in UNSAFE_METHODS and auth != "cookie"
            if token_auth and (name, method) not in TOKEN_AUTH_ROUTES:
                problems.append(f"{name} {method}: token auth not in TOKEN_AUTH_ROUTES")
            wrapped = getattr(pattern.callback, "skiw_action", None) is not None
            pairs.append(Pair(name, method, auth, url, frozenset(methods), wrapped))
    token = {(p.name, p.method) for p in pairs if p.auth == "token" and p.method in UNSAFE_METHODS}
    problems += [
        f"{entry}: stale TOKEN_AUTH_ROUTES entry" for entry in TOKEN_AUTH_ROUTES.keys() - token
    ]
    return pairs, problems


PAIRS = inventory(CASES_URLCONF)[0]
COOKIE_MUTATING = [p for p in PAIRS if p.method in UNSAFE_METHODS and p.auth == "cookie"]
REFUSED_VERBS = [
    (p, verb)
    for p in {p.name: p for p in PAIRS}.values()
    for verb in sorted(UNSAFE_METHODS - p.methods)
]


def ids(pair: Pair) -> str:
    return f"{pair.name}-{pair.method}"


@pytest.fixture
def browser(dist: Path) -> tuple[Client, str]:
    """A client that loaded the shell: the HttpOnly cookie in its jar, the token from the meta."""
    client = Client(enforce_csrf_checks=True)
    shell = client.get("/", secure=True)
    match = META.search(shell.content.decode())
    assert match, "the shell carries no CSRF token"
    return client, match.group(1)


def send(client: Client, method: str, url: str, headers: dict[str, str]) -> HttpResponseBase:
    body = FIXTURES[resolve(url).url_name or ""].body
    return client.generic(
        method, url, body, content_type="application/json", secure=True, headers=headers
    )


def assert_past_csrf(response: HttpResponseBase, pair: Pair) -> None:
    """The handler's own outcome, not a CSRF refusal (for a browser that passed the check)."""
    assert "X-Skiw-Csrf" not in response.headers
    answers = FIXTURES[pair.name].answers
    if answers is not None:
        assert response.status_code == answers
    else:
        assert response.status_code < 300 or response.status_code in (400, 422)


def assert_csrf_refused(response: HttpResponseBase, code: str) -> None:
    assert isinstance(response, HttpResponse)
    assert response.status_code == 403
    assert response.headers.get("X-Skiw-Csrf") == "rejected"
    assert response.content.decode() == code


@pytest.mark.parametrize("urlconf", URLCONFS)
def test_inventory_is_complete(urlconf: str) -> None:
    pairs, problems = inventory(urlconf)
    assert pairs
    assert problems == []


def test_a_view_mounted_without_route_fails_completeness(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = import_module(CASES_URLCONF)
    bare = route("bare", lambda request: None, name="bare", methods=("GET",), auth="cookie")
    vars(bare.callback).pop("skiw_methods")
    monkeypatch.setattr(urls, "urlpatterns", [*urls.urlpatterns, bare])
    assert inventory(CASES_URLCONF)[1] == ["bare: not mounted by config.routes.route()"]


@pytest.mark.urls(CASES_URLCONF)
@pytest.mark.parametrize("pair", COOKIE_MUTATING, ids=ids)
def test_cookie_auth_mutating_route_accepts_a_same_origin_token(
    browser: tuple[Client, str], pair: Pair
) -> None:
    client, token = browser
    valid = send(client, pair.method, pair.url, {"Origin": ORIGIN, "X-CSRFToken": token})
    if pair.wrapped:  # past CSRF, the wrapper refuses a browser that never signed in
        assert "X-Skiw-Csrf" not in valid.headers
        assert valid.status_code == 401
    else:
        assert_past_csrf(valid, pair)


# case -> (Origin, token or None for none, the code config.csrf.failure sends)
REFUSALS = {
    "missing": (ORIGIN, None, "token-missing"),
    "wrong": (ORIGIN, "x" * 64, "token-invalid"),
    "cross-site": (CROSS_SITE, "valid", "origin"),
}


@pytest.mark.urls(CASES_URLCONF)
@pytest.mark.parametrize("case", REFUSALS)
@pytest.mark.parametrize("pair", COOKIE_MUTATING, ids=ids)
def test_cookie_auth_mutating_route_is_refused_by_csrf(
    browser: tuple[Client, str], pair: Pair, case: str
) -> None:
    client, token = browser
    origin, sent, code = REFUSALS[case]
    headers = {"Origin": origin}
    if sent is not None:
        headers["X-CSRFToken"] = token if sent == "valid" else sent
    assert_csrf_refused(send(client, pair.method, pair.url, headers), code)


@pytest.mark.urls(CASES_URLCONF)
@pytest.mark.parametrize(("pair", "verb"), REFUSED_VERBS, ids=lambda v: getattr(v, "name", v))
def test_a_verb_the_route_does_not_accept_is_refused_by_the_view(
    browser: tuple[Client, str], pair: Pair, verb: str
) -> None:
    client, token = browser
    response = send(client, verb, pair.url, {"Origin": ORIGIN, "X-CSRFToken": token})
    assert response.status_code == 405


@pytest.mark.urls(CASES_URLCONF)
def test_token_auth_routes_refuse_a_session_cookie_alone(browser: tuple[Client, str]) -> None:
    client, _ = browser
    for name, method in TOKEN_AUTH_ROUTES:
        pair = next(p for p in PAIRS if (p.name, p.method) == (name, method))
        assert not 200 <= send(client, method, pair.url, {"Origin": ORIGIN}).status_code < 300


def test_csrf_cookie_is_host_prefixed_and_http_only(dist: Path) -> None:
    response = Client().get("/", secure=True)
    cookie = response.cookies["__Host-csrftoken"]
    assert cookie["secure"] is True and cookie["httponly"] is True
    assert cookie["samesite"] == "Strict" and cookie["path"] == "/"
    assert cookie["domain"] == "" and cookie["max-age"] == "" and cookie["expires"] == ""
    assert META.search(response.content.decode())
    assert "no-store" in response["Cache-Control"]


@pytest.mark.parametrize(
    ("methods", "auth"),
    [((), "cookie"), (("GET", "GET"), "cookie"), (("TRACE",), "cookie"), (("GET",), "none")],
)
def test_route_refuses_a_bad_registration(methods: tuple[str, ...], auth: Any) -> None:
    with pytest.raises(ImproperlyConfigured, match="route 'x'"):
        route("x", lambda request: None, name="x", methods=methods, auth=auth)
