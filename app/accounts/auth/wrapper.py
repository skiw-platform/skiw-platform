"""`authorized_action`: the one gate for a signed-in request (spec D6, T5; AUTH-01, AUTH-02; plan M3
§3 M3d). There is no auth middleware; every signed-in route is a handler wrapped here, and the
route registry test (app/tests/test_route_registry.py) fails any route that is neither wrapped nor
reviewed as public. The steps run in AUTH-01 order and a failing step stops the request:

1. session: a completed login (the `_skiw_*` keys of accounts.auth.login), else 401;
2. tenant: `with_agency(_skiw_agency)`, inside which the idle timeout (a marker and a logout),
   the revocation markers and `status = 'active'` are checked; a failure logs out, 401;
3. role/permission (slice spec Decisions 6, 7, 8, 26), in the same with_agency(): a second
   factor, else 403 `forbidden`. A self-service `permission` reads no grant and gives empty
   access. A catalogue code reads the user's grants once (accounts.access.grants) and keeps each
   grant whose assignment line matches the route's `line` in LINE_MATCHES; none: 403 `forbidden`.
   Of those, a grant that needs a step-up is kept only while `stepup.recent()` finds this
   session's evidence for its purpose (one call per distinct purpose, nothing cached); none left:
   403 `stepup-required`, never for a line refusal. No 403 logs out. The kept grants are
   `Signed.access`, the handler's only grants;
4. input: `schema` parses the JSON object body (UNI-03); InvalidInput gives 400;
5. idempotency: no M3 action needs it;
6. the handler, in the same tenant transaction; or, with `own_transaction=True`, after steps 1-4
   have committed and outside any transaction, for a handler that counts attempts (the factor
   counters refuse an open transaction). Such a handler opens with_agency(signed.agency_id) itself
   for every tenant query (TEN-09); steps 1-4 and their order are the same in both modes, and its
   `access` is what step 3 read before that commit.

Every refusal is `Cache-Control: no-store` (AUTH-05).

The agency is the session's, never the client's: nothing here reads an agency from the body, the
query or a header (TEN-11). `_skiw_seen_at` is written at most once a minute, because each session
write re-seals the row."""

import functools
import inspect
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Final, Literal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from accounts.access.catalogue import ACTION_LINES, ROUTE_CODES, SELF_SERVICE, ActionLine
from accounts.access.grants import Grant, grants
from accounts.access.tables import Line
from accounts.auth.login import AGENCY, AUTH_AT, FACTOR, SEEN_AT, USER
from accounts.auth.revoke import mark, revoked
from accounts.auth.stepup import StepUp, recent
from accounts.factor_model import KINDS
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

SEEN_STEP = timedelta(minutes=1)
# config.routes.SAFE_METHODS, which accounts may not import (import-linter): these carry no body.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Decision 26: (assignment line, action line) pairs that match, listed one by one. Any other pair,
# a value outside the types included, matches nothing.
LINE_MATCHES: Final[frozenset[tuple[Line, ActionLine]]] = frozenset(
    {
        ("insurance", "insurance"),
        ("insurance", "any"),
        ("investment", "investment"),
        ("investment", "any"),
        ("both", "insurance"),
        ("both", "investment"),
        ("both", "any"),
    }
)


class InvalidInput(Exception):
    """Raised by a schema: the request body is not what the action accepts. No detail is sent."""


@dataclass(frozen=True)
class Signed:
    """Who is acting, as the session says; the handler's only source of user and agency."""

    user_id: uuid.UUID
    agency_id: uuid.UUID
    factor: str | None
    auth_at: datetime
    seen_at: datetime
    access: frozenset[Grant]  # step 3's kept grants; empty for a self-service action


def nothing(body: Mapping[str, Any]) -> None:
    """The schema of an action that takes no input: exactly `{}`."""
    if body:
        raise InvalidInput


