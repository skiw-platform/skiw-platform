"""The accounts HTTP views (plan M3 §3 M3e). config.urls mounts them, the one config -> accounts
edge the TEN-10 contract allows (owner Q10 (a)). The login steps run before there is a signed-in
session, so they are reviewed PUBLIC_ROUTES entries (app/tests/test_route_registry.py), not
authorized_action handlers; so is enrolment, which a user without a password reaches by link,
and the session state route, which answers anyone.
Step-up, logout, password change and the factor routes are signed in, so they are
authorized_action handlers.
Every answer is one of a few fixed bodies; a failure never says why (AUTH-05)."""

import json
import uuid
from collections.abc import Mapping
from datetime import timedelta
from typing import Any, TypeGuard

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token, rotate_token

from accounts.auth import (
    assertion,
    enrol,
    factor_change,
    factors,
    password_change,
    password_step,
    second_factor,
)
from accounts.auth.blob import EMAIL_MAX
from accounts.auth.login import login
from accounts.auth.revoke import mark
from accounts.auth.stepup import PURPOSES, StepUp
from accounts.auth.stepup import verify as verify_stepup
from accounts.auth.throttle import client_ip
from accounts.auth.wrapper import InvalidInput, Signed, authorized_action, nothing, signed_in
from accounts.session import SessionStore
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


