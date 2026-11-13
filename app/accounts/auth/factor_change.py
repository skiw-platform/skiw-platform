"""A signed-in user's own factors (spec D7, AUTH-07, AUTH-09; plan M3 §3 M3h, M3g; owner decision
2026-11-06 item 4; DECISIONS M3h-5, M3h-6, M3g-1c): the list, adding and removing a TOTP or a
passkey and regenerating the recovery codes, each change behind a `factor.change` step-up of this
session.

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
attempt is given back. No TOTP count cap [A].

Adding a passkey is two calls too: `begin_passkey` (step-up checked) issues the registration
options, the user's passkeys in use excluded, with a `register` challenge for this user in the
session; `confirm_passkey` takes it (outside any transaction: `SessionStore.take` refuses one),
verifies the registration, then in one with_agency() transaction runs the same `hold`, `recent`,
row, marker and `reissue` as a TOTP. The row holds the verified credential id, public key and
count, and `lookup_blob_ct` sealed to the user and agency with the credential id as AAD, so
`lookup.lookup_credential` resolves it. A failed take or verify and a credential id already
registered (to anyone, in use or retired: the global unique key) are one refusal, `refused`, with
nothing logged; nothing is counted, since the challenge is spent either way and a registration
guesses nothing. A passkey is optional: it never replaces a TOTP or changes what sign-in asks.

Removing a TOTP or a passkey retires it: the row stays, so step-up evidence naming it still
verifies (the FK is NO ACTION, DECISIONS M3h-1), with `retired_at` set and the secret, public key
and lookup blob cleared; every lookup skips a retired row. A retired passkey keeps its credential
id, so that id cannot be registered again. The user's last TOTP is never removed (spec D7: TOTP is
required), and a passkey never counts in its place: a passkey goes only while a TOTP stays.
Replacing a TOTP is add, step up again, remove. Remove and regenerate run in the wrapper's
with_agency() in the same order as every credential change. No secret or code is logged (UNI-09)."""

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.db.models.functions import Now
from django.http import HttpRequest

from accounts.auth import blob, factors, passkey, recovery, second_factor, totp
from accounts.auth.login import reissue
from accounts.auth.revoke import hold, mark
from accounts.auth.stepup import FACTOR_CHANGE, recent
from accounts.auth.transactions import require_open
from accounts.auth.wrapper import Signed
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

ADD_TOTP = "_skiw_add_totp"  # {"id": factor id, "ct": the sealed secret, base64}
Refused = Literal["no-pending", "invalid", "stepup-required", "signed-out", "limited", "wrong_code"]
Unchanged = Literal["stepup-required", "signed-out"]
Kind = Literal["totp", "passkey"]
CREDENTIAL_KEY = "user_factor_credential_id_key"  # spec §4.1 uq(credential_id), global


@dataclass(frozen=True)
class Listing:
    totp: list[uuid.UUID]
    passkey: list[uuid.UUID]
    recovery_left: int


def listing(signed: Signed) -> Listing:
    """The session user's TOTP and passkey factor ids and unused recovery codes, in the wrapper's
    with_agency(); no secret, key or credential id, nothing else about a factor."""
    require_open("the factor list")
    own = UserFactor.objects.filter(user_id=signed.user_id)
    return Listing(_totps(signed), _passkeys(signed), own.filter(kind="recovery").count())


def _in_use(signed: Signed, kind: Kind) -> QuerySet[UserFactor]:
    """The session user's `kind` factors that are not retired."""
    return UserFactor.objects.filter(user_id=signed.user_id, kind=kind, retired_at__isnull=True)


def _totps(signed: Signed) -> list[uuid.UUID]:
    return list(_in_use(signed, "totp").order_by("id").values_list("id", flat=True))


def _passkeys(signed: Signed) -> list[uuid.UUID]:
    return list(_in_use(signed, "passkey").order_by("id").values_list("id", flat=True))


def _changing(request: HttpRequest, signed: Signed) -> Unchanged | None:
    """`hold` then `recent`, first in a change made in the wrapper's with_agency(); a session
    `hold` refuses is flushed."""
    if not hold(signed, str(request.session.session_key)):
        request.session.flush()
        return "signed-out"
    return "stepup-required" if recent(request, FACTOR_CHANGE) is None else None


def _changed(request: HttpRequest, signed: Signed) -> None:
    mark(signed.agency_id, signed.user_id, None)  # AUTH-07: every other session ends
    reissue(request, signed)


