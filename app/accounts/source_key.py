"""The `django_session` row MAC under `tenant_source_key` (spec §4.1 `django_session`, TEN-11, §8.4
H4; plan M2c, A7). No database access, and it does not import the store, so config.asgi may
import it (the TEN-10 import contract covers accounts.session and accounts.session_model only).

session_data = v<n>:<mac>:<Django-signed blob>, where mac is base64url HMAC-SHA-256 under key
version n over LABEL || field(stored key) || field(expire_date, UTC ISO-8601 to the microsecond)
|| field(blob), each field length-prefixed. The newest version signs; every listed one verifies.
"""

import base64
import functools
import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime

from django.conf import settings

LABEL = b"skiw-session-v1"  # keeps this use of the key apart from row_mac and args_mac
SEALED = re.compile(r"v([1-9][0-9]{0,5}):([A-Za-z0-9_-]{43}):(.+)", re.ASCII | re.DOTALL)
log = logging.getLogger("django.security.SuspiciousSession")


@functools.cache
def require_key() -> tuple[tuple[int, bytes], ...]:
    """The tenant_source_key versions, newest first, read once. Raises (fail closed) when the key
    is missing or malformed; config.asgi calls it before serving."""
    return tuple(settings.SKIW_TENANT_SOURCE_KEYS())


def field(value: str) -> bytes:
    """`value` as UTF-8 behind its 8-byte big-endian length (also accounts.auth.recovery)."""
    data = value.encode()
    return len(data).to_bytes(8, "big") + data


def _mac(key: bytes, stored_key: str, expire_date: datetime, blob: str) -> bytes:
    if expire_date.utcoffset() is None:
        raise ValueError("expire_date must be timezone-aware")
    instant = expire_date.astimezone(UTC).isoformat(timespec="microseconds")
    message = LABEL + field(stored_key) + field(instant) + field(blob)
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=")


def seal(stored_key: str, expire_date: datetime, blob: str) -> str:
    version, key = require_key()[0]
    return f"v{version}:{_mac(key, stored_key, expire_date, blob).decode()}:{blob}"


def unseal(stored_key: str, expire_date: datetime, session_data: str) -> str | None:
    """The blob when the MAC verifies for this row, else None and one warning that carries no
    key, cookie, MAC or session content (UNI-09)."""
    match = SEALED.fullmatch(session_data)
    key = dict(require_key()).get(int(match[1])) if match else None
    if match is None or key is None:
        log.warning("session row rejected: malformed data or an unlisted key version")
        return None
    if not hmac.compare_digest(match[2].encode(), _mac(key, stored_key, expire_date, match[3])):
        log.warning("session row rejected: its MAC does not match")
        return None
    return match[3]
