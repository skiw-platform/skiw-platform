"""The password step of login (spec Flow 5.1 (0)-(1), AUTH-05, AUTH-06; plan M3 §3 M3e). Known and
unknown emails do the same work until the password is right, so neither the answer nor the work
tells an account from no account (plan Risk 2):

1. `throttle.blocked` for the account, IP and lock keys: limited, with no lookup and no Argon2;
2. `lookup.lookup_login`: the row's blob or a decoy of the same length, and its security_event;
3. `blob.open_login`: a decoy, or a blob for another email, opens to None;
4. one Argon2 verify: the record's hash, or `dummy_verify` for None;
5. any failure: the three throttle counters and one `login.failed` event, whatever the reason;
6. a verified password: `status` is read in `with_agency()` (not `active` is a failure as in 5,
   plan [A]), and the lock counter is reset. A hash made with older Argon2 parameters is re-made
   with the current ones and re-sealed in that same transaction, so after a parameter change a
   stored hash and the dummy cost the same again once its user signs in (PR 112 R1 P3 #1).

All of it runs outside `with_agency()` apart from the status read: no tenant is known yet, and the
throttle rows and events are global. `start_pending` then gives the browser a new session that
holds only the pending state the second factor (M3f) completes; `accounts.auth.login.login()`
writes the signed-in keys after that factor."""

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import rotate_token
from django.utils import timezone

from accounts.auth import blob, passwords, throttle
from accounts.auth.events import record_event
from accounts.auth.login import AGENCY, USER
from accounts.auth.lookup import lookup_login
from accounts.auth.revoke import mark
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

PENDING_USER = "_skiw_pending_user"
PENDING_AGENCY = "_skiw_pending_agency"
PENDING_UNTIL = "_skiw_pending_until"  # UTC ISO-8601; the second factor must come before it
# Set only by the enrolment route: this pending user has no second factor yet and may add a first
# one (M3f, M3g), which makes them `active`. A login's pending state never carries it.
PENDING_ENROL = "_skiw_pending_enrol"


@dataclass(frozen=True)
class Verified:
    user_id: uuid.UUID
    agency_id: uuid.UUID


def attempt(email: str, password: str, ip: str) -> Verified | Literal["limited", "failed"]:
    if throttle.blocked(email, ip) is not None:
        return "limited"
    sealed = lookup_login(email)
    record = blob.open_login(sealed, email)
    if record is None:
        passwords.dummy_verify(password)
        verified = False
    else:
        verified = passwords.verify(record.password_hash, password)
    if record is not None and verified:
        with with_agency(record.agency_id):
            verified = AppUser.objects.filter(id=record.user_id, status="active").exists()
            if verified and passwords.needs_rehash(record.password_hash):
                _rehash(record, email, password, sealed)
    if record is None or not verified:
        throttle.record_failure(email, ip)
        keys = throttle.keys(email, ip)
        record_event("login.failed", keys.account, keys.ip, {})
        return "failed"
    throttle.reset_on_success(email)
    return Verified(record.user_id, record.agency_id)


def _rehash(record: blob.LoginRecord, email: str, password: str, sealed: bytes) -> None:
    """Only where the row still holds the blob this login opened: a password set meanwhile wins."""
    fresh = blob.LoginRecord(record.user_id, record.agency_id, passwords.hash_password(password))
    AppUser.objects.filter(id=record.user_id, login_blob_ct=sealed).update(
        login_blob_ct=blob.seal_login(fresh, email)
    )


def start_pending(request: HttpRequest, verified: Verified, *, enrol: bool = False) -> None:
    """A new session key and nothing carried over; `enrol` marks an enrolment's pending state. A
    signed-in session is retired with a `session_revocation` marker first, in one with_agency()
    transaction with the row delete, as login() does (plan M3 §3 M3d), so the old row put back by
    SQL is still refused."""
    session = request.session
    if not isinstance(session, SessionStore):
        raise TypeError("the password step needs the accounts session store")
    previous, key = session.get(USER), session.session_key
    if previous is None or key is None:
        session.flush()
    else:
        agency = uuid.UUID(session[AGENCY])
        with with_agency(agency):
            mark(agency, uuid.UUID(previous), key)
            session.flush()
    until = timezone.now() + timedelta(minutes=settings.SKIW_LOGIN_PENDING_MIN)
    session.update(
        {
            PENDING_USER: str(verified.user_id),
            PENDING_AGENCY: str(verified.agency_id),
            PENDING_UNTIL: until.isoformat(timespec="microseconds"),
        }
    )
    if enrol:
        session[PENDING_ENROL] = True
    rotate_token(request)
