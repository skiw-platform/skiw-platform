"""A passkey as the second factor of a sign-in (spec D7, Flow 5.1 (2), AUTH-05, AUTH-06; plan M3
§3 M3g; DECISIONS M3g-1d-1). `match` is the whole check of an assertion, kept apart from the
sign-in flow so a step-up can use it the same way (M3g-1d-2).

`begin_login` issues assertion options only for a pending login (not an enrolment's) whose user is
still `active` and has a passkey in use, allowing exactly those credential ids; otherwise it starts
nothing. `finish_login` takes the session's `login` challenge (outside any transaction:
SessionStore.take refuses one; consumed whatever follows), then runs the check through
`second_factor.counted`, the one copy of the count, fault and lock rules: the attempt is counted
before anything is looked up, so the lookup (and its `passkey.lookup` event) sits behind the same
per-user budget and ten-in-a-row lock as TOTP and recovery codes, and a wrong assertion is a wrong
code on that budget and run.

`discover`, after reservation and outside with_agency(): no challenge, an id outside 1..1023
bytes (checked before any lookup), or an owner (`lookup.lookup_credential`) other than this user
AND agency are refused. The lookup event commits before tenant work, even if that work faults.
An empty `allowCredentials` admits any discoverable credential, so this is the real guard.
`match`, inside counted's with_agency(): no passkey row
in use, or an assertion that does not verify, are all one refusal. A decoy, an unknown or retired
id and a wrong key therefore count and answer alike. Then ONE conditional update sets `sign_count`
and `last_challenge_at` only where the row is still in use, the stored count is below the new one
(both zero: still zero) and `last_challenge_at` is NULL or strictly before the challenge's issue
time. Its row count decides: a challenge put back by a stale session save, or a replay of the same
assertion, has an issue time equal to the stored one and updates nothing (PR 154 R1 P2 #2). Of two
challenges, the earlier one is refused once a later one was used, even from another session: that
fails closed. Nothing is logged."""

import uuid
from typing import Any, Literal

from django.db.models import Q
from django.http import HttpRequest

from accounts.auth import factors, passkey, second_factor
from accounts.auth.factors import Failure
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.auth.second_factor import Passed
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

NoPasskey = Literal["no-passkey"]


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
    challenge = passkey.take_challenge(request, "login", state.user_id)

    def check(user: AppUser) -> bool:
        return match(user, credential, challenge) is not None

    result = second_factor.counted(
        request,
        state.user_id,
        state.agency_id,
        check,
        feeds_lock=True,
        precheck=lambda: discover(state.user_id, state.agency_id, credential, challenge),
    )
    if result != "ok":
        return result
    factors.clear_pending(request)
    return Passed(state.user_id, state.agency_id, "passkey")


def discover(
    user_id: uuid.UUID,
    agency_id: uuid.UUID,
    credential: object,
    challenge: passkey.Challenge | None,
) -> bool:
    """Compare both sealed owner IDs outside a tenant transaction, after reservation."""
    credential_id = passkey.asserted_id(credential)
    return (
        challenge is not None
        and credential_id is not None
        and lookup_credential(credential_id) == CredentialOwner(user_id, agency_id)
    )


def match(
    user: AppUser, credential: object, challenge: passkey.Challenge | None
) -> UserFactor | None:
    """The user's passkey that `credential` proves for `challenge`, its count and challenge time
    now stored, or None. Call inside `counted`, after its `discover` precheck passed."""
    credential_id = passkey.asserted_id(credential)
    if challenge is None or credential_id is None:
        return None
    in_use = UserFactor.objects.filter(kind="passkey", retired_at__isnull=True)
    row = in_use.filter(user_id=user.id, credential_id=credential_id).first()
    if row is None or row.public_key is None:
        return None
    count = passkey.verify_assertion(
        credential, challenge, credential_id, bytes(row.public_key), row.sign_count
    )
    if count is None:
        return None
    fresh = Q(last_challenge_at__isnull=True) | Q(last_challenge_at__lt=challenge.issued_at)
    rising = Q(sign_count__lt=count) if count else Q(sign_count=0)
    used = in_use.filter(fresh, rising, id=row.id).update(
        sign_count=count, last_challenge_at=challenge.issued_at
    )
    return row if used else None
