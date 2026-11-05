"""TOTP codes (spec Flow 5.1 (2); plan M3 §3 M3f): RFC 6238 over RFC 4226 HOTP, HMAC-SHA-1,
6 digits, 30-second steps from the Unix epoch [A: the spec fixes only the ±1 step], a 20-byte
secret, own code tested against the RFCs' vectors (pyotp rejected, plan M3 §2). No database
access: the caller stores the accepted step in `user_factor.sign_count` and passes it back as
`last`, so a step at or below it is refused (replay); the secret is sealed by
blob.seal_factor_secret.
"""

import hmac
import secrets
import time

from django.conf import settings

from accounts.auth.blob import FACTOR_SECRET_SIZE

DIGITS = 6
PERIOD = 30
SECRET_BYTES = FACTOR_SECRET_SIZE


def new_secret() -> bytes:
    return secrets.token_bytes(SECRET_BYTES)


def code(secret: bytes, step: int) -> str:
    """RFC 4226 §5.3: HMAC-SHA-1 of the 8-byte big-endian counter, dynamic truncation, the last
    DIGITS decimal digits."""
    digest = hmac.digest(secret, step.to_bytes(8, "big"), "sha1")
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFF_FFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def step_at(unix_time: float) -> int:
    return int(unix_time // PERIOD)


def accept(secret: bytes, candidate: str, last: int, now: float | None = None) -> int | None:
    """The step `candidate` matches within ±SKIW_TOTP_SKEW_STEPS of `now`, if it is later than
    `last`; None otherwise. Only exactly DIGITS ASCII digits are compared. Every step in the window
    is computed and compared in constant time, whether or not one already matched, so the time
    taken says nothing about which step matched."""
    if len(candidate) != DIGITS or not (candidate.isascii() and candidate.isdigit()):
        return None
    current = step_at(time.time() if now is None else now)
    skew = settings.SKIW_TOTP_SKEW_STEPS
    matched = None
    for step in range(current - skew, current + skew + 1):
        if hmac.compare_digest(code(secret, step), candidate) and step > last:
            matched = step
    return matched
