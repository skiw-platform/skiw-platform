"""Passkey ceremonies, the WebAuthn half of an optional second factor (spec D7; plan M3 §3 M3g,
DECISIONS M3g-1). `accounts.auth.factor_change` registers passkeys with these (M3g-1c); M3g-1d
signs in and steps up with them. A passkey is never required; TOTP stays every user's factor.

Relying party: SKIW_WEBAUTHN (config.env.webauthn), the exact app hostname as RP ID (owner Q8
(a)) and one exact origin. User verification is required in the options AND in each verify call
(py_webauthn defaults it to off), attestation is not asked for and not trusted, and the
algorithms are pinned rather than left to the library's default.

The challenge: 32 random bytes, kept in the session with its purpose, its user and a deadline of
SKIW_LOGIN_PENDING_MIN (the browser timeout is the same). One per session; a new ceremony
replaces it. `take_challenge` removes it from the stored row before anything is checked
(SessionStore.take), so a challenge is consumed by a verify that fails as much as one that passes,
and of two parallel verifies only one gets it. A stale save of the session by a parallel request
can still write it back; M3g-1d's conditional update on the factor row (the challenge's issue
time, like TOTP's step) is what makes one challenge sign in at most once.

Sign count: py_webauthn refuses a new count that does not exceed the stored one when either is
non-zero. Both zero is accepted: WebAuthn says 0 means the authenticator keeps no counter (most
synced passkeys), and the challenge is then the only replay guard.

Nothing here logs, and no refusal says why: a credential id, key, challenge or assertion is never
written anywhere but the session and the caller's row (UNI-09). The library's messages carry the
expected origin and are dropped."""

import base64
import binascii
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json_dict
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from accounts.factor_model import CREDENTIAL_ID_MAX
from accounts.session import SessionStore

CHALLENGE = "_skiw_passkey_challenge"
CHALLENGE_BYTES = 32
RP_NAME = "SKIW Assistant"
# EdDSA, then ES256 (platform and security keys), then RS256 (Windows Hello) [A].
ALGORITHMS = [
    COSEAlgorithmIdentifier.EDDSA,
    COSEAlgorithmIdentifier.ECDSA_SHA_256,
    COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
]
MAX_CREDENTIAL_ID = CREDENTIAL_ID_MAX  # the bound user_factor_passkey_shape enforces too
Purpose = Literal["register", "login", "stepup"]


@dataclass(frozen=True)
class Challenge:
    value: bytes
    issued_at: datetime  # M3g-1d stores it on the factor row: one challenge, one sign-in


@dataclass(frozen=True)
class Registered:
    credential_id: bytes
    public_key: bytes  # COSE_Key
    sign_count: int


def _store(request: HttpRequest) -> SessionStore:
    if not isinstance(request.session, SessionStore):
        raise TypeError("passkeys need the accounts session store")
    return request.session


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64url(value: object) -> bytes | None:
    """Strict base64url without padding; None for anything else (UNI-03)."""
    if not isinstance(value, str) or not value.isascii() or value.endswith("="):
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None
    return raw if _b64url(raw) == value else None


def _issue(request: HttpRequest, purpose: Purpose, user_id: uuid.UUID) -> bytes:
    value = secrets.token_bytes(CHALLENGE_BYTES)
    now = timezone.now()
    until = now + timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN)
    _store(request)[CHALLENGE] = {
        "purpose": purpose,
        "user": str(user_id),
        "value": _b64url(value),
        "at": now.isoformat(),
        "until": until.isoformat(),
    }
    return value


def _timeout_ms() -> int:
    return int(settings.SKIW_LOGIN_PENDING_MIN) * 60_000


