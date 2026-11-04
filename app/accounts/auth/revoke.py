"""Session revocation on the `session_revocation` marker (plan M3 §3 M3d, carry-over (b); AUTH-07).

A marker with `session_key_hash` revokes one session (idle expiry, logout, a login over an
authenticated session); a user-wide marker revokes every session of the user that signed in at or
before `revoked_at`. `revoked_at` is the database's statement time and `_skiw_auth_at` the web
process's clock; both containers read the host's one clock, and a tie counts as revoked.

`mark()` and `revoked()` run in the caller's with_agency() transaction, so a marker and the
session row delete commit together, and a failed insert leaves the session as it was."""

import uuid
from datetime import datetime

from django.db.models import Q

from accounts.revocation_model import SessionRevocation
from accounts.session import stored_key
from tenancy.binding import with_agency


def mark(agency: uuid.UUID, user: uuid.UUID, session_key: str | None) -> None:
    """One marker: for the session with cookie value `session_key`, or user-wide for None."""
    key_hash = None if session_key is None else stored_key(session_key)
    SessionRevocation.objects.create(agency_id=agency, user_id=user, session_key_hash=key_hash)


def revoked(user: uuid.UUID, session_key: str, auth_at: datetime) -> bool:
    by_key = Q(session_key_hash=stored_key(session_key))
    user_wide = Q(user_id=user, session_key_hash__isnull=True, revoked_at__gte=auth_at)
    return SessionRevocation.objects.filter(by_key | user_wide).exists()


def revoke_user(agency: uuid.UUID, user: uuid.UUID) -> None:
    """AUTH-07: every session of `user` that exists now is revoked (password, 2FA or email
    change). Session rows carry no readable user id, so only the marker does it."""
    with with_agency(agency):
        mark(agency, user, None)
