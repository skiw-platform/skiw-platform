"""A signed-in user's own factors (spec D7, AUTH-07, AUTH-09; plan M3 §3 M3h; owner decision
2026-11-06 item 4; DECISIONS M3h-5): the list, and adding a TOTP behind step-up. Removing a TOTP
and regenerating recovery codes are M3h-6.

Adding is two calls, as at enrolment, with a session key of its own (ADD_TOTP, never enrolment's
`_skiw_pending_totp`), so the two flows cannot be mixed. `begin` needs a recent `factor.change`
step-up of this session and keeps a new secret in the session, sealed to a new factor id, the user
and the agency (`factors.seal_new`). `confirm` takes the first code from the new secret through
`second_factor.counted` on the user's one budget, with `feeds_lock=False`: a user typing the code
of a secret they just made is not guessing anyone's factor (as at enrolment, DECISIONS M3f-3c-1b),
but the budget and the lock still hold. In the check's one with_agency() transaction, in the order
of every credential change (DECISIONS M3h-4): `revoke.hold`, `stepup.recent`, the factor row with
`sign_count` = the accepted step (so the confirming code cannot sign in again), the pending secret
dropped, a user-wide marker (AUTH-07: every other session ends) and `login.reissue` for this one.
A refusal inside the check (revoked, no step-up, a secret that does not open) is not a guess: the
attempt is given back. No TOTP count cap [A]. No secret or code is logged (UNI-09)."""

import uuid
from dataclasses import dataclass
from typing import Literal

from django.http import HttpRequest

from accounts.auth import blob, factors, second_factor, totp
from accounts.auth.login import reissue
from accounts.auth.revoke import hold, mark
from accounts.auth.stepup import FACTOR_CHANGE, recent
from accounts.auth.transactions import require_open
from accounts.auth.wrapper import Signed
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser

ADD_TOTP = "_skiw_add_totp"  # {"id": factor id, "ct": the sealed secret, base64}
Refused = Literal["no-pending", "invalid", "stepup-required", "signed-out", "limited", "wrong_code"]


@dataclass(frozen=True)
class Listing:
    totp: list[uuid.UUID]
    recovery_left: int


def listing(signed: Signed) -> Listing:
    """The session user's TOTP factor ids and unused recovery codes, in the wrapper's
    with_agency(); no secret, nothing else about a factor."""
    require_open("the factor list")
    own = UserFactor.objects.filter(user_id=signed.user_id)
    ids = own.filter(kind="totp").order_by("id").values_list("id", flat=True)
    return Listing(list(ids), own.filter(kind="recovery").count())


def begin(request: HttpRequest, signed: Signed) -> factors.Setup | Literal["stepup-required"]:
    """In the wrapper's with_agency(): a new secret to add, replacing an unconfirmed one."""
    if recent(request, FACTOR_CHANGE) is None:
        return "stepup-required"
    return factors.seal_new(request, ADD_TOTP, AppUser.objects.get(id=signed.user_id))


def confirm(request: HttpRequest, signed: Signed, candidate: str) -> uuid.UUID | Refused:
    """The new factor's id once `candidate` is the begun secret's current code; outside any
    transaction (the factor counters refuse one). "no-pending": nothing begun, nothing counted.
    "invalid": not six ASCII digits, nothing counted. "wrong_code": counted, the lock run
    unchanged."""
    stored = factors.stored_secret(request, ADD_TOTP)
    if stored is None:
        return "no-pending"
    if not second_factor.is_totp(candidate):
        return "invalid"
    factor, sealed = stored
    refused: list[Refused] = []

    def check(user: AppUser) -> bool:
        if not hold(signed, str(request.session.session_key)):
            request.session.flush()
            refused.append("signed-out")
            return True  # not a guess: the attempt is given back
        if recent(request, FACTOR_CHANGE) is None:
            refused.append("stepup-required")
            return True
        secret = blob.open_factor_secret(sealed, factor, user.id, user.agency_id)
        if secret is None:
            refused.append("no-pending")
            return True
        step = totp.accept(secret, candidate, 0)
        if step is None:
            return False
        UserFactor.objects.create(
            id=factor,
            agency_id=user.agency_id,
            user_id=user.id,
            kind="totp",
            secret_ct=sealed,
            sign_count=step,
        )
        request.session.pop(ADD_TOTP)
        mark(signed.agency_id, signed.user_id, None)  # AUTH-07: every other session ends
        reissue(request, signed)
        return True

    result = second_factor.counted(
        request, signed.user_id, signed.agency_id, check, feeds_lock=False
    )
    if result == "unavailable":
        return "signed-out"  # the user stopped being `active` after the wrapper
    if result != "ok":
        return result
    return refused[0] if refused else factor
