"""`login()`: binds a fully authenticated user to the request's session (spec D6, D7; plan M3 §3
M3d, owner Q7 (a)). `django.contrib.auth` is not installed, so this does Django's own steps on the
project's session store: a session of another user is flushed, the session gets a new lifetime
and a new key, the `_skiw_*` keys are written, and the CSRF token is rotated.

A login over an authenticated session (the same user again, or another) retires that session's key
with a `session_revocation` marker, in one with_agency() transaction with the row delete, so the old
row put back by SQL is still refused (plan M3 §3 M3d "a rotation of an authenticated session"). So
login() must run outside any atomic block; a failed marker insert leaves the old session as it was.

Semgrep `start-new-lifetime-login-only` keeps `start_new_lifetime()` in this module: anything
else that renews the absolute deadline would let a session outlive SKIW_SESSION_ABSOLUTE_H.

`reissue()` gives the session of a credential change a new key and login time after the user-wide
marker, so it alone survives that marker (AUTH-07); it keeps the absolute deadline (DECISIONS
M3h-4)."""

import uuid
from typing import TYPE_CHECKING

from django.http import HttpRequest
from django.middleware.csrf import rotate_token
from django.utils import timezone

from accounts.auth.revoke import mark
from accounts.auth.transactions import require_open
from accounts.factor_model import KINDS
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

if TYPE_CHECKING:  # wrapper imports this module
    from accounts.auth.wrapper import Signed

USER = "_skiw_user"
AGENCY = "_skiw_agency"
AUTH_AT = "_skiw_auth_at"  # when this login completed (UTC ISO-8601, microseconds)
SEEN_AT = "_skiw_seen_at"  # the idle clock; the action wrapper refreshes it
FACTOR = "_skiw_factor"  # the second factor that completed the login


def login(request: HttpRequest, user: AppUser, *, factor: str) -> None:
    """Call only after the password and the second factor `factor` were both verified."""
    if factor not in KINDS:
        raise ValueError("unknown second factor")
    session = request.session
    if not isinstance(session, SessionStore):
        raise TypeError("login() needs the accounts session store")
    previous, key = session.get(USER), session.session_key
    if previous is None or key is None:
        _rotate(session, user)
    else:
        agency = uuid.UUID(session[AGENCY])
        with with_agency(agency):
            mark(agency, uuid.UUID(previous), key)
            _rotate(session, user)
    now = timezone.now().isoformat(timespec="microseconds")
    session.update(
        {
            USER: str(user.id),
            AGENCY: str(user.agency_id),
            AUTH_AT: now,
            SEEN_AT: now,
            FACTOR: factor,
        }
    )
    rotate_token(request)


def reissue(request: HttpRequest, signed: "Signed") -> None:
    """Inside the caller's with_agency(), after `revoke.hold` and the user-wide marker: this key is
    retired with its own marker (a saved row put back by SQL stays refused) and replaced; the new
    login time is the app's clock, after the marker's time (the transaction start time,
    `CURRENT_TIMESTAMP`), so the session outlives the marker. The factor stays, and so does the
    deadline: a credential change is not a new login."""
    session = request.session
    if not isinstance(session, SessionStore):
        raise TypeError("reissue() needs the accounts session store")
    require_open("reissue()")
    mark(signed.agency_id, signed.user_id, str(session.session_key))
    session.cycle_key()
    now = timezone.now().isoformat(timespec="microseconds")
    session.update({AUTH_AT: now, SEEN_AT: now})
    rotate_token(request)


def _rotate(session: SessionStore, user: AppUser) -> None:
    if session.get(USER, str(user.id)) != str(user.id):
        session.flush()  # never carry another user's session data over
    session.start_new_lifetime()
    session.cycle_key()
