"""The second factor of a login (spec Flow 5.1 (2), D7, AUTH-06; plan M3 §3 M3f, DECISIONS
M3f-3c-1). No route yet: M3f-3c-2 calls `attempt` from `POST /api/auth/second-factor`, then
`login()`. It checks one code for the user a password step left pending (`factors.pending`, not an
enrolment's): a TOTP code or a recovery code, told apart by shape (a TOTP code is exactly six
ASCII digits, a recovery code is sixteen symbols).

Order: the pending state; the attempt is counted (`throttle.factor_reserve`, one atomic statement,
before anything is checked; over the limit, or while the factor lock holds, is `limited` and
nothing else happens); then, in one with_agency() transaction, the user must still be `active` and
the code is checked. A verified code, or a fault before the comparison, gives the attempt back
(`factor_release`), so only wrong codes stay counted. A fault AFTER a wrong comparison (leaving
the transaction) keeps the count: otherwise a failure an attacker can provoke would hand every
guess back (PR 130 R1 P3). TOTP and recovery codes share the one per-user budget. Feeding wrong
codes to the factor soft-lock (`factor_failed`, `factor_reset`) is M3f-3c-1d.

A TOTP code is accepted by a conditional update, `sign_count < step`, and the update's row count
decides: of two parallel submissions of one code, one finds the stored step already at it and is
refused, so a code works once whatever the interleaving (a read-then-write check would pass both).
A recovery code is `recovery.consume`, a `DELETE ... RETURNING`. A user with no TOTP factor takes
the same path with a throwaway secret, so having one or not does not change the work done (the
result is never used).

On success the pending state is cleared, because login() keeps it; the caller then calls login()
with `factor`. Nothing here logs and no code is kept anywhere (UNI-09). Consuming a recovery code
is a use of the factor, not a change to the factor set, so it writes no revocation marker (AUTH-07;
plan M3f lists only adding, removing and regenerating)."""

import uuid
from dataclasses import dataclass
from typing import Literal

from django.http import HttpRequest

from accounts.auth import blob, factors, recovery, throttle, totp
from accounts.auth.factors import Failure
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

NO_SECRET = bytes(totp.SECRET_BYTES)  # for a user with no TOTP row; its result is never used


@dataclass(frozen=True)
class Passed:
    """A verified second factor; the caller passes `factor` to login()."""

    user_id: uuid.UUID
    agency_id: uuid.UUID
    factor: Literal["totp", "recovery"]


def _is_totp(candidate: str) -> bool:
    return len(candidate) == totp.DIGITS and candidate.isascii() and candidate.isdigit()


@dataclass
class _Seen:
    """What `_check` learned before it left the transaction, for the case that leaving raises."""

    wrong: bool = False  # the code was compared and was wrong


def attempt(request: HttpRequest, candidate: str) -> Passed | Failure:
    """ "unavailable": no pending login (none, an enrolment's, expired or malformed) or the user is
    no longer `active`; nothing is left counted. "limited": the attempt limit or the factor lock
    holds, nothing was checked. "wrong_code": counted against the user."""
    state = factors.pending(request)
    if state is None or state.enrol:
        return "unavailable"
    reservation = throttle.factor_reserve(state.user_id)
    if reservation is None:
        return "limited"
    kind: Literal["totp", "recovery"] = "totp" if _is_totp(candidate) else "recovery"
    seen = _Seen()
    try:
        result = _check(state, candidate, kind, seen)
    except BaseException:
        # Only a fault BEFORE the comparison is not a guess; after a wrong one the count stays.
        if not seen.wrong:
            throttle.factor_release(reservation)
        raise
    if result == "wrong_code":
        return result  # the attempt stays counted
    throttle.factor_release(reservation)
    if result == "unavailable":
        return result
    factors.clear_pending(request)
    return Passed(state.user_id, state.agency_id, kind)


def _check(
    state: factors.Pending, candidate: str, kind: Literal["totp", "recovery"], seen: _Seen
) -> Literal["ok", "unavailable", "wrong_code"]:
    with with_agency(state.agency_id):
        user = AppUser.objects.filter(id=state.user_id, status="active").first()
        if user is None:
            return "unavailable"
        right = _totp(user, candidate) if kind == "totp" else recovery.consume(user.id, candidate)
        seen.wrong = not right  # the comparison is done
    return "ok" if right else "wrong_code"


def _totp(user: AppUser, candidate: str) -> bool:
    rows = list(UserFactor.objects.filter(user_id=user.id, kind="totp"))
    if not rows:
        totp.accept(NO_SECRET, candidate, 0)  # the same work, whatever the answer
        return False
    for row in rows:
        secret = blob.open_factor_secret(
            bytes(row.secret_ct or b""), row.id, user.id, user.agency_id
        )
        step = None if secret is None else totp.accept(secret, candidate, row.sign_count)
        # The row count decides: another request may have taken this step since the row was read.
        if step is not None and UserFactor.objects.filter(id=row.id, sign_count__lt=step).update(
            sign_count=step
        ):
            return True
    return False