def take_challenge(request: HttpRequest, purpose: Purpose, user_id: uuid.UUID) -> Challenge | None:
    """The session's challenge if it is for `purpose` and `user_id` and not past its deadline,
    else None. Consumed either way: taken from the stored row before it is checked."""
    record = _store(request).take(CHALLENGE)
    if not isinstance(record, dict) or set(record) != {"purpose", "user", "value", "at", "until"}:
        return None
    if record["purpose"] != purpose or record["user"] != str(user_id):
        return None
    value = _unb64url(record["value"])
    try:
        issued_at = datetime.fromisoformat(record["at"])
        until = datetime.fromisoformat(record["until"])
    except (TypeError, ValueError):
        return None
    if value is None or len(value) != CHALLENGE_BYTES or until.tzinfo is None:
        return None
    if timezone.now() >= until:
        return None
    return Challenge(value, issued_at)


def _descriptors(credential_ids: Sequence[bytes]) -> list[PublicKeyCredentialDescriptor]:
    return [PublicKeyCredentialDescriptor(id=bytes(c)) for c in credential_ids]


def begin_registration(
    request: HttpRequest, user_id: uuid.UUID, email: str, existing: Sequence[bytes]
) -> dict[str, Any]:
    """Creation options for the browser; `existing` (the user's live passkeys) is excluded, so
    one authenticator is not registered twice."""
    rp = settings.SKIW_WEBAUTHN()
    options = generate_registration_options(
        rp_id=rp.rp_id,
        rp_name=RP_NAME,
        user_name=email,
        user_id=user_id.bytes,
        user_display_name=email,
        challenge=_issue(request, "register", user_id),
        timeout=_timeout_ms(),
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=_descriptors(existing),
        supported_pub_key_algs=ALGORITHMS,
    )
    return options_to_json_dict(options)


def begin_assertion(
    request: HttpRequest,
    purpose: Literal["login", "stepup"],
    user_id: uuid.UUID,
    credential_ids: Sequence[bytes],
) -> dict[str, Any]:
    """Request options for the browser, allowing only `credential_ids` (the user's passkeys)."""
    rp = settings.SKIW_WEBAUTHN()
    options = generate_authentication_options(
        rp_id=rp.rp_id,
        challenge=_issue(request, purpose, user_id),
        timeout=_timeout_ms(),
        allow_credentials=_descriptors(credential_ids),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return options_to_json_dict(options)


def _credential_id(credential: object) -> bytes | None:
    """`rawId`, bounded, equal to `id` (UNI-03); None for any other shape."""
    if not isinstance(credential, dict):
        return None
    raw = _unb64url(credential.get("rawId"))
    if raw is None or not 0 < len(raw) <= MAX_CREDENTIAL_ID or credential.get("id") != _b64url(raw):
        return None
    return raw


def asserted_id(credential: object) -> bytes | None:
    """The credential id an assertion names, for M3g-1d's guarded lookup; nothing verified yet."""
    return _credential_id(credential)


def verify_registration(credential: object, challenge: Challenge) -> Registered | None:
    """The new passkey, or None when the response does not verify for this RP, origin and
    challenge with user verification, or its attested id is not the id it was sent under."""
    sent_id = _credential_id(credential)
    if sent_id is None or not isinstance(credential, dict):
        return None
    rp = settings.SKIW_WEBAUTHN()
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.value,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
            require_user_verification=True,
            supported_pub_key_algs=ALGORITHMS,
        )
    except Exception:  # untrusted input; py_webauthn also raises KeyError
        return None
    if verified.credential_id != sent_id:
        return None
    return Registered(sent_id, verified.credential_public_key, verified.sign_count)


def verify_assertion(
    credential: object,
    challenge: Challenge,
    credential_id: bytes,
    public_key: bytes,
    sign_count: int,
) -> int | None:
    """The authenticator's new sign count, or None when the assertion does not verify for this
    RP, origin, challenge and stored key with user verification, names another credential, or
    its count does not exceed `sign_count` while either is non-zero."""
    if _credential_id(credential) != credential_id or not isinstance(credential, dict):
        return None
    rp = settings.SKIW_WEBAUTHN()
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.value,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
            credential_public_key=public_key,
            credential_current_sign_count=sign_count,
            require_user_verification=True,
        )
    except Exception:  # untrusted input; py_webauthn also raises KeyError
        return None
    return verified.new_sign_count