def _signed(session: SessionStore) -> Signed | None:
    """The completed login in the session, or None. Only login() writes these keys (UTC-aware
    times), and a row that fails the MAC (M2c) loads as empty with no key, so a session that has
    them has a key and well-formed values; a missing key is still no login, never a 500."""
    try:
        return Signed(
            user_id=uuid.UUID(session[USER]),
            agency_id=uuid.UUID(session[AGENCY]),
            factor=session.get(FACTOR),
            auth_at=datetime.fromisoformat(session[AUTH_AT]),
            seen_at=datetime.fromisoformat(session[SEEN_AT]),
            access=frozenset(),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _tenant_step(signed: Signed, key: str, now: datetime) -> Literal["live", "idle", "signed-out"]:
    """Step 2's checks, inside the caller's with_agency(signed.agency_id); reads only. The
    wrapper acts on a failure (marker, flush); `signed_in` only reports it."""
    if now - signed.seen_at >= timedelta(minutes=settings.SKIW_SESSION_IDLE_MIN):
        return "idle"
    active = AppUser.objects.filter(id=signed.user_id, status="active").exists()
    if not active or revoked(signed.user_id, key, signed.auth_at):
        return "signed-out"
    return "live"


def _role_step(
    request: HttpRequest, signed: Signed, permission: str, line: ActionLine
) -> frozenset[Grant] | Literal["forbidden", "stepup-required"]:
    """Step 3 after the factor check, inside the caller's with_agency(): the kept grants, or the
    403 code. One grant read and one step-up read per purpose, never cached (AUTH-09, AUTH-12)."""
    if permission in SELF_SERVICE:
        return frozenset()
    held = grants(signed.user_id, permission)
    # isinstance first, as at registration: an unhashable line would raise TypeError in the lookup
    # (a 500); a line that is not a str matches nothing (Decision 26).
    matching = [g for g in held if isinstance(line, str) and (g.line, line) in LINE_MATCHES]
    if not matching:
        return "forbidden"
    purposes = {g.stepup for g in matching if g.stepup is not None}
    fresh = {p for p in purposes if isinstance(recent(request, p), StepUp)}
    kept = frozenset(g for g in matching if g.stepup is None or g.stepup in fresh)
    return kept or "stepup-required"


def signed_in(session: SessionStore) -> bool:
    """Whether the wrapper would let this session past steps 1-2 and the factor check of step 3
    (no permission is named, so no grant is read), for GET /api/auth/session
    (DECISIONS M3i-0). The absolute deadline and the row's MAC are the store's (a row past either
    loads empty). Changes nothing: no marker, no flush and no idle clock write, so a poll never
    keeps a session alive; a refused session stays refused and the next wrapped call ends it."""
    signed = _signed(session)
    if signed is None or signed.factor not in KINDS:
        return False
    with with_agency(signed.agency_id):
        return _tenant_step(signed, str(session.session_key), timezone.now()) == "live"


def _body(request: HttpRequest) -> Mapping[str, Any]:
    if request.method in SAFE_METHODS:
        return {}
    if request.content_type != "application/json":
        raise InvalidInput
    try:
        body = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidInput from exc
    if not isinstance(body, dict):
        raise InvalidInput
    return body


def _refused(status: int, code: str) -> HttpResponse:
    response = JsonResponse({"error": code}, status=status)
    response["Cache-Control"] = "no-store"
    return response


def authorized_action[T](
    *,
    schema: Callable[[Mapping[str, Any]], T],
    permission: str,
    line: ActionLine,
    own_transaction: bool = False,
) -> Callable[[Callable[[HttpRequest, Signed, T], HttpResponse]], Callable[..., HttpResponse]]:
    # `line` has no default (Decision 26): leaving it out is Python's TypeError (DECISIONS M4r-2 A).
    # isinstance first: an unhashable value would raise TypeError in the set lookup.
    if not isinstance(permission, str) or permission not in ROUTE_CODES:
        raise ImproperlyConfigured(f"authorized_action: unknown permission {permission!r}")
    if not isinstance(line, str) or line not in ACTION_LINES:
        raise ImproperlyConfigured(f"authorized_action: line must be one of {ACTION_LINES}")

    def decorate(
        handler: Callable[[HttpRequest, Signed, T], HttpResponse],
    ) -> Callable[..., HttpResponse]:
        # A coroutine returned here would run after with_agency() closed, outside the binding.
        if inspect.iscoroutinefunction(handler):
            raise ImproperlyConfigured("authorized_action wraps sync handlers only")

        @functools.wraps(handler)
        def view(request: HttpRequest) -> HttpResponse:
            session = request.session
            if not isinstance(session, SessionStore):  # the MAC-checked store (M2c), nothing else
                raise TypeError("authorized_action needs the accounts session store")
            signed = _signed(session)
            if signed is None:
                return _refused(401, "signed-out")
            now, key = timezone.now(), str(session.session_key)
            with with_agency(signed.agency_id):
                state = _tenant_step(signed, key, now)
                if state == "idle":
                    mark(signed.agency_id, signed.user_id, key)
                    session.flush()
                    return _refused(401, "idle")
                if state == "signed-out":
                    session.flush()
                    return _refused(401, "signed-out")
                if signed.factor not in KINDS:
                    return _refused(403, "forbidden")
                access = _role_step(request, signed, permission, line)
                if isinstance(access, str):
                    return _refused(403, access)
                signed = replace(signed, access=access)
                try:
                    data = schema(_body(request))
                except InvalidInput:
                    return _refused(400, "invalid")
                if now - signed.seen_at >= SEEN_STEP:
                    session[SEEN_AT] = now.isoformat(timespec="microseconds")
                if not own_transaction:
                    return handler(request, signed, data)
            return handler(request, signed, data)  # own_transaction: the checks have committed

        vars(view).update(skiw_action=permission, skiw_line=line)  # the route registry reads them
        return view

    return decorate
