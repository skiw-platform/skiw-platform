"""Step-up evidence MAC (spec §4.1 `auth_stepup`, D7, AUTH-09; plan M3 §3 M3h, DECISIONS M3h-1,
M3h-2). M3h-2a is the MAC only; `record` and `recent` (M3h-2b) and `verify` (M3h-3) build on it.

`evidence_mac` is the newest `tenant_source_key` version in RECOVERY_VERSION_BYTES big-endian
bytes, then HMAC-SHA-256 under that version over LABEL, then every other column in a fixed order,
each behind its 8-byte length (source_key.field): id, agency_id, user_id, factor_id, purpose,
verified_at (UTC ISO-8601 to the microsecond, as timestamptz keeps it) and session_key_hash. The
version is in clear, outside the MAC, and picks the key: a changed or removed version verifies
nothing, and a row under an older listed version keeps verifying (as recovery codes, M3f-3a)."""

import hashlib
import hmac
import uuid
from datetime import UTC

from accounts import source_key
from accounts.factor_model import RECOVERY_VERSION_BYTES
from accounts.stepup_model import AuthStepup

LABEL = b"skiw-stepup-v1"  # apart from the session, recovery and throttle uses of the key
VERSION_BYTES = RECOVERY_VERSION_BYTES  # the same 4-byte prefix as a recovery code's secret_ct
FACTOR_CHANGE = "factor.change"  # add or remove a TOTP, regenerate recovery codes (M3h-5, M3h-6)
# Closed list; a consumer adds its purpose when it is built (outbox.approve M9, drive.write M16).
PURPOSES = frozenset({FACTOR_CHANGE})


def _factor(row: AuthStepup) -> uuid.UUID:
    if row.factor_id is None:  # never stored: auth_stepup_factor_named (accounts.0013)
        raise ValueError("a step-up names the factor that proved it")
    return row.factor_id


def _message(row: AuthStepup) -> bytes:
    instant = row.verified_at.astimezone(UTC).isoformat(timespec="microseconds")
    values = (row.id, row.agency_id, row.user_id, _factor(row), row.purpose, instant)
    message = LABEL + b"".join(source_key.field(str(value)) for value in values)
    return message + source_key.field(row.session_key_hash)


def _mac(key: bytes, row: AuthStepup) -> bytes:
    return hmac.new(key, _message(row), hashlib.sha256).digest()


def evidence(row: AuthStepup) -> bytes:
    """The `evidence_mac` of `row` under the newest key version."""
    version, key = source_key.require_key()[0]
    return version.to_bytes(VERSION_BYTES, "big") + _mac(key, row)


def _genuine(row: AuthStepup) -> bool:
    """True when `evidence_mac` verifies under the listed version its prefix names."""
    mac = bytes(row.evidence_mac)
    key = dict(source_key.require_key()).get(int.from_bytes(mac[:VERSION_BYTES], "big"))
    return key is not None and hmac.compare_digest(mac[VERSION_BYTES:], _mac(key, row))
