"""The accounts HTTP views (plan M3 §3 M3e). config.urls mounts them, the one config -> accounts
edge the TEN-10 contract allows (owner Q10 (a)). The login steps run before there is a signed-in
session, so they are reviewed PUBLIC_ROUTES entries (app/tests/test_route_registry.py), not
authorized_action handlers. Every answer is one of three fixed bodies; a failure never says why
(AUTH-05)."""

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token

from accounts.auth import password_step
from accounts.auth.throttle import client_ip

EMAIL_MAX = 254  # RFC 5321 §4.5.3.1.3: the longest path, so the longest address
FORM = "application/x-www-form-urlencoded"


def _answer(body: dict[str, str], status: int) -> HttpResponse:
    response = JsonResponse(body, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _failed() -> HttpResponse:
    return _answer({"error": "login-failed"}, 401)


def _credentials(request: HttpRequest) -> tuple[str, str] | None:
    """Email and password from a JSON object or a form post (FE-32), or None (UNI-03)."""
    if request.content_type == "application/json":
        try:
            body = json.loads(request.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(body, dict):
            return None
    elif request.content_type == FORM:
        body = request.POST
    else:
        return None
    email, password = body.get("email"), body.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return None
    if not 0 < len(email) <= EMAIL_MAX or "\x00" in email or not password:
        return None  # PostgreSQL text takes no NUL
    return email, password


def login_password(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/login. A malformed body gets the failure answer without touching any row:
    it names no account to count against."""
    credentials = _credentials(request)
    if credentials is None:
        return _failed()
    outcome = password_step.attempt(*credentials, client_ip(request))
    if outcome == "limited":
        return _answer({"error": "limited"}, 429)
    if outcome == "failed":
        return _failed()
    password_step.start_pending(request, outcome)
    return _answer({"next": "second_factor", "csrf": get_token(request)}, 200)
