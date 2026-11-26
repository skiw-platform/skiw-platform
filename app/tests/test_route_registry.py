"""The route registry (AUTH-02; plan M3 §3 M3d and §4 M3d row, Risk 4). There is no auth middleware,
so a route is authorized only if its view is an `accounts.auth.wrapper.authorized_action` handler.
Every route of the real URLconf is either wrapped (the view carries `skiw_action`, which
`route()`'s `require_http_methods` keeps) or listed below as public with the reason it needs no
login. A new route that is neither fails here; so does a stale or a contradictory entry. A list
keyed on the route name only holds if each name is one route, so a name used twice fails too.

Each wrapped route also carries the permission and business line it registered with (`skiw_action`,
`skiw_line`; slice spec Decision 26). ACTIONS below is the reviewed list of both for every wrapped
route of the real URLconf: a missing, extra or changed route fails, and no route may register
`staff.manage` while M4-rest has no in-app role writer (Decision 29)."""

from collections import Counter
from collections.abc import Mapping
from importlib import import_module
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from accounts.access.catalogue import ROUTE_CODES
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
    "shell-enrol": "the same SPA page at the invite link's path; the token stays in the fragment,"
    " which the browser never sends",
    "auth-session": "says which screen to show (signed out, second factor, enrolment, signed in)"
    " by the wrapper's own checks; one body for every signed-out case (AUTH-05), names no user,"
    " writes nothing and does not move the idle clock",
    "auth-login": "the password step, before any session exists: uniform answers (AUTH-05) and the"
    " throttle (AUTH-06) stand in for a login; it leaves only a pending state, never a sign-in",
    "auth-second-factor": "the second factor of a sign-in, for a pending login session only (the"
    " password step came first): without that session, or for any other pending-state failure, the"
    " one answer is 401 `login-expired` (AUTH-05); wrong codes are throttled per user and ten in a"
    " row lock the user (AUTH-06); the right one completes the sign-in through login(), the one"
    " place a session becomes a login",
    "auth-second-factor-passkey": "passkey options for a pending login session only, as"
    " `auth-second-factor`: without one the answer is 401 `login-expired`; it counts nothing,"
    " signs nobody in and begins nothing for a user with no passkey in use",
    "auth-second-factor-passkey-confirm": "the passkey branch of `auth-second-factor`, for a"
    " pending login session only: the same `login-expired` answer, one `passkey-wrong` for every"
    " assertion that is not the pending user's, the same per-user budget and lock (AUTH-06) in"
    " front of the credential lookup; a right one completes the sign-in through login()",
    "auth-enrol": "the enrolment password, before the user has any credential: the single-use,"
    " expiring HMAC link (AUTH-08) stands in for a login, every refusal has one answer (AUTH-05);"
    " it leaves only a pending enrolment, never a sign-in",
    "auth-enrol-totp": "the first authenticator secret, for a pending enrolment session only (the"
    " enrolment link's password came first): without that session the one answer is 401; it stores"
    " nothing and signs nobody in",
    "auth-enrol-totp-confirm": "the first authenticator code, for a pending enrolment session"
    " only: wrong codes are throttled per user (AUTH-06); the right one completes the sign-in"
    " through login(), the one place a session becomes a login",
}

