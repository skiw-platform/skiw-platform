"""The accounts HTTP views (plan M3 §3 M3e). config.urls mounts them, the one config -> accounts
edge the TEN-10 contract allows (owner Q10 (a)). The login steps run before there is a signed-in
session, so they are reviewed PUBLIC_ROUTES entries (app/tests/test_route_registry.py), not
authorized_action handlers; so is enrolment, which a user without a password reaches by link.
Every answer is one of a few fixed bodies; a failure never says why (AUTH-05)."""

import json
from collections.abc import Mapping
from typing import Any, TypeGuard

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token

from accounts.auth import enrol, factors, password_step
from accounts.auth.blob import EMAIL_MAX
from accounts.auth.login import login
from accounts.auth.throttle import client_ip
from accounts.user_model import AppUser
from tenancy.binding import with_agency

FORM = "application/x-www-form-urlencoded"


def _answer(body: Mapping[str, object], status: int) -> HttpResponse:
    response = JsonResponse(body, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _failed() -> HttpResponse:
    return _answer({"error": "login-failed"}, 401)


def _body(request: HttpRequest) -> Mapping[str, Any] | None:
    """The JSON object or form fields posted, or None (UNI-03)."""
    if request.content_type == "application/json":
        try:
            body = json.loads(request.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return body if isinstance(body, dict) else None
    return request.POST if request.content_type == FORM else None


def _fields(request: HttpRequest, first: str, second: str) -> tuple[str, str] | None:
    """Two string fields from a JSON object or a form post (FE-32), or None (UNI-03)."""
    body = _body(request)
    if body is None:
        return None
    one, two = body.get(first), body.get(second)
    if not _text(one) or not _text(two):
        return None
    return one, two


def _text(value: object) -> TypeGuard[str]:
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


def _expired() -> HttpResponse:
    """No usable enrolment state: none, past SKIW_LOGIN_PENDING_MIN, or the user is no longer
    `invited`. The caller holds a pending session, so this tells nothing about any account; the
    page says to ask for a new link (docs/runbooks/host-rebuild.md "Enrol a user")."""
    return _answer({"error": "enrol-expired"}, 401)


def enrol_factor_begin(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/enrol/totp (no body): a new TOTP secret for the enrolling user, as text and
    as an otpauth:// link, shown once. A second call replaces the unconfirmed secret. Nothing is
    stored until the first code is confirmed."""
    setup = factors.begin_totp(request)
    if setup is None:
        return _expired()
    return _answer({"secret": setup.secret, "uri": setup.uri}, 200)


def enrol_factor_confirm(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/enrol/totp/confirm: the first code from the user's authenticator. Right: the
    user is active, the pending state is gone, the session is a completed login (factor `totp`) and
    the ten recovery codes are in this answer, the only time they are shown. Wrong codes are counted
    per user (AUTH-06). `login()` runs after the enrolment commits and outside any transaction; if
    it failed the user would be active with a factor and sign in normally, but the codes would be
    lost (plan M3 §3 M3f, DECISIONS M3f-3b-2)."""
    body = _body(request)
    code = None if body is None else body.get("code")
    if not _text(code):
        return _answer({"error": "invalid"}, 400)
    outcome = factors.confirm_totp(request, code)
    if outcome == "unavailable":
        return _expired()
    if outcome == "limited":
        return _answer({"error": "limited"}, 429)
    if outcome == "wrong_code":
        return _answer({"error": "code-wrong"}, 401)
    with with_agency(outcome.agency_id):
        user = AppUser.objects.get(id=outcome.user_id)
    login(request, user, factor="totp")
    return _answer(
        {"next": "signed_in", "recovery_codes": outcome.codes, "csrf": get_token(request)}, 200
    )