def login_second_factor(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/second-factor: the code (authenticator or recovery) for the user the password
    step left pending (spec Flow 5.1 (2)). Every pending-state failure (none, an enrolment's,
    expired, a user no longer `active`) is the one `login-expired` answer with no cookie, so it
    tells a holder of the pending session nothing (AUTH-05); wrong codes are counted per user and
    ten in a row lock the user's second factor (AUTH-06, DECISIONS M3f-3c-1b/d); both end in the
    same `limited` answer. Right: `login()` makes the session a login, called straight after the
    attempt (only the user read is between them). If either fails the code is already spent and
    stays spent: the 500 saves no session, so the pending login is as it was and the user can try
    another code. Accepted, never undone by restoring the code, which would reopen replay
    (DECISIONS M3f-3c-2)."""
    body = _body(request)
    code = None if body is None else body.get("code")
    if not _text(code):
        return _answer({"error": "invalid"}, 400)
    return _second_factor(request, second_factor.attempt(request, code), "code-wrong")


def _second_factor(
    request: HttpRequest, outcome: second_factor.Passed | factors.Failure, wrong: str
) -> HttpResponse:
    """The answers of a second-factor attempt, and on `Passed` the login."""
    if outcome == "unavailable":
        return _answer({"error": "login-expired"}, 401)
    if outcome == "limited":
        return _answer({"error": "limited"}, 429)
    if outcome == "wrong_code":
        return _answer({"error": wrong}, 401)
    with with_agency(outcome.agency_id):
        user = AppUser.objects.get(id=outcome.user_id)
    login(request, user, factor=outcome.factor)
    return _answer({"next": "signed_in", "csrf": get_token(request)}, 200)


NO_PASSKEY = ({"error": "no-passkey"}, 409)  # the user has no passkey in use: nothing begun


def login_passkey_begin(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/second-factor/passkey (no body read): the options for
    navigator.credentials.get(), allowing only the pending user's passkeys in use, and a `login`
    challenge replacing any other (DECISIONS M3g-1d-1). A pending-state failure is `login-expired`,
    as above; no passkey in use is `no-passkey` and begins nothing. Counts nothing."""
    options = assertion.begin_login(request)
    if options == "unavailable":
        return _answer({"error": "login-expired"}, 401)
    if options == "no-passkey":
        return _answer(*NO_PASSKEY)
    return _answer({"options": options}, 200)


def login_passkey(request: HttpRequest) -> HttpResponse:
    """POST /api/auth/second-factor/passkey/confirm, body exactly `{"credential": <object>}` (else
    400 `invalid`, nothing taken or counted): the assertion for this session's `login` challenge,
    which is spent whatever follows. As the code route: `login-expired`, `limited`, or one
    `passkey-wrong` for every assertion that does not prove one of the pending user's passkeys
    (an unknown, retired or other user's credential, a wrong key, a replay), counted on the same
    budget and lock as wrong codes. Right: `login()` with factor `passkey`."""
    body = _body(request)
    credential = None if body is None or body.keys() != {"credential"} else body["credential"]
    if not isinstance(credential, dict):
        return _answer({"error": "invalid"}, 400)
    return _second_factor(request, assertion.finish_login(request, credential), "passkey-wrong")


SESSION_PENDING = {False: "second_factor", True: "enrol_factor"}  # by Pending.enrol


def session_state(request: HttpRequest) -> HttpResponse:
    """GET /api/auth/session: which screen the page shows after a load (DECISIONS M3i-0).
    `signed_in` is exactly the wrapper's checks; `second_factor` and `enrol_factor` are a live
    pending state (`factors.pending`, which clears a stale one, as the routes that use it do);
    anything else is `signed_out`, with one body and status whatever the reason (AUTH-05).
    Apart from that clearing it writes nothing, counts nothing and leaves the idle clock alone.
    Names no user."""
    session = request.session
    if not isinstance(session, SessionStore):
        raise TypeError("the session route needs the accounts session store")
    if signed_in(session):
        state = "signed_in"
    else:
        pending = factors.pending(request)
        state = "signed_out" if pending is None else SESSION_PENDING[pending.enrol]
    return _answer({"state": state, "csrf": get_token(request)}, 200)


def _stepup_body(body: Mapping[str, Any]) -> tuple[str, str]:
    """Exactly `{"purpose": a listed purpose, "code": text}` (UNI-03); the code's shape is
    `stepup.verify`'s to judge."""
    purpose, code = body.get("purpose"), body.get("code")
    if body.keys() != {"purpose", "code"} or not _text(purpose) or not _text(code):
        raise InvalidInput
    if purpose not in PURPOSES:  # after the type check: an unhashable value would raise
        raise InvalidInput
    return purpose, code


STEPUP_REFUSED = {
    "invalid": ({"error": "invalid"}, 400),  # not six ASCII digits: nothing counted
    "unavailable": ({"error": "signed-out"}, 401),  # the user stopped being `active`
    "wrong_code": ({"error": "code-wrong"}, 401),
    "limited": ({"error": "limited"}, 429),  # the budget or the factor lock, as at sign-in
}


@authorized_action(schema=_stepup_body, permission="auth.stepup", own_transaction=True)
def stepup(request: HttpRequest, signed: Signed, data: tuple[str, str]) -> HttpResponse:
    """POST /api/auth/stepup: a TOTP code proves the signed-in user for `purpose` (spec D7,
    AUTH-09; DECISIONS M3h-3). Wrong codes are counted on the user's one second-factor budget and
    feed the same lock as sign-in. The session key stays, so the CSRF token does too. The answer
    names when the step-up stops counting."""
    outcome = verify_stepup(request, signed, *data)
    if not isinstance(outcome, StepUp):
        return _answer(*STEPUP_REFUSED[outcome])
    until = outcome.verified_at + timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN)
    return _answer({"next": "verified", "until": until.isoformat()}, 200)


@authorized_action(schema=nothing, permission="auth.logout")
def logout(request: HttpRequest, signed: Signed, data: None) -> HttpResponse:
    """POST /api/auth/logout, body `{}` (AUTH-13, server half): a marker for this session and the
    row delete commit together in the wrapper's transaction, so the old cookie, and the old row put
    back by SQL, are refused; the empty session makes the middleware delete the cookie. A session
    the wrapper refuses (idle, revoked) is signed out already."""
    mark(signed.agency_id, signed.user_id, str(request.session.session_key))
    request.session.flush()
    rotate_token(request)
    return _answer({"next": "signed_out", "csrf": get_token(request)}, 200)


def _password_body(body: Mapping[str, Any]) -> tuple[str, str]:
    """Exactly `{"current": text, "new": text}`, the new one without NUL (UNI-03)."""
    current, new = body.get("current"), body.get("new")
    if body.keys() != {"current", "new"} or not _text(current) or not _text(new) or "\x00" in new:
        raise InvalidInput
    return current, new


PASSWORD_ANSWERS: dict[password_change.Outcome, tuple[dict[str, str], int]] = {
    "short": ({"error": "password-short"}, 400),  # nothing counted
    "limited": ({"error": "limited"}, 429),  # the login form's budget or lock
    "wrong": ({"error": "password-wrong"}, 401),
    "signed-out": ({"error": "signed-out"}, 401),
    "conflict": ({"error": "changed"}, 409),  # changed by another request meanwhile
}


