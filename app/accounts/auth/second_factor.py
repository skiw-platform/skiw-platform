"""The second factor of a login (spec Flow 5.1 (2), D7, AUTH-06; plan M3 §3 M3f, DECISIONS
M3f-3c-1). `POST /api/auth/second-factor` calls `attempt`, then `login()`; step-up
(`stepup.verify`, M3h-3) shares `counted` and `match_totp`, so one user's sign-in and step-up
codes share one budget, one lock run and one `sign_count`. `attempt` checks one code for the user
a password step left pending (`factors.pending`, not an enrolment's): a TOTP code or a recovery
code, told apart by shape (a TOTP code is exactly six ASCII digits, a recovery code is sixteen
symbols).

Order: the pending state; the attempt is counted (`throttle.factor_reserve`, one atomic statement,
before anything is checked; over the limit, or while the factor lock holds, is `limited` and
nothing else happens); then, in one with_agency() transaction, the user must still be `active` and
the code is checked. A verified code, or a fault before the comparison, gives the attempt back
(`factor_release`), so only wrong codes stay counted; a wrong code also counts toward the factor
soft-lock (`factor_failed`: Flow 5.1 "Failures", SKIW_AUTH_LOCK_AFTER in a row lock the user's
second factor for SKIW_AUTH_LOCK_MIN and raise the owner alert), a verified one resets that run.
A fault AFTER a wrong comparison (leaving the transaction) keeps the count and feeds the lock.
TOTP and recovery codes share the one per-user budget and the one run.

A TOTP code is accepted by a conditional update, `sign_count < step`, and the update's row count
decides: of two parallel submissions of one code, one finds the stored step already at it and is
refused, so a code works once whatever the interleaving (a read-then-write check would pass both).
A recovery code is `recovery.consume`, a `DELETE ... RETURNING`. A user with no TOTP factor takes
the same path with a throwaway secret, so having one or not does not change the work done (the
result is never used).

On success the pending state is cleared, because login() keeps it; the caller then calls login()
with `factor`. Only the lock writes anything outside the tables above (an event and a warning,
HMACs and counts only) and no code is kept anywhere (UNI-09). Consuming a recovery code
is a use of the factor, not a change to the factor set, so it writes no revocation marker (AUTH-07;
plan M3f lists only adding, removing and regenerating)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from django.http import HttpRequest

from accounts.auth import blob, factors, recovery, throttle, totp
from accounts.auth.factors import Failure
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

NO_SECRET = bytes(totp.SECRET_BYTES)  # for a user with no TOTP row; its result is never used
Counted = Literal["ok", "unavailable", "limited", "wrong_code"]


@dataclass(frozen=True)
class Passed:
    """A verified second factor; the caller passes `factor` to login()."""

    user_id: uuid.UUID
    agency_id: uuid.UUID
    factor: Literal["totp", "recovery", "passkey"]  # passkey: accounts.auth.assertion (M3g-1d-1)


def is_totp(candidate: str) -> bool:
    """The shape of a TOTP code: exactly six ASCII digits."""
    return len(candidate) == totp.DIGITS and candidate.isascii() and candidate.isdigit()


@dataclass
class _Seen:
    """What `_check` learned before it left the transaction, for the case that leaving raises."""

    wrong: bool = False  # the code was compared and was wrong
    email: str = ""  # of the user, for the lock event's HMACs


def attempt(request: HttpRequest, candidate: str) -> Passed | Failure:
    """ "unavailable": no pending login (none, an enrolment's, expired or malformed) or the user is
    no longer `active`; nothing is left counted. "limited": the attempt limit or the factor lock
    holds, nothing was checked. "wrong_code": counted against the user, and toward the lock."""
    state = factors.pending(request)
    if state is None or state.enrol:
        return "unavailable"
    kind: Literal["totp", "recovery"] = "totp" if is_totp(candidate) else "recovery"

    def check(user: AppUser) -> bool:
        if kind == "totp":
            return match_totp(user, candidate) is not None
        return recovery.consume(user.id, candidate)

    result = counted(request, state.user_id, state.agency_id, check, feeds_lock=True)
    if result != "ok":
        return result
    factors.clear_pending(request)
    return Passed(state.user_id, state.agency_id, kind)


def counted(
    request: HttpRequest,
    user_id: uuid.UUID,
    agency_id: uuid.UUID,
    check: Callable[[AppUser], bool],
    *,
    feeds_lock: bool,
    precheck: Callable[[], bool] | None = None,
) -> Counted:
    """The one copy of the count, fault and lock rules for a code check (UNI-05; DECISIONS
    M3h-3), used by sign-in and step-up. `check(user)` runs inside with_agency(agency_id) on the
    user's `active` row and says whether the code was right; whatever it writes commits only with
    that transaction. Optional `precheck()` runs after reservation but before with_agency(),
    for audited pre-tenant discovery; False still counts as a wrong comparison for an active user.
    Outside any transaction (the factor counters refuse one).

    "limited": refused by `factor_reserve` (budget or factor lock), nothing checked.
    "unavailable": the user is no longer `active`; the attempt is given back. "wrong_code": the
    attempt stays counted and, if `feeds_lock`, feeds the factor lock's run. "ok": the attempt is
    given back and, if `feeds_lock`, the run ends. A fault before the comparison gives the attempt
    back; after a wrong comparison it keeps the count (and feeds the run if `feeds_lock`)."""
    reservation = throttle.factor_reserve(user_id)
    if reservation is None:
        return "limited"
    seen = _Seen()
    try:
        ready = precheck is None or precheck()
        result = _check(user_id, agency_id, lambda user: ready and check(user), seen)
    except BaseException:
        # Only a fault BEFORE the comparison is not a guess. After a wrong comparison the guess
        # stays counted (and counts toward the lock) even if leaving the transaction failed:
        # otherwise a failure an attacker can provoke would hand every guess back (PR 130 R1 P3).
        if not seen.wrong:
            throttle.factor_release(reservation)
        elif feeds_lock:
            throttle.factor_failed(user_id, seen.email, throttle.client_ip(request))
        raise
    if result == "wrong_code":
        if feeds_lock:
            throttle.factor_failed(user_id, seen.email, throttle.client_ip(request))
        return result  # the attempt stays counted
    throttle.factor_release(reservation)
    if result == "ok" and feeds_lock:
        throttle.factor_reset(user_id)
    return result


def _check(
    user_id: uuid.UUID, agency_id: uuid.UUID, check: Callable[[AppUser], bool], seen: _Seen
) -> Literal["ok", "unavailable", "wrong_code"]:
    with with_agency(agency_id):
        user = AppUser.objects.filter(id=user_id, status="active").first()
        if user is None:
            return "unavailable"
        right = check(user)
        seen.wrong, seen.email = not right, user.email  # the comparison is done
    return "ok" if right else "wrong_code"


def match_totp(user: AppUser, candidate: str) -> UserFactor | None:
    """The user's TOTP factor whose code `candidate` is, with that step now used up, or None.
    Inside the caller's with_agency(); only `counted` checks may call it (the step is stored).
    A retired factor (M3h-6) is never read, and one retired after the read is not used."""
    rows = list(UserFactor.objects.filter(user_id=user.id, kind="totp", retired_at__isnull=True))
    if not rows:
        totp.accept(NO_SECRET, candidate, 0)  # the same work, whatever the answer
        return None
    for row in rows:
        secret = blob.open_factor_secret(
            bytes(row.secret_ct or b""), row.id, user.id, user.agency_id
        )
        step = None if secret is None else totp.accept(secret, candidate, row.sign_count)
        if step is None:
            continue
        # The row count decides: another request may have taken this step, or retired the factor
        # (factor_change.remove), since the row was read.
        unused = UserFactor.objects.filter(id=row.id, sign_count__lt=step, retired_at__isnull=True)
        if unused.update(sign_count=step):
            return row
    return None
