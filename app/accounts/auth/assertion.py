"""Passkey assertions: the second factor of a sign-in and the proof of a step-up (spec D7, Flow
5.1 (2), AUTH-05, AUTH-06, AUTH-09; plan M3 §3 M3g; DECISIONS M3g-1d-1, M3g-1d-2).

`counted_assertion` is the one supported way to check an assertion (PR 157 R2 P2): sign-in
(`finish_login`) and step-up (`stepup.verify_passkey`) both call it, and nothing else verifies
one. Outside any transaction (SessionStore.take and the factor counters refuse one), in order:
1. the session's challenge for the purpose (`login` or `stepup`) and user is taken, so it is spent
   whatever follows;
2. `second_factor.counted` reserves the attempt (budget and lock, `feeds_lock=True`, the one copy
   of the count, fault and lock rules); over the budget or locked, nothing is looked up;
3. `_discover`, its precheck, in autocommit: no challenge, an id outside 1..1023 bytes (checked
   before any lookup) or an owner (`lookup.lookup_credential`) other than this user AND agency
   is a refusal; the lookup's `passkey.lookup` event commits before any tenant work, even if that
   work faults. An empty `allowCredentials` admits any discoverable credential, so this is the
   real guard. A pass is a `Discovered`, which only `_discover` can make;
4. `_verify`, inside counted's with_agency(), takes that `Discovered` and nothing else: no passkey
   row of the user in use, or an assertion that does not verify, are the same refusal. A decoy,
   an unknown or retired id and a wrong key therefore count and answer alike. Then ONE
   conditional update sets `sign_count` and `last_challenge_at` only where the row is still in
   use, the stored count is below the new one (both zero: still zero) and `last_challenge_at` is
   NULL or strictly before the challenge's issue time. Its row count decides: a challenge put
   back by a stale session save, or a replay, has an issue time equal to the stored one and
   updates nothing (PR 154 R1 P2 #2). Of two challenges, the earlier one is refused once a later
   one was used, even from another session: that fails closed;
5. `then(row)`, in the same transaction (step-up writes its evidence there).

`begin_login` issues assertion options only for a pending login (not an enrolment's) whose user is
still `active` and has a passkey in use, allowing exactly those credential ids; otherwise it starts
nothing. Nothing is logged."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from django.db.models import Q
from django.http import HttpRequest

from accounts.auth import factors, passkey, second_factor
from accounts.auth.factors import Failure
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.auth.second_factor import Counted, Passed
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

NoPasskey = Literal["no-passkey"]
_MINTED = object()  # only _discover holds it


@dataclass(frozen=True)
class Discovered:
    """A discovery that passed: the credential's sealed owner is this user and agency. Made only
    by `_discover`; any other construction raises, so `_verify` cannot run without one."""

    user_id: uuid.UUID
    agency_id: uuid.UUID
    credential_id: bytes
    challenge: passkey.Challenge
    seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.seal is not _MINTED:
            raise TypeError("an assertion is verified only after its discovery passed")


def credential_ids(user_id: uuid.UUID) -> list[bytes]:
    """The user's passkeys in use, in the caller's with_agency()."""
    rows = UserFactor.objects.filter(user_id=user_id, kind="passkey", retired_at__isnull=True)
    return [bytes(c) for c in rows.order_by("id").values_list("credential_id", flat=True) if c]


def begin_login(request: HttpRequest) -> dict[str, Any] | NoPasskey | Literal["unavailable"]:
    """Assertion options and a `login` challenge for the pending user's passkeys in use.
    "unavailable": no pending login (as `second_factor.attempt`) or the user is not `active`.
    "no-passkey": the user has none in use; no challenge is issued. Nothing is counted."""
    state = factors.pending(request)
    if state is None or state.enrol:
        return "unavailable"
    with with_agency(state.agency_id):
        if not AppUser.objects.filter(id=state.user_id, status="active").exists():
            return "unavailable"
        ids = credential_ids(state.user_id)
    if not ids:
        return "no-passkey"
    return passkey.begin_assertion(request, "login", state.user_id, ids)


def finish_login(request: HttpRequest, credential: object) -> Passed | Failure:
    """As `second_factor.attempt`, with `credential` (the browser's assertion JSON) in place of a
    code: "unavailable" (nothing counted), "limited" (nothing checked) or "wrong_code" (counted,
    feeds the lock). The challenge is spent in every case after the pending check."""
    state = factors.pending(request)
    if state is None or state.enrol:
        return "unavailable"
    result = counted_assertion(request, "login", state.user_id, state.agency_id, credential)
    if result != "ok":
        return result
    factors.clear_pending(request)
    return Passed(state.user_id, state.agency_id, "passkey")


def counted_assertion(
    request: HttpRequest,
    purpose: Literal["login", "stepup"],
    user_id: uuid.UUID,
    agency_id: uuid.UUID,
    credential: object,
    then: Callable[[UserFactor], object] | None = None,
) -> Counted:
    """Checks `credential` for the session's `purpose` challenge as `user_id` in `agency_id`
    (from the server session, never input: TEN-11), in the order of the module docstring, and
    on success calls `then` with the passkey row inside the transaction that used it. The
    answers are `second_factor.counted`'s."""
    challenge = passkey.take_challenge(request, purpose, user_id)
    found: list[Discovered] = []

    def discovered() -> bool:
        result = _discover(user_id, agency_id, credential, challenge)
        found[:] = [] if result is None else [result]
        return result is not None

    def verified(user: AppUser) -> bool:
        row = _verify(user, credential, found[0]) if found else None
        if row is not None and then is not None:
            then(row)
        return row is not None

    return second_factor.counted(
        request, user_id, agency_id, verified, feeds_lock=True, precheck=discovered
    )


def _discover(
    user_id: uuid.UUID,
    agency_id: uuid.UUID,
    credential: object,
    challenge: passkey.Challenge | None,
) -> Discovered | None:
    """Both sealed owner IDs compared outside a tenant transaction, after reservation."""
    credential_id = passkey.asserted_id(credential)
    if challenge is None or credential_id is None:
        return None
    if lookup_credential(credential_id) != CredentialOwner(user_id, agency_id):
        return None
    return Discovered(user_id, agency_id, credential_id, challenge, _MINTED)


def _verify(user: AppUser, credential: object, found: Discovered) -> UserFactor | None:
    """The user's passkey that `credential` proves for the discovered challenge, its count and
    challenge time now stored, or None. Inside counted's with_agency()."""
    if (found.user_id, found.agency_id) != (user.id, user.agency_id):
        return None
    in_use = UserFactor.objects.filter(kind="passkey", retired_at__isnull=True)
    row = in_use.filter(user_id=user.id, credential_id=found.credential_id).first()
    if row is None or row.public_key is None:
        return None
    challenge = found.challenge
    count = passkey.verify_assertion(
        credential, challenge, found.credential_id, bytes(row.public_key), row.sign_count
    )
    if count is None:
        return None
    fresh = Q(last_challenge_at__isnull=True) | Q(last_challenge_at__lt=challenge.issued_at)
    rising = Q(sign_count__lt=count) if count else Q(sign_count=0)
    used = in_use.filter(fresh, rising, id=row.id).update(
        sign_count=count, last_challenge_at=challenge.issued_at
    )
    return row if used else None
