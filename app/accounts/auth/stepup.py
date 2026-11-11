"""Step-up evidence (spec §4.1 `auth_stepup`, D7, AUTH-09; plan M3 §3 M3h, DECISIONS M3h-1, M3h-2).
No route yet: M3h-3's `verify` calls `record` after a right TOTP code, in the transaction that used
the code; the factor changes (M3h-5, M3h-6) and later consumers call `recent`.

`evidence_mac` is the newest `tenant_source_key` version in RECOVERY_VERSION_BYTES big-endian
bytes, then HMAC-SHA-256 under that version over LABEL, then every other column in a fixed order,
each behind its 8-byte length (source_key.field): id, agency_id, user_id, factor_id, purpose,
verified_at (UTC ISO-8601 to the microsecond, as timestamptz keeps it) and session_key_hash. The
version is in clear, outside the MAC, and picks the key: a changed or removed version verifies
nothing, and a row under an older listed version keeps verifying (as recovery codes, M3f-3a).

Both functions run in the caller's with_agency() transaction and take the user, the agency and
the session from the request's signed session (`_skiw_user`, `_skiw_agency`, the session key),
never from input (TEN-11). Only `record` writes rows (Semgrep auth-stepup-insert-stepup-only), and
only for one of the session user's own TOTP factors: a recovery code is never step-up, and a
recovery row is deleted by raw DELETE, which a step-up naming it would block (FK NO ACTION).

`recent` reads the session's rows for one purpose, no older than SKIW_STEPUP_MAX_AGE_MIN and not
in the future, newest first, and returns the first whose MAC verifies. A row that fails it is
skipped with one warning that carries no row, key, MAC or session material (UNI-09)."""

import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import connection
from django.db.transaction import TransactionManagementError
from django.http import HttpRequest
from django.utils import timezone

from accounts import source_key
from accounts.auth.login import AGENCY, USER
from accounts.factor_model import RECOVERY_VERSION_BYTES, UserFactor
from accounts.session import SessionStore, stored_key
from accounts.stepup_model import AuthStepup

LABEL = b"skiw-stepup-v1"  # apart from the session, recovery and throttle uses of the key
VERSION_BYTES = RECOVERY_VERSION_BYTES  # the same 4-byte prefix as a recovery code's secret_ct
FACTOR_CHANGE = "factor.change"  # add or remove a TOTP, regenerate recovery codes (M3h-5, M3h-6)
# Closed list; a consumer adds its purpose when it is built (outbox.approve M9, drive.write M16).
PURPOSES = frozenset({FACTOR_CHANGE})
FACTOR_KINDS = frozenset({"totp"})  # spec D7: a passkey too, from M3g
log = logging.getLogger("django.security.SuspiciousStepUp")


@dataclass(frozen=True)
class StepUp:
    """Genuine evidence, without its MAC or session hash."""

    id: uuid.UUID
    factor_id: uuid.UUID
    purpose: str
    verified_at: datetime


def _in_transaction() -> None:
    """Fail loudly, not by RLS's empty answer, when called outside the caller's with_agency()."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("step-up runs inside the caller's with_agency()")


def _known(purpose: str) -> None:
    if purpose not in PURPOSES:
        raise ValueError("unknown step-up purpose")


def _signed(request: HttpRequest) -> tuple[uuid.UUID, uuid.UUID, str] | None:
    """The session's user, agency and stored key, or None for a session with no completed login.
    Only login() writes `_skiw_user` and `_skiw_agency`; the key is read after them, because
    loading a missing or forged row (M2c) drops it."""
    session = request.session
    if not isinstance(session, SessionStore):  # the MAC-checked store (M2c), nothing else
        raise TypeError("step-up needs the accounts session store")
    try:
        user, agency = uuid.UUID(session[USER]), uuid.UUID(session[AGENCY])
    except (KeyError, TypeError, ValueError):
        return None
    key = session.session_key
    return None if key is None else (user, agency, stored_key(key))


def _factor(row: AuthStepup) -> uuid.UUID:
    if row.factor_id is None:  # never stored: auth_stepup_factor_named (accounts.0013)
        raise ValueError("a step-up names the factor that proved it")
    return row.factor_id


def _message(row: AuthStepup) -> bytes:
    if row.verified_at.tzinfo is None:  # as source_key._mac: a naive instant is a caller bug
        raise ValueError("a step-up instant is timezone-aware")
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


def _stepup(row: AuthStepup) -> StepUp:
    return StepUp(row.id, _factor(row), row.purpose, row.verified_at)


def record(request: HttpRequest, factor: uuid.UUID, purpose: str) -> StepUp:
    """Writes evidence that the session's user proved `factor` just now, for `purpose`. Call only
    after the factor was verified, in the same transaction. Raises ValueError for an unknown
    purpose, a session with no completed login, or a factor that is not one of the user's own
    TOTP factors (another user's, a recovery code, a passkey before M3g, none)."""
    _known(purpose)
    _in_transaction()
    signed = _signed(request)
    if signed is None:
        raise ValueError("step-up needs a signed-in session")
    user, agency, key_hash = signed
    if not UserFactor.objects.filter(id=factor, user_id=user, kind__in=FACTOR_KINDS).exists():
        raise ValueError("step-up is proved by one of the user's own TOTP factors")
    row = AuthStepup(
        id=uuid.uuid4(),
        agency_id=agency,
        user_id=user,
        factor_id=factor,
        purpose=purpose,
        verified_at=timezone.now(),
        session_key_hash=key_hash,
    )
    row.evidence_mac = evidence(row)
    row.save(force_insert=True)
    return _stepup(row)


def recent(request: HttpRequest, purpose: str) -> StepUp | None:
    """The newest genuine step-up of this session's user, in this session, for `purpose`, at most
    SKIW_STEPUP_MAX_AGE_MIN old (inclusive) and not in the future; None when there is none or the
    session has no completed login. Raises ValueError for an unknown purpose."""
    _known(purpose)
    _in_transaction()
    signed = _signed(request)
    if signed is None:
        return None
    user, _, key_hash = signed  # the agency is the caller's with_agency() (RLS) and in the MAC
    now = timezone.now()
    rows = AuthStepup.objects.filter(
        user_id=user,
        session_key_hash=key_hash,
        purpose=purpose,
        verified_at__gte=now - timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN),
        verified_at__lte=now,
    ).order_by("-verified_at")
    for row in rows:
        if _genuine(row):
            return _stepup(row)
        log.warning("step-up row rejected: its evidence does not verify")
    return None
