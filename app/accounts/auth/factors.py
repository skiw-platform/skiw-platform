"""Enrolling a user's first second factor, a TOTP secret (spec Flow 5.1 (4), D7, AUTH-07; plan M3 §3
M3f, DECISIONS M3f-3b-1). No route yet: M3f-3b-2 calls these from the two enrolment endpoints.

`pending()` reads the pending state `password_step.start_pending` left (a login's, or an
enrolment's marked `_skiw_pending_enrol`), refusing one that is malformed or past its deadline.
Only an enrolment's pending state may add a first factor, and only for a user still `invited`.

Enrolling is two calls. `begin_totp` makes a secret and keeps it in the session sealed
(blob.seal_factor_secret, bound to a new factor id, the user and the agency), so the session row
holds no readable secret (C3); it returns the secret and the `otpauth://` URI to show once.
`confirm_totp` takes the user's first code, and in ONE with_agency() transaction: locks the user,
stores the factor (the same sealed bytes, `sign_count` = the accepted step, so that code cannot
sign the user in again), sets the user `active`, replaces the recovery codes and writes the
user-wide revocation marker (AUTH-07). Any failure rolls all of it back, so no user is `active`
without a factor and recovery codes. The pending keys are cleared after the commit, so a caller
cannot reach login() with them still set (login() keeps them).

Wrong codes are counted per user (throttle.factor_*). The user row is locked while `invited`, so
two confirmations of one secret take turns: the second finds the user `active` and is refused."""

import base64
import binascii
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from django.http import HttpRequest
from django.utils import timezone

from accounts.auth import blob, recovery, revoke, throttle, totp
from accounts.auth.password_step import PENDING_AGENCY, PENDING_ENROL, PENDING_UNTIL, PENDING_USER
from accounts.factor_model import UserFactor
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

PENDING_TOTP = "_skiw_pending_totp"  # {"id": factor id, "ct": the sealed secret, base64}
PENDING_KEYS = (PENDING_USER, PENDING_AGENCY, PENDING_UNTIL, PENDING_ENROL, PENDING_TOTP)
Failure = Literal["unavailable", "limited", "wrong_code"]


@dataclass(frozen=True)
class Pending:
    user_id: uuid.UUID
    agency_id: uuid.UUID
    enrol: bool


@dataclass(frozen=True)
class Setup:
    secret: str = field(repr=False)  # base32, to type in
    uri: str = field(repr=False)  # otpauth://, to import


@dataclass(frozen=True)
class Enrolled:
    user_id: uuid.UUID
    agency_id: uuid.UUID
    codes: list[str] = field(repr=False)  # the recovery codes, shown once


def _store(request: HttpRequest) -> SessionStore:
    if not isinstance(request.session, SessionStore):
        raise TypeError("the second factor needs the accounts session store")
    return request.session


def clear_pending(request: HttpRequest) -> None:
    """Every key of a pending state, including an unconfirmed secret."""
    session = _store(request)
    for key in PENDING_KEYS:
        session.pop(key, None)


def pending(request: HttpRequest) -> Pending | None:
    """The pending user, or None: no pending state, a malformed one, or one past its deadline
    (SKIW_LOGIN_PENDING_MIN). A pending state that cannot be used is cleared."""
    session = _store(request)
    try:
        user, agency = uuid.UUID(session[PENDING_USER]), uuid.UUID(session[PENDING_AGENCY])
        until = datetime.fromisoformat(session[PENDING_UNTIL])
    except (KeyError, TypeError, ValueError):
        until = None
    if until is None or until.tzinfo is None or timezone.now() >= until:
        clear_pending(request)
        return None
    return Pending(user, agency, session.get(PENDING_ENROL) is True)


def _secret(session: SessionStore) -> tuple[uuid.UUID, bytes] | None:
    """The factor id and sealed secret `begin_totp` stored, or None if absent or malformed."""
    try:
        value = session[PENDING_TOTP]
        return uuid.UUID(value["id"]), base64.b64decode(value["ct"], validate=True)
    except (KeyError, TypeError, ValueError, binascii.Error):
        return None


def begin_totp(request: HttpRequest) -> Setup | None:
    """A new secret for the enrolling user, replacing any earlier unconfirmed one; None unless
    this is an enrolment's pending state and the user is still `invited`."""
    state = pending(request)
    if state is None or not state.enrol:
        return None
    with with_agency(state.agency_id):
        user = AppUser.objects.filter(id=state.user_id, status="invited").first()
    if user is None:
        return None
    secret, factor = totp.new_secret(), uuid.uuid4()
    sealed = blob.seal_factor_secret(secret, factor, user.id, user.agency_id)
    _store(request)[PENDING_TOTP] = {"id": str(factor), "ct": base64.b64encode(sealed).decode()}
    return Setup(totp.text(secret), totp.uri(secret, user.email))


def confirm_totp(request: HttpRequest, candidate: str) -> Enrolled | Failure:
    """Enrols the secret `begin_totp` made if `candidate` is its current code; see the module
    docstring for what that commits. "unavailable": no usable enrolment state or the user is no
    longer `invited`, nothing counted. "limited": too many wrong codes, nothing checked.
    "wrong_code": counted against the user."""
    state, session = pending(request), _store(request)
    stored = _secret(session)
    if state is None or not state.enrol or stored is None:
        return "unavailable"
    if throttle.factor_blocked(state.user_id):
        return "limited"
    factor, sealed = stored
    with with_agency(state.agency_id):
        user = AppUser.objects.select_for_update().filter(id=state.user_id, status="invited")
        locked = user.first()
        if locked is None:
            return "unavailable"
        secret = blob.open_factor_secret(sealed, factor, locked.id, locked.agency_id)
        if secret is None:
            return "unavailable"
        step = totp.accept(secret, candidate, 0)
        if step is not None:
            codes = _commit(locked, factor, sealed, step)
    if step is None:
        throttle.record_factor_failure(state.user_id)  # after the lookup, outside the tenant
        return "wrong_code"
    clear_pending(request)
    return Enrolled(state.user_id, state.agency_id, codes)


def _commit(user: AppUser, factor: uuid.UUID, sealed: bytes, step: int) -> list[str]:
    UserFactor.objects.create(
        id=factor,
        agency_id=user.agency_id,
        user_id=user.id,
        kind="totp",
        secret_ct=sealed,
        sign_count=step,
    )
    user.status = "active"
    user.save(update_fields=["status"])
    codes = recovery.generate(user.agency_id, user.id)
    revoke.mark(user.agency_id, user.id, None)  # AUTH-07: a new factor revokes the older sessions
    return codes
