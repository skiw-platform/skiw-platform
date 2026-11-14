"""Enrolling a user's first second factor, a TOTP secret (spec Flow 5.1 (4), D7, AUTH-07; plan M3 §3
M3f, DECISIONS M3f-3b-1). No route yet: M3f-3b-2 calls these from the two enrolment endpoints.

`pending()` reads the pending state `password_step.start_pending` left (a login's, or an
enrolment's marked `_skiw_pending_enrol`), refusing one that is malformed, past its deadline, or
older than a user-wide revocation marker: a credential change (password, factor; AUTH-07) at or
after the password step ends a login still waiting for its second factor (PR 141 R1 P2, DECISIONS
M3h-5). The pending start is the app clock, the marker the database's transaction start; a tie
counts as revoked.
Only an enrolment's pending state may add a first factor, and only for a user still `invited`.

Enrolling is two calls. `begin_totp` makes a secret and keeps it in the session sealed
(blob.seal_factor_secret, bound to a new factor id, the user and the agency), so the session row
holds no readable secret (C3); it returns the secret and the `otpauth://` URI to show once.
`confirm_totp` takes the user's first code, and in ONE with_agency() transaction: locks the user,
stores the factor (the same sealed bytes, `sign_count` = the accepted step, so that code cannot
sign the user in again), sets the user `active`, replaces the recovery codes and writes the
user-wide revocation marker (AUTH-07), then runs the caller's `then(user, factor)` last: the
enrolment route signs the user in there (login(), a new session key) and records a `factor.change`
step-up for that key (DECISIONS M3g-2s-1). Any failure rolls all of it back, so no user is
`active` without a factor and recovery codes. The pending keys are cleared after the commit
(login() keeps them).

Wrong codes are counted per user (throttle.factor_reserve: the attempt is counted before the code
is checked, and given back unless the code was wrong). The user row is locked while `invited`, so
two confirmations of one secret take turns: the second finds the user `active` and is refused."""

import base64
import binascii
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from django.http import HttpRequest
from django.utils import timezone

from accounts.auth import blob, recovery, revoke, throttle, totp
from accounts.auth.password_step import (
    PENDING_AGENCY,
    PENDING_AT,
    PENDING_ENROL,
    PENDING_UNTIL,
    PENDING_USER,
)
from accounts.factor_model import UserFactor
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

PENDING_TOTP = "_skiw_pending_totp"  # {"id": factor id, "ct": the sealed secret, base64}
PENDING_KEYS = (
    PENDING_USER,
    PENDING_AGENCY,
    PENDING_AT,
    PENDING_UNTIL,
    PENDING_ENROL,
    PENDING_TOTP,
)
Failure = Literal["unavailable", "limited", "wrong_code"]
Then = Callable[[AppUser, uuid.UUID], None]  # the user, now `active`, and the new factor's id


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
    """The pending user, or None: no pending state, a malformed one, one past its deadline
    (SKIW_LOGIN_PENDING_MIN), or one a credential change ended (module docstring). Outside any
    transaction. A pending state that cannot be used is cleared."""
    session = _store(request)
    try:
        user, agency = uuid.UUID(session[PENDING_USER]), uuid.UUID(session[PENDING_AGENCY])
        since = datetime.fromisoformat(session[PENDING_AT])
        until = datetime.fromisoformat(session[PENDING_UNTIL])
    except (KeyError, TypeError, ValueError):
        clear_pending(request)
        return None
    if (
        None in (since.tzinfo, until.tzinfo)
        or timezone.now() >= until
        or _changed_since(user, agency, since)
    ):
        clear_pending(request)
        return None
    return Pending(user, agency, session.get(PENDING_ENROL) is True)


def _changed_since(user: uuid.UUID, agency: uuid.UUID, since: datetime) -> bool:
    with with_agency(agency):
        return revoke.changed_since(user, since)


def stored_secret(request: HttpRequest, key: str) -> tuple[uuid.UUID, bytes] | None:
    """The factor id and sealed secret `seal_new` stored under `key`, or None if absent or
    malformed."""
    try:
        value = _store(request)[key]
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
    return seal_new(request, PENDING_TOTP, user)


def seal_new(request: HttpRequest, key: str, user: AppUser) -> Setup:
    """A new secret for `user`, kept in the session under `key` sealed (bound to a new factor id,
    the user and the agency), replacing any earlier one; the secret and URI to show once. Shared
    by enrolment (PENDING_TOTP) and a signed-in user adding a TOTP (factor_change.ADD_TOTP)."""
    secret, factor = totp.new_secret(), uuid.uuid4()
    sealed = blob.seal_factor_secret(secret, factor, user.id, user.agency_id)
    _store(request)[key] = {"id": str(factor), "ct": base64.b64encode(sealed).decode()}
    return Setup(totp.text(secret), totp.uri(secret, user.email))


def confirm_totp(
    request: HttpRequest, candidate: str, then: Then | None = None
) -> Enrolled | Failure:
    """Enrols the secret `begin_totp` made if `candidate` is its current code; see the module
    docstring for what that commits, `then` included. "unavailable": no usable enrolment state or
    the user is no longer `invited`, nothing counted. "limited": too many wrong codes, nothing
    checked. "wrong_code": counted against the user. The attempt is counted before the code is
    checked and given back unless the code was wrong (throttle.factor_reserve), so parallel guesses
    cannot exceed the limit."""
    state, stored = pending(request), stored_secret(request, PENDING_TOTP)
    if state is None or not state.enrol or stored is None:
        return "unavailable"
    reservation = throttle.factor_reserve(state.user_id)
    if reservation is None:
        return "limited"
    try:
        result = _confirm(state, *stored, candidate, then)
    except BaseException:
        throttle.factor_release(reservation)  # a fault is not a guess
        raise
    if result == "wrong_code":
        return result  # the attempt stays counted
    throttle.factor_release(reservation)
    if isinstance(result, str):
        return result
    clear_pending(request)
    return Enrolled(state.user_id, state.agency_id, result)


def _confirm(
    state: Pending, factor: uuid.UUID, sealed: bytes, candidate: str, then: Then | None
) -> list[str] | Failure:
    """The recovery codes when the first code is right, else why not."""
    with with_agency(state.agency_id):
        user = AppUser.objects.select_for_update().filter(id=state.user_id, status="invited")
        locked = user.first()
        if locked is None:
            return "unavailable"
        secret = blob.open_factor_secret(sealed, factor, locked.id, locked.agency_id)
        if secret is None:
            return "unavailable"
        step = totp.accept(secret, candidate, 0)
        return "wrong_code" if step is None else _commit(locked, factor, sealed, step, then)


def _commit(
    user: AppUser, factor: uuid.UUID, sealed: bytes, step: int, then: Then | None
) -> list[str]:
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
    if then is not None:
        then(user, factor)
    return codes
