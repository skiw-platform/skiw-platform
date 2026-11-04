"""The route registry (AUTH-02; plan M3 §3 M3d and §4 M3d row, Risk 4). There is no auth middleware,
so a route is authorized only if its view is an `accounts.auth.wrapper.authorized_action` handler.
Every route of the real URLconf is either wrapped (the view carries `skiw_action`, which
`route()`'s `require_http_methods` keeps) or listed below as public with the reason it needs no
login. A new route that is neither fails here; so does a stale or a contradictory entry. A list
keyed on the route name only holds if each name is one route, so a name used twice fails too."""

from collections import Counter
from collections.abc import Mapping
from importlib import import_module
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from accounts.auth import wrapper
from accounts.auth.wrapper import Signed, authorized_action
from config import routes
from config.routes import route
from tests.test_csrf_gate import walk

URLCONF = "config.urls"
# Reviewed public routes: name -> why it needs no login. Each change needs the reviewer's sign-off.
PUBLIC_ROUTES: dict[str, str] = {
    "healthz": "liveness probe for Docker and the uptime ping; reads no data",
    "readyz": "readiness probe; binds the deployment agency itself and answers by status only",
    "asset": "hashed SPA build files, the same for every visitor",
    "shell": "the SPA page a signed-out visitor loads first; carries only the CSRF token",
    "auth-login": "the password step, before any session exists: uniform answers (AUTH-05) and the"
    " throttle (AUTH-06) stand in for a login; it leaves only a pending state, never a sign-in",
}


def unauthorized(urlconf: str = URLCONF) -> list[str]:
    problems: list[str] = []
    found = list(walk(import_module(urlconf).urlpatterns))
    names = Counter(name for name, _ in found)
    problems += [f"{name}: name used by {n} routes" for name, n in names.items() if name and n > 1]
    for name, pattern in found:
        label = name or str(pattern.pattern)
        wrapped = getattr(pattern.callback, "skiw_action", None) is not None
        if wrapped and name in PUBLIC_ROUTES:
            problems.append(f"{label}: wrapped, but also listed in PUBLIC_ROUTES")
        elif not wrapped and name not in PUBLIC_ROUTES:
            problems.append(f"{label}: neither wrapped by authorized_action nor in PUBLIC_ROUTES")
    problems += [f"{name}: stale PUBLIC_ROUTES entry" for name in PUBLIC_ROUTES.keys() - names]
    return problems


def handler(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    return HttpResponse()


def anything(body: Mapping[str, Any]) -> Mapping[str, Any]:
    return body


def added(monkeypatch: pytest.MonkeyPatch, view: Any, name: str = "added") -> None:
    urls = import_module(URLCONF)
    entry = route(name, view, name=name, methods=("POST",), auth="cookie")
    monkeypatch.setattr(urls, "urlpatterns", [*urls.urlpatterns, entry])


def test_the_registry_walks_the_urlconf_the_app_serves() -> None:
    assert settings.ROOT_URLCONF == URLCONF


def test_every_route_is_wrapped_or_reviewed_as_public() -> None:
    assert unauthorized() == []


def test_a_route_without_the_wrapper_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    added(monkeypatch, lambda request: HttpResponse())
    assert unauthorized() == ["added: neither wrapped by authorized_action nor in PUBLIC_ROUTES"]


def test_a_wrapped_route_passes_through_route(monkeypatch: pytest.MonkeyPatch) -> None:
    added(monkeypatch, authorized_action(schema=anything, permission="test.added")(handler))
    assert unauthorized() == []


def test_a_wrapped_route_listed_as_public_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    added(monkeypatch, authorized_action(schema=anything, permission="test.x")(handler))
    monkeypatch.setitem(PUBLIC_ROUTES, "added", "listed by mistake")
    assert unauthorized() == ["added: wrapped, but also listed in PUBLIC_ROUTES"]


def test_an_unwrapped_route_named_like_a_public_one_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR 109 R1 P2 #1: keyed on the name alone, it would pass as the public `healthz`."""
    added(monkeypatch, lambda request: HttpResponse(), "healthz")
    assert unauthorized() == ["healthz: name used by 2 routes"]


def test_two_wrapped_routes_sharing_a_name_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    for permission in ("test.one", "test.two"):
        added(monkeypatch, authorized_action(schema=anything, permission=permission)(handler))
    assert unauthorized() == ["added: name used by 2 routes"]


def test_a_stale_public_entry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(PUBLIC_ROUTES, "gone", "a route that was removed")
    assert unauthorized() == ["gone: stale PUBLIC_ROUTES entry"]


def test_the_wrapper_reads_no_body_for_the_same_methods_route_calls_safe() -> None:
    """accounts may not import config (import-linter), so the wrapper keeps its own copy."""
    assert wrapper.SAFE_METHODS == routes.SAFE_METHODS