@authorized_action(schema=_password_body, permission="auth.password", own_transaction=True)
def password(request: HttpRequest, signed: Signed, data: tuple[str, str]) -> HttpResponse:
    """POST /api/auth/password: the current password and a new one (DECISIONS M3h-4). Right: every
    other session of the user ends (AUTH-07) and this one gets a new key, so a new CSRF token."""
    outcome = password_change.change(request, signed, *data)
    if outcome != "changed":
        return _answer(*PASSWORD_ANSWERS[outcome])
    return _answer({"next": "changed", "csrf": get_token(request)}, 200)


@authorized_action(schema=nothing, permission="auth.factors")
def factor_list(request: HttpRequest, signed: Signed, data: None) -> HttpResponse:
    """GET /api/auth/factors: the signed-in user's own TOTP and passkey factor ids in use (M3i
    names the one to retire) and how many recovery codes are left; no secret, key or credential
    id, no step-up [A] (DECISIONS M3h-5, M3g-1c)."""
    own = factor_change.listing(signed)
    totp = [{"id": str(factor)} for factor in own.totp]
    passkeys = [{"id": str(factor)} for factor in own.passkey]
    return _answer({"totp": totp, "passkey": passkeys, "recovery_left": own.recovery_left}, 200)


STEPUP_REQUIRED = ({"error": "stepup-required"}, 403)


@authorized_action(schema=nothing, permission="auth.factor-change")
def factor_totp_begin(request: HttpRequest, signed: Signed, data: None) -> HttpResponse:
    """POST /api/auth/factors/totp, body `{}`: after a `factor.change` step-up of this session, a
    new TOTP secret to add, as text and as an otpauth:// link, shown once; nothing is stored until
    its first code is confirmed. A second call replaces the unconfirmed secret."""
    setup = factor_change.begin(request, signed)
    if setup == "stepup-required":
        return _answer(*STEPUP_REQUIRED)
    return _answer({"secret": setup.secret, "uri": setup.uri}, 200)


def _code_body(body: Mapping[str, Any]) -> str:
    """Exactly `{"code": text}` (UNI-03); its shape is `factor_change.confirm`'s to judge."""
    code = body.get("code")
    if body.keys() != {"code"} or not _text(code):
        raise InvalidInput
    return code


ADD_REFUSED: dict[factor_change.Refused, tuple[dict[str, str], int]] = {
    "no-pending": ({"error": "no-pending"}, 409),  # nothing begun, or already confirmed
    "invalid": ({"error": "invalid"}, 400),  # not six ASCII digits: nothing counted
    "stepup-required": STEPUP_REQUIRED,
    "signed-out": ({"error": "signed-out"}, 401),
    "wrong_code": ({"error": "code-wrong"}, 401),
    "limited": ({"error": "limited"}, 429),
}


@authorized_action(schema=_code_body, permission="auth.factor-change", own_transaction=True)
def factor_totp_confirm(request: HttpRequest, signed: Signed, data: str) -> HttpResponse:
    """POST /api/auth/factors/totp/confirm: the first code of the begun secret (DECISIONS M3h-5).
    Right: the factor is added, every other session of the user ends (AUTH-07) and this one gets a
    new key, so a new CSRF token. Wrong codes count on the user's one budget, not the lock run."""
    outcome = factor_change.confirm(request, signed, data)
    if isinstance(outcome, str):
        return _answer(*ADD_REFUSED[outcome])
    return _answer({"next": "added", "factor_id": str(outcome), "csrf": get_token(request)}, 200)


def _id_body(body: Mapping[str, Any]) -> uuid.UUID:
    """Exactly `{"id": a UUID in text}` (UNI-03)."""
    factor = body.get("id")
    if body.keys() != {"id"} or not _text(factor):
        raise InvalidInput
    try:
        return uuid.UUID(factor)
    except ValueError:
        raise InvalidInput from None


CHANGE_REFUSED = {
    "stepup-required": STEPUP_REQUIRED,
    "signed-out": ({"error": "signed-out"}, 401),
    "not-found": ({"error": "not-found"}, 404),  # not one of the user's factors of that kind
    "last-factor": ({"error": "last-factor"}, 409),  # no TOTP would be left (spec D7)
}


