"""A signed-in user changes their password (spec AUTH-04, AUTH-06, AUTH-07; plan M3 §3 M3h;
DECISIONS M3h-4). The current password is the proof; no step-up. Outside any transaction: the
throttle counts in autocommit and Argon2 (64 MiB) runs with no transaction open.

1. a new password shorter than SKIW_PW_MIN_LENGTH: "short", before any count or Argon2 work;
2. `throttle.blocked` for the user's email and the client IP, the login form's own account, IP and
   lock budget: "limited";
3. one Argon2 verify of `current`: the blob's hash, or `dummy_verify` when the blob does not open
   or names another user or agency, so every failure costs the same; a failure is counted as a
   failed login (`record_failure`, which writes `account.locked` at the lock) and is "wrong";
4. the new hash, sealed; then one with_agency() transaction: `revoke.hold`, the blob swapped only
   where the row still holds the blob step 3 opened ("conflict" otherwise), a user-wide marker
   that ends every other session of the user, and `login.reissue` for this one.

Neither password is logged or kept."""

from typing import Literal

from django.conf import settings
from django.http import HttpRequest

from accounts.auth import blob, passwords, throttle
from accounts.auth.login import reissue
from accounts.auth.revoke import hold, mark
from accounts.auth.wrapper import Signed
from accounts.user_model import AppUser
from tenancy.binding import with_agency

Outcome = Literal["changed", "short", "limited", "wrong", "signed-out", "conflict"]


def change(request: HttpRequest, signed: Signed, current: str, new: str) -> Outcome:
    if len(passwords.normalise(new)) < settings.SKIW_PW_MIN_LENGTH:
        return "short"
    with with_agency(signed.agency_id):
        user = AppUser.objects.filter(id=signed.user_id, status="active").first()
    if user is None:
        return "signed-out"
    email, sealed, ip = user.email, bytes(user.login_blob_ct or b""), throttle.client_ip(request)
    if throttle.blocked(email, ip) is not None:
        return "limited"
    record = blob.open_login(sealed, email)
    if record is None or (record.user_id, record.agency_id) != (signed.user_id, signed.agency_id):
        passwords.dummy_verify(current)
        right = False
    else:
        right = passwords.verify(record.password_hash, current)
    if not right:
        throttle.record_failure(email, ip)
        return "wrong"
    throttle.reset_on_success(email)
    fresh = blob.LoginRecord(signed.user_id, signed.agency_id, passwords.hash_password(new))
    resealed = blob.seal_login(fresh, email)
    with with_agency(signed.agency_id):
        if not hold(signed, str(request.session.session_key)):
            request.session.flush()
            return "signed-out"
        swapped = AppUser.objects.filter(id=signed.user_id, login_blob_ct=sealed)
        if not swapped.update(login_blob_ct=resealed):
            return "conflict"  # the password changed after step 3 read it
        mark(signed.agency_id, signed.user_id, None)
        reissue(request, signed)
    return "changed"
