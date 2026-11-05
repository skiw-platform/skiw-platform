"""The accounts HTTP views (plan M3 §3 M3e). config.urls mounts them, the one config -> accounts
edge the TEN-10 contract allows (owner Q10 (a)). The login steps run before there is a signed-in
session, so they are reviewed PUBLIC_ROUTES entries (app/tests/test_route_registry.py), not
authorized_action handlers; so is enrolment, which a user without a password reaches by link.
Every answer is one of a few fixed bodies; a failure never says why (AUTH-05)."""

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token

from accounts.auth import enrol, password_step
from accounts.auth.blob import EMAIL_MAX
from accounts.auth.throttle import client_ip

FORM = "application/x-www-form-urlencoded"


def _answer(body: dict[str, str], status: int) -> HttpResponse:
    response = JsonResponse(body, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _failed() -> HttpResponse:
    return _answer({"error": "login-failed"}, 401)


def _fields(request: HttpRequest, first: str, second: str) -> tuple[str, str] | None:
    """Two string fields from a JSON object or a form post (FE-32), or None (UNI-03)."""
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
    one, two = body.get(first), body.get(second)
    if not _text(one) or not _text(two):
        return None
    return one, two


def _text(value: object) -> bool:
    """A str UTF-8 can encode. JSON allows a lone surrogate ("\\ud800"), which Argon2 and
    PostgreSQL refuse with an exception, so it would answer 500 instead of the refusal."""
    if not isinstance(value, str):
        return False
    try:
        value.encode()
    except UnicodeEncodeError:
        return False
    return True


def _credentials(request: HttpRequest) -> tuple[str, str] | None:
    """Email and password, or None (UNI-03)."""
    fields = _fields(request, "email", "password")
    if fields is None:
        return None
    email, password = fields
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


def enrol_password(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/enrol: the link's token and the new password (spec AUTH-08, Flow 5.1 (4)).
    Every refusal, a malformed body among them, gets one answer and no cookie; a malformed body
    touches no row. The link's HMAC stands in for the login throttle: nothing here can be guessed.
    Success leaves the same pending state as a password login, marked as an enrolment, never a
    sign-in: the user is still `invited` until a first second factor (M3f, M3g)."""
    fields = _fields(request, "token", "password")
    verified = None if fields is None else enrol.redeem(*fields)
    if verified is None:
        return _answer({"error": "enrol-failed"}, 401)
    password_step.start_pending(request, verified, enrol=True)
    return _answer({"next": "enrol_factor", "csrf": get_token(request)}, 200)
