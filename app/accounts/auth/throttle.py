"""Pre-login rate limits and the soft-lock, stored in `auth_throttle` (spec §4.1, Flow 5.1,
AUTH-06, T18; plan M3c). M3e's login step calls `blocked` before any lookup or Argon2 verify,
`record_failure` after every failed attempt and `reset_on_success` after a verified password.

Keys are HMAC-SHA-256 under the newest `tenant_source_key` version over a label and the
normalised email (account, lock) or the client IP (ip), so no raw email or IP reaches a row or a
SQL parameter. Every key is derived from the email as typed, whether or not an account has it:
no function here takes or looks up an account, so limits and the lock behave the same for
unknown emails. Account and IP counters use fixed windows of SKIW_AUTH_WINDOW_MIN. The lock
counts consecutive failures in one row (window_start RUN), never windowed, and is reset by
`reset_on_success`; each SKIW_AUTH_LOCK_AFTER-th consecutive failure adds a lock marker row
(window_start = the failure time) that blocks for SKIW_AUTH_LOCK_MIN. Each counter is one upsert.
"""

import hashlib
import hmac
import ipaddress
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from django.conf import settings
from django.db import connection, transaction
from django.http import HttpRequest
from django.utils import timezone

from accounts import source_key
from accounts.auth.blob import normalise_email
from accounts.auth.events import record_event

ACCOUNT, IP, LOCK = b"skiw-throttle-account-v1", b"skiw-throttle-ip-v1", b"skiw-throttle-lock-v1"
FACTOR = b"skiw-throttle-factor-v1"
MALFORMED_IP = "malformed"  # every unparseable client address counts under this one key
RUN = datetime(1970, 1, 1, tzinfo=UTC)  # window_start of the consecutive-failure row
UPSERT = (
    "INSERT INTO auth_throttle (key_hmac, window_start, count) VALUES (%s, %s, 1)"
    " ON CONFLICT (key_hmac, window_start) DO UPDATE SET count = auth_throttle.count + 1"
    " RETURNING count"
)
log = logging.getLogger("django.security.throttle")
Limit = Literal["lock", "account", "ip"]


@dataclass(frozen=True)
class Keys:
    account: bytes
    ip: bytes
    lock: bytes


def _hmac(label: bytes, value: str) -> bytes:
    key = source_key.require_key()[0][1]
    return hmac.new(key, label + value.encode(), hashlib.sha256).digest()


def keys(email: str, ip: str) -> Keys:
    address = normalise_email(email)
    return Keys(_hmac(ACCOUNT, address), _hmac(IP, ip), _hmac(LOCK, address))


def client_ip(request: HttpRequest) -> str:
    """X-Forwarded-For only behind Caddy, which replaces any client-sent value with the one peer
    address (no trusted_proxies, infra/host/caddy/edge.caddy); otherwise REMOTE_ADDR."""
    header = "HTTP_X_FORWARDED_FOR" if settings.SKIW_BEHIND_CADDY else "REMOTE_ADDR"
    try:
        return str(ipaddress.ip_address(request.META.get(header, "").strip()))
    except ValueError:
        return MALFORMED_IP


def _window(now: datetime) -> datetime:
    size = settings.SKIW_AUTH_WINDOW_MIN * 60
    return datetime.fromtimestamp(int(now.timestamp()) // size * size, UTC)


def blocked(email: str, ip: str) -> Limit | None:
    """Which limit refuses an attempt now, if any; M3e answers every one with the same 429."""
    k, now = keys(email, ip), timezone.now()
    lock_since = now - timedelta(minutes=settings.SKIW_AUTH_LOCK_MIN)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT key_hmac, count FROM auth_throttle"
            " WHERE key_hmac IN (%s, %s) AND window_start = %s"
            " OR key_hmac = %s AND window_start > %s",  # a lock marker newer than LOCK_MIN
            [k.account, k.ip, _window(now), k.lock, lock_since],
        )
        counts = {bytes(key): count for key, count in cursor.fetchall()}
    if k.lock in counts:
        return "lock"
    if counts.get(k.account, 0) >= settings.SKIW_AUTH_FAILS_PER_ACCOUNT:
        return "account"
    if counts.get(k.ip, 0) >= settings.SKIW_AUTH_FAILS_PER_IP:
        return "ip"
    return None


def record_failure(email: str, ip: str) -> None:
    k, now = keys(email, ip), timezone.now()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(UPSERT, [k.account, _window(now)])
        cursor.execute(UPSERT, [k.ip, _window(now)])
        cursor.execute(UPSERT, [k.lock, RUN])
        (consecutive,) = cursor.fetchone()
        locked = consecutive % settings.SKIW_AUTH_LOCK_AFTER == 0
        if locked:
            cursor.execute(UPSERT, [k.lock, now])  # concurrent locks at one instant share a row
            record_event("account.locked", k.account, k.ip, {"consecutive": consecutive})
    if locked:  # after the commit, so a rolled-back lock logs nothing
        log.warning("account soft-locked after %d consecutive failed logins", consecutive)


def reset_on_success(email: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE auth_throttle SET count = 0 WHERE key_hmac = %s AND window_start = %s",
            [_hmac(LOCK, normalise_email(email)), RUN],
        )


def factor_blocked(user: uuid.UUID) -> bool:
    """True once `user` has had SKIW_AUTH_FAILS_PER_ACCOUNT wrong second-factor codes in this
    window (AUTH-06). The user is known here (a pending session, after the password), so the
    count is per user, not per email or IP: a password holder guessing from many addresses is
    still counted. Windowed like the account counter, never reset by a success."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count FROM auth_throttle WHERE key_hmac = %s AND window_start = %s",
            [_hmac(FACTOR, str(user)), _window(timezone.now())],
        )
        row = cursor.fetchone()
    return row is not None and row[0] >= settings.SKIW_AUTH_FAILS_PER_ACCOUNT


def record_factor_failure(user: uuid.UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute(UPSERT, [_hmac(FACTOR, str(user)), _window(timezone.now())])
