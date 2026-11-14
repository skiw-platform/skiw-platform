"""Session revocation on the `session_revocation` marker (plan M3 §3 M3d, carry-over (b); AUTH-07).

A marker with `session_key_hash` revokes one session (idle expiry, logout, a login over an
authenticated session); a user-wide marker revokes every session of the user that signed in at or
before `revoked_at`. `revoked_at` is the marker insert's own statement time
(`statement_timestamp()`, the column's `db_default=Now()`), not the transaction start, and
`_skiw_auth_at` the web process's clock; both containers read the host's one clock, and a tie
counts as revoked. So a change writes the marker before `login()` or `login.reissue` sets the new
login time: the other order would leave the new session at or before the marker, revoked. A
user-wide marker also ends a login still at its second factor whose password step passed at or
before it (`changed_since`, DECISIONS M3h-5).

`mark()` and `revoked()` run in the caller's with_agency() transaction, so a marker and the
session row delete commit together, and a failed insert leaves the session as it was.

`hold()` comes first in every credential change (DECISIONS M3h-4): it locks the user's row, so two
changes for one user take turns, and the second sees the first's user-wide marker (READ
COMMITTED) instead of re-issuing a session that marker revoked."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from django.db.models import Q

from accounts.auth.transactions import require_open
from accounts.revocation_model import SessionRevocation
from accounts.session import stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency

if TYPE_CHECKING:  # wrapper imports this module
    from accounts.auth.wrapper import Signed


def mark(agency: uuid.UUID, user: uuid.UUID, session_key: str | None) -> None:
    """One marker: for the session with cookie value `session_key`, or user-wide for None."""
    key_hash = None if session_key is None else stored_key(session_key)
    SessionRevocation.objects.create(agency_id=agency, user_id=user, session_key_hash=key_hash)


def _user_wide(user: uuid.UUID, since: datetime) -> Q:
    return Q(user_id=user, session_key_hash__isnull=True, revoked_at__gte=since)


def revoked(user: uuid.UUID, session_key: str, auth_at: datetime) -> bool:
    by_key = Q(session_key_hash=stored_key(session_key))
    return SessionRevocation.objects.filter(by_key | _user_wide(user, auth_at)).exists()


def changed_since(user: uuid.UUID, since: datetime) -> bool:
    """Inside the caller's with_agency(): a user-wide marker (a credential change) at or after
    `since`, a tie included."""
    return SessionRevocation.objects.filter(_user_wide(user, since)).exists()


def hold(signed: "Signed", session_key: str) -> bool:
    """Inside the caller's with_agency(): locks the session user's row until the transaction ends
    and says whether the user is still `active` and this session not revoked. Read after the lock,
    so a marker another change committed while this one waited is seen."""
    require_open("credential changes")
    user = AppUser.objects.select_for_update().filter(id=signed.user_id, status="active").first()
    return user is not None and not revoked(signed.user_id, session_key, signed.auth_at)


def revoke_user(agency: uuid.UUID, user: uuid.UUID) -> None:
    """AUTH-07: every session of `user` that exists now is revoked (password, 2FA or email
    change). Session rows carry no readable user id, so only the marker does it."""
    with with_agency(agency):
        mark(agency, user, None)
