"""Users with a password and readers of the login records, for the password-step tests (M3e-2).
skiw_app cannot delete users, throttle rows or events, so each test uses fresh emails and IPs. The
users stay, but `unseal()` clears the blobs a test sealed: `accounts.0008` reversed puts back the
222-byte check, which a kept 220-byte blob would refuse (the tenancy reversal test runs it)."""

import ipaddress
import secrets
import uuid

from django.db import connection
from django.utils import timezone

from accounts.auth import blob
from accounts.auth.blob import LoginRecord
from accounts.auth.passwords import hash_password
from accounts.auth.throttle import FACTOR, RUN, _hmac, _window, keys
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import committed_user

PASSWORD = "correct horse battery staple"
FAILING = ["known-wrong", "unknown", "invited", "disabled-right"]
SEALED: list[AppUser] = []


def random_ip() -> str:
    return str(ipaddress.IPv6Address(secrets.token_bytes(16)))


def unknown() -> str:
    return f"{uuid.uuid4().hex}@example.test"


def enrolled(status: str = "active") -> tuple[AppUser, str]:
    """A user with a password, as M3e-3's enrolment will leave one; the email as it is stored."""
    user = committed_user(status=status)
    record = LoginRecord(user.id, user.agency_id, hash_password(PASSWORD))
    with with_agency(user.agency_id):
        sealed = blob.seal_login(record, user.email)
        AppUser.objects.filter(id=user.id).update(login_blob_ct=sealed)
    SEALED.append(user)
    return user, user.email


def unseal() -> None:
    while SEALED:
        user = SEALED.pop()
        with with_agency(user.agency_id):
            AppUser.objects.filter(id=user.id).update(login_blob_ct=None)


def failing(case: str) -> tuple[str, str]:
    """An email and password that must fail, for each case of FAILING (AUTH-05)."""
    if case == "known-wrong":
        return enrolled()[1], "wrong"
    if case == "unknown":
        return unknown(), PASSWORD
    if case == "invited":  # a user with no password yet
        return committed_user(status="invited").email, PASSWORD
    return enrolled(status="disabled")[1], PASSWORD


def failures(email: str, ip: str) -> int:
    """`login.failed` events for this email and IP, each with no details."""
    k = keys(email, ip)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM security_event WHERE kind = 'login.failed'"
            " AND email_hmac = %s AND ip_hmac = %s AND details_json::text = '{}'",
            [k.account, k.ip],
        )
        return int(cursor.fetchone()[0])


def consecutive(email: str) -> int:
    """The account's consecutive-failure counter, the one the soft lock counts."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(sum(count), 0) FROM auth_throttle"
            " WHERE key_hmac = %s AND window_start = %s",
            [keys(email, "").lock, RUN],
        )
        return int(cursor.fetchone()[0])


def factor_count(user: uuid.UUID) -> int:
    """Second-factor attempts counted for `user` in the current window (0 when none)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count FROM auth_throttle WHERE key_hmac = %s AND window_start = %s",
            [_hmac(FACTOR, str(user)), _window(timezone.now())],
        )
        row = cursor.fetchone()
    return 0 if row is None else int(row[0])
