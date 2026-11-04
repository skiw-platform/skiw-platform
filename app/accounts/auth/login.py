"""`login()`: binds a fully authenticated user to the request's session (spec D6, D7; plan M3 §3
M3d, owner Q7 (a)). `django.contrib.auth` is not installed, so this does Django's own steps on the
project's session store: a session of another user is flushed, the session gets a new lifetime
and a new key, the `_skiw_*` keys are written, and the CSRF token is rotated.

Semgrep `start-new-lifetime-login-only` keeps `start_new_lifetime()` in this module: anything
else that renews the absolute deadline would let a session outlive SKIW_SESSION_ABSOLUTE_H."""

from django.http import HttpRequest
from django.middleware.csrf import rotate_token
from django.utils import timezone

from accounts.factor_model import KINDS
from accounts.session import SessionStore
from accounts.user_model import AppUser

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
    if session.get(USER, str(user.id)) != str(user.id):
        session.flush()  # never carry another user's session data over
    session.start_new_lifetime()
    session.cycle_key()
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
