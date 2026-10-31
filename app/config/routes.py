"""The only way a plain Django view enters a URLconf (spec T6; plan M2d). Semgrep rule
urls-route-only rejects `path(` / `re_path(` anywhere else in app/.

Django keeps no accepted-method list per URL pattern, so `route()` records it on the view it
mounts: dispatch (`require_http_methods`) and the CSRF gate (app/tests/test_csrf_gate.py) read the
same `skiw_methods`. `auth` is how a caller is identified: "cookie" for anything a browser
reaches with its cookies (every route so far, public ones included), "token" for a bearer or API
token route, which must also be listed in the gate's reviewed TOKEN_AUTH_ROUTES.
"""

from collections.abc import Callable, Iterable
from typing import Any, Literal

from django.core.exceptions import ImproperlyConfigured
from django.urls import URLPattern, path
from django.views.decorators.http import require_http_methods

Auth = Literal["cookie", "token"]
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def route(
    pattern: str,
    view: Callable[..., Any],
    *,
    name: str,
    methods: Iterable[str],
    auth: Auth,
) -> URLPattern:
    allowed = tuple(methods)
    # TRACE is refused: Django's CSRF check treats it as safe, the gate does not.
    if not allowed or len(set(allowed)) != len(allowed):
        raise ImproperlyConfigured(f"route {name!r}: methods must be distinct and non-empty")
    if not set(allowed) <= SAFE_METHODS | UNSAFE_METHODS:
        raise ImproperlyConfigured(f"route {name!r}: unknown method in {allowed}")
    if auth not in ("cookie", "token"):
        raise ImproperlyConfigured(f"route {name!r}: auth must be 'cookie' or 'token'")
    mounted = require_http_methods(list(allowed))(view)
    vars(mounted).update(skiw_methods=frozenset(allowed), skiw_auth=auth)
    return path(pattern, mounted, name=name)