@authorized_action(schema=_id_body, permission="auth.factor-change")
def factor_totp_remove(request: HttpRequest, signed: Signed, data: uuid.UUID) -> HttpResponse:
    """POST /api/auth/factors/totp/remove, body `{"id"}` (DECISIONS M3h-6): after a
    `factor.change` step-up, retires one of the user's TOTP factors, never the last. Every other
    session of the user ends (AUTH-07) and this one gets a new key, so a new CSRF token."""
    return _removed(request, factor_change.remove(request, signed, data, "totp"))


def _removed(request: HttpRequest, outcome: str) -> HttpResponse:
    if outcome != "removed":
        return _answer(*CHANGE_REFUSED[outcome])
    return _answer({"next": "removed", "csrf": get_token(request)}, 200)


@authorized_action(schema=nothing, permission="auth.factor-change")
def recovery_regenerate(request: HttpRequest, signed: Signed, data: None) -> HttpResponse:
    """POST /api/auth/factors/recovery, body `{}` (DECISIONS M3h-6): after a `factor.change`
    step-up, new recovery codes replace the old ones and are in this answer, the only time they
    are shown. Every other session ends (AUTH-07); this one gets a new key and CSRF token."""
    outcome = factor_change.regenerate(request, signed)
    if isinstance(outcome, str):
        return _answer(*CHANGE_REFUSED[outcome])
    body = {"next": "regenerated", "recovery_codes": outcome, "csrf": get_token(request)}
    return _answer(body, 200)


@authorized_action(schema=nothing, permission="auth.factor-change")
def factor_passkey_begin(request: HttpRequest, signed: Signed, data: None) -> HttpResponse:
    """POST /api/auth/factors/passkey, body `{}` (DECISIONS M3g-1c): after a `factor.change`
    step-up of this session, the options for navigator.credentials.create(), the user's passkeys
    in use excluded. A second call replaces the challenge. Nothing is stored until confirmed."""
    options = factor_change.begin_passkey(request, signed)
    if options == "stepup-required":
        return _answer(*STEPUP_REQUIRED)
    return _answer({"options": options}, 200)


def _credential_body(body: Mapping[str, Any]) -> dict[str, Any]:
    """Exactly `{"credential": a JSON object}` (UNI-03); its fields are `passkey`'s to judge."""
    credential = body.get("credential")
    if body.keys() != {"credential"} or not isinstance(credential, dict):
        raise InvalidInput
    return credential


PASSKEY_REFUSED: dict[str, tuple[dict[str, str], int]] = {
    # no challenge for this user, a registration that does not verify, or an id known already
    "refused": ({"error": "passkey-refused"}, 400),
    "stepup-required": STEPUP_REQUIRED,
    "signed-out": ({"error": "signed-out"}, 401),
}


@authorized_action(schema=_credential_body, permission="auth.factor-change", own_transaction=True)
def factor_passkey_confirm(
    request: HttpRequest, signed: Signed, data: dict[str, Any]
) -> HttpResponse:
    """POST /api/auth/factors/passkey/confirm, body `{"credential"}`: the new passkey, as the
    browser returned it, for the challenge begun in this session (taken outside any transaction).
    Right: the passkey is added, every other session of the user ends (AUTH-07) and this one gets
    a new key, so a new CSRF token. Every refusal of the credential is one answer."""
    outcome = factor_change.confirm_passkey(request, signed, data)
    if isinstance(outcome, str):
        return _answer(*PASSKEY_REFUSED[outcome])
    return _answer({"next": "added", "factor_id": str(outcome), "csrf": get_token(request)}, 200)


@authorized_action(schema=_id_body, permission="auth.factor-change")
def factor_passkey_remove(request: HttpRequest, signed: Signed, data: uuid.UUID) -> HttpResponse:
    """POST /api/auth/factors/passkey/remove, body `{"id"}` (DECISIONS M3g-1c): after a
    `factor.change` step-up, retires one of the user's passkeys while a TOTP stays. Every other
    session of the user ends (AUTH-07) and this one gets a new key, so a new CSRF token."""
    return _removed(request, factor_change.remove(request, signed, data, "passkey"))
