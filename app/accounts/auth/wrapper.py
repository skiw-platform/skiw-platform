"""`authorized_action`: the one gate for a signed-in request (spec D6, T5; AUTH-01, AUTH-02; plan M3
§3 M3d). There is no auth middleware; every signed-in route is a handler wrapped here, and the
route registry test (app/tests/test_route_registry.py) fails any route that is neither wrapped nor
reviewed as public. The steps run in AUTH-01 order and a failing step stops the request:

1. session: a completed login (the `_skiw_*` keys of accounts.auth.login), else 401;
2. tenant: `with_agency(_skiw_agency)`, inside which the idle timeout (a marker and a logout),
   the revocation markers and `status = 'active'` are checked; a failure logs out, 401;
3. role/permission: until M4-rest, "signed in with a second factor" (AUTH-03 is not checked yet;
   `permission` names the §6 matrix entry M4-rest will check), else 403;
4. input: `schema` parses the JSON object body (UNI-03); InvalidInput gives 400;
5. idempotency: no M3 action needs it;
6. the handler, in the same tenant transaction.

The agency is the session's, never the client's: nothing here reads an agency from the body, the
query or a header (TEN-11). `_skiw_seen_at` is written at most once a minute, because each session
write re-seals the row."""

import functools
import inspect
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from accounts.auth.login import AGENCY, AUTH_AT, FACTOR, SEEN_AT, USER
from accounts.auth.revoke import mark, revoked
from accounts.factor_model import KINDS
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency

SEEN_STEP = timedelta(minutes=1)
# config.routes.SAFE_METHODS, which accounts may not import (import-linter): these carry no body.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


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
        )
    except (KeyError, TypeError, ValueError):
        return None


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
    return JsonResponse({"error": code}, status=status)


def authorized_action[T](
    *, schema: Callable[[Mapping[str, Any]], T], permission: str
) -> Callable[[Callable[[HttpRequest, Signed, T], HttpResponse]], Callable[..., HttpResponse]]:
    if not permission:
        raise ImproperlyConfigured("authorized_action needs the permission it checks")

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
                if now - signed.seen_at >= timedelta(minutes=settings.SKIW_SESSION_IDLE_MIN):
                    mark(signed.agency_id, signed.user_id, key)
                    session.flush()
                    return _refused(401, "idle")
                active = AppUser.objects.filter(id=signed.user_id, status="active").exists()
                if not active or revoked(signed.user_id, key, signed.auth_at):
                    session.flush()
                    return _refused(401, "signed-out")
                if signed.factor not in KINDS:
                    return _refused(403, "forbidden")
                try:
                    data = schema(_body(request))
                except InvalidInput:
                    return _refused(400, "invalid")
                if now - signed.seen_at >= SEEN_STEP:
                    session[SEEN_AT] = now.isoformat(timespec="microseconds")
                return handler(request, signed, data)

        vars(view).update(skiw_action=permission)  # the route registry reads it
        return view

    return decorate