# Reviewed wrapped routes: name -> (permission, line). Every M4-rest route is a self-service
# `auth.*` code on line `any` (Decisions 6, 26); a later route's line is set by its milestone spec.
ACTIONS: dict[str, tuple[str, str]] = {
    "auth-stepup": ("auth.stepup", "any"),
    "auth-stepup-passkey": ("auth.stepup", "any"),
    "auth-stepup-passkey-confirm": ("auth.stepup", "any"),
    "auth-logout": ("auth.logout", "any"),
    "auth-password": ("auth.password", "any"),
    "auth-factors": ("auth.factors", "any"),
    "auth-factor-totp": ("auth.factor-change", "any"),
    "auth-factor-totp-confirm": ("auth.factor-change", "any"),
    "auth-factor-totp-remove": ("auth.factor-change", "any"),
    "auth-recovery-regenerate": ("auth.factor-change", "any"),
    "auth-factor-passkey": ("auth.factor-change", "any"),
    "auth-factor-passkey-confirm": ("auth.factor-change", "any"),
    "auth-factor-passkey-remove": ("auth.factor-change", "any"),
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


def actions(urlconf: str = URLCONF) -> dict[str, tuple[object, object]]:
    """Every wrapped route -> the (permission, line) its view carries; a missing line is None."""
    return {
        name or str(pattern.pattern): (
            vars(pattern.callback)["skiw_action"],
            getattr(pattern.callback, "skiw_line", None),
        )
        for name, pattern in walk(import_module(urlconf).urlpatterns)
        if getattr(pattern.callback, "skiw_action", None) is not None
    }


def drift(urlconf: str = URLCONF) -> list[str]:
    found = actions(urlconf)
    problems = [f"{name}: wrapped, but not in ACTIONS" for name in found.keys() - ACTIONS.keys()]
    problems += [f"{name}: stale ACTIONS entry" for name in ACTIONS.keys() - found.keys()]
    problems += [
        f"{name}: registers {found[name]}, ACTIONS says {ACTIONS[name]}"
        for name in found.keys() & ACTIONS.keys()
        if found[name] != ACTIONS[name]
    ]
    return sorted(problems)


def managing(urlconf: str = URLCONF) -> list[str]:
    """Wrapped routes that register `staff.manage` (Decision 29: none while M4-rest has no in-app
    writer of roles, ticks, assignments or org units)."""
    return [name for name, (code, _) in actions(urlconf).items() if code == "staff.manage"]


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


def test_every_wrapped_route_registers_the_reviewed_permission_and_line() -> None:
    assert drift() == []


def test_the_reviewed_actions_are_route_codes_on_line_any() -> None:
    assert all(code in ROUTE_CODES and line == "any" for code, line in ACTIONS.values())
    assert {line for _, line in actions().values()} == {"any"}


def test_no_route_registers_staff_manage() -> None:
    assert managing() == []


def test_a_route_registering_staff_manage_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    view = authorized_action(schema=anything, permission="staff.manage", line="any")(handler)
    added(monkeypatch, view)
    monkeypatch.setitem(ACTIONS, "added", ("staff.manage", "any"))  # listed: still refused
    assert drift() == [] and managing() == ["added"]


def test_a_wrapped_route_missing_from_actions_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    view = authorized_action(schema=anything, permission="client.view", line="any")(handler)
    added(monkeypatch, view)
    assert drift() == ["added: wrapped, but not in ACTIONS"]


def test_a_stale_actions_entry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ACTIONS, "gone", ("auth.logout", "any"))
    assert drift() == ["gone: stale ACTIONS entry"]


@pytest.mark.parametrize(
    ("key", "value"),
    [("skiw_line", "insurance"), ("skiw_action", "auth.password"), ("skiw_line", None)],
    ids=["line", "permission", "no-line"],
)
def test_a_route_registering_something_else_fails(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str | None
) -> None:
    view = authorized_action(schema=anything, permission="auth.logout", line="any")(handler)
    if value is None:
        del vars(view)[key]
    else:
        vars(view)[key] = value
    added(monkeypatch, view)
    monkeypatch.setitem(ACTIONS, "added", ("auth.logout", "any"))
    [problem] = drift()
    assert problem.startswith("added: registers")


def test_the_app_serves_no_test_only_probe() -> None:
    """The probes of tests.csrf_urls (`stepup-probe` reads step-up evidence) exist only there."""
    assert [name for name, _ in walk(import_module(URLCONF).urlpatterns) if "probe" in name] == []


def test_a_route_without_the_wrapper_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    added(monkeypatch, lambda request: HttpResponse())
    assert unauthorized() == ["added: neither wrapped by authorized_action nor in PUBLIC_ROUTES"]


def test_a_wrapped_route_passes_through_route(monkeypatch: pytest.MonkeyPatch) -> None:
    added(
        monkeypatch,
        authorized_action(schema=anything, permission="auth.logout", line="any")(handler),
    )
    assert unauthorized() == []


def test_a_wrapped_route_listed_as_public_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    added(
        monkeypatch,
        authorized_action(schema=anything, permission="auth.logout", line="any")(handler),
    )
    monkeypatch.setitem(PUBLIC_ROUTES, "added", "listed by mistake")
    assert unauthorized() == ["added: wrapped, but also listed in PUBLIC_ROUTES"]


def test_an_unwrapped_route_named_like_a_public_one_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR 109 R1 P2 #1: keyed on the name alone, it would pass as the public `healthz`."""
    added(monkeypatch, lambda request: HttpResponse(), "healthz")
    assert unauthorized() == ["healthz: name used by 2 routes"]


def test_two_wrapped_routes_sharing_a_name_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    for permission in ("auth.logout", "auth.password"):
        view = authorized_action(schema=anything, permission=permission, line="any")
        added(monkeypatch, view(handler))
    assert unauthorized() == ["added: name used by 2 routes"]


def test_a_stale_public_entry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(PUBLIC_ROUTES, "gone", "a route that was removed")
    assert unauthorized() == ["gone: stale PUBLIC_ROUTES entry"]


def test_the_wrapper_reads_no_body_for_the_same_methods_route_calls_safe() -> None:
    """accounts may not import config (import-linter), so the wrapper keeps its own copy."""
    assert wrapper.SAFE_METHODS == routes.SAFE_METHODS
