"""The password step of login (spec Flow 5.1 (0)-(1), AUTH-05, AUTH-06; plan M3 §3 M3e). Known and
unknown emails do the same work until the password is right, so neither the answer nor the work
tells an account from no account (plan Risk 2):

1. `throttle.blocked` for the account, IP and lock keys: limited, with no lookup and no Argon2;
2. `lookup.lookup_login`: the row's blob or a decoy of the same length, and its security_event;
3. `blob.open_login`: a decoy, or a blob for another email, opens to None;
4. one Argon2 verify: the record's hash, or `dummy_verify` for None;
5. any failure: the three throttle counters and one `login.failed` event, whatever the reason;
6. a verified password: `status` is read in `with_agency()` (not `active` is a failure as in 5,
   plan [A]), and the lock counter is reset.

All of it runs outside `with_agency()` apart from the status read: no tenant is known yet, and the
throttle rows and events are global. The login route (M3e-2b) answers each outcome."""

import uuid
from dataclasses import dataclass
from typing import Literal

from accounts.auth import blob, passwords, throttle
from accounts.auth.events import record_event
from accounts.auth.lookup import lookup_login
from accounts.user_model import AppUser
from tenancy.binding import with_agency


@dataclass(frozen=True)
class Verified:
    user_id: uuid.UUID
    agency_id: uuid.UUID


def attempt(email: str, password: str, ip: str) -> Verified | Literal["limited", "failed"]:
    if throttle.blocked(email, ip) is not None:
        return "limited"
    record = blob.open_login(lookup_login(email), email)
    if record is None:
        passwords.dummy_verify(password)
        verified = False
    else:
        verified = passwords.verify(record.password_hash, password)
    if record is not None and verified:
        with with_agency(record.agency_id):
            verified = AppUser.objects.filter(id=record.user_id, status="active").exists()
    if record is None or not verified:
        throttle.record_failure(email, ip)
        keys = throttle.keys(email, ip)
        record_event("login.failed", keys.account, keys.ip, {})
        return "failed"
    throttle.reset_on_success(email)
    return Verified(record.user_id, record.agency_id)