def remove(
    request: HttpRequest, signed: Signed, factor: uuid.UUID, kind: Kind = "totp"
) -> Literal["removed", "not-found", "last-factor"] | Unchanged:
    """Retires `factor`, one of the session user's `kind` factors that is not retired, unless no
    TOTP would be left. "not-found": anything else (another user's, another kind, a retired one)."""
    refused = _changing(request, signed)
    if refused is not None:
        return refused
    totps = _totps(signed)  # after the lock: a parallel remove has committed or waits
    if factor not in (totps if kind == "totp" else _passkeys(signed)):
        return "not-found"
    if not set(totps) - {factor}:  # TOTP is required (spec D7); a passkey never stands in for it
        return "last-factor"
    UserFactor.objects.filter(id=factor).update(
        retired_at=Now(), secret_ct=None, public_key=None, lookup_blob_ct=None
    )
    _changed(request, signed)
    return "removed"


def regenerate(request: HttpRequest, signed: Signed) -> list[str] | Unchanged:
    """Replaces the session user's recovery codes with new ones, returned to be shown once."""
    refused = _changing(request, signed)
    if refused is not None:
        return refused
    codes = recovery.generate(signed.agency_id, signed.user_id)
    _changed(request, signed)
    return codes


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
        unchanged = _changing(request, signed)
        if unchanged is not None:
            refused.append(unchanged)
            return True  # not a guess: the attempt is given back
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
        _changed(request, signed)
        return True

    result = second_factor.counted(
        request, signed.user_id, signed.agency_id, check, feeds_lock=False
    )
    if result == "unavailable":
        return "signed-out"  # the user stopped being `active` after the wrapper
    if result != "ok":
        return result
    return refused[0] if refused else factor


def begin_passkey(
    request: HttpRequest, signed: Signed
) -> dict[str, Any] | Literal["stepup-required"]:
    """In the wrapper's with_agency(): registration options for a new passkey, the user's passkeys
    in use excluded, and a `register` challenge in the session, replacing any other challenge."""
    if recent(request, FACTOR_CHANGE) is None:
        return "stepup-required"
    user = AppUser.objects.get(id=signed.user_id)
    own = _in_use(signed, "passkey").values_list("credential_id", flat=True)
    return passkey.begin_registration(request, user.id, user.email, [bytes(c) for c in own if c])


def confirm_passkey(
    request: HttpRequest, signed: Signed, credential: dict[str, Any]
) -> uuid.UUID | Literal["refused"] | Unchanged:
    """The new passkey's factor id once `credential` verifies against this session's `register`
    challenge for this user; outside any transaction. "refused": no such challenge (none, another
    purpose or user, past its deadline, taken already), a registration that does not verify, or a
    credential id registered before. The challenge is spent whatever the outcome."""
    challenge = passkey.take_challenge(request, "register", signed.user_id)
    registered = None if challenge is None else passkey.verify_registration(credential, challenge)
    if registered is None:
        return "refused"
    with with_agency(signed.agency_id):
        unchanged = _changing(request, signed)
        if unchanged is not None:
            return unchanged
        factor = uuid.uuid4()
        if not _stored(signed, factor, registered):
            return "refused"
        _changed(request, signed)
    return factor


def _stored(signed: Signed, factor: uuid.UUID, registered: passkey.Registered) -> bool:
    """Inserts the passkey row; False when its credential id is registered already (the global
    unique key, which also sees other agencies' and retired rows). The savepoint keeps the
    transaction usable, and the clash, whose detail echoes the id, is neither logged nor told."""
    user, agency, credential = signed.user_id, signed.agency_id, registered.credential_id
    try:
        with transaction.atomic():
            UserFactor.objects.create(
                id=factor,
                agency_id=agency,
                user_id=user,
                kind="passkey",
                credential_id=credential,
                public_key=registered.public_key,
                sign_count=registered.sign_count,
                lookup_blob_ct=blob.seal_credential(user, agency, credential),
            )
    except IntegrityError as clash:
        # psycopg's diagnostics, read without importing psycopg (the TEN-10 contract keeps config,
        # which mounts these views, clear of it)
        diag = getattr(clash.__cause__, "diag", None)
        if getattr(diag, "constraint_name", None) != CREDENTIAL_KEY:
            raise
        return False
    return True
