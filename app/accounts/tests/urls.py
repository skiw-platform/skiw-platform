"""TEST ONLY: views that write and read the session through the real middleware. Mounted only by
the accounts tests (`pytest.mark.urls`), never by config.urls."""

import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path

from accounts.access.catalogue import ACTION_LINES, ROUTE_CODES, ActionLine
from accounts.access.scope import scoped
from accounts.auth.wrapper import InvalidInput, Signed, authorized_action
from accounts.tests.scope_probe import PROBES
from accounts.views import stepup
from tenancy.binding import with_agency


def write(request: HttpRequest) -> HttpResponse:
    request.session["probe"] = secrets.token_hex(8)
    return HttpResponse()


async def awrite(request: HttpRequest) -> HttpResponse:
    await request.session.aset("probe", secrets.token_hex(8))
    return HttpResponse()


def read(request: HttpRequest) -> HttpResponse:
    return HttpResponse(b"set" if "probe" in request.session else b"")


@dataclass(frozen=True)
class Seen:
    signed: Signed
    data: Mapping[str, Any]
    bound: uuid.UUID  # guard.current_agency() inside the handler


SEEN: list[Seen] = []  # what the action handler saw; the response never echoes it


def note_only(body: Mapping[str, Any]) -> Mapping[str, Any]:
    """A schema: at most a string `note`. `agency_id` passes through so the forged-tenant tests can
    show the handler ignores it."""
    if set(body) - {"note", "agency_id"} or not isinstance(body.get("note", ""), str):
        raise InvalidInput
    return body


def handle(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    with connection.cursor() as cursor:
        cursor.execute("SELECT guard.current_agency()")
        (bound,) = cursor.fetchone()
    SEEN.append(Seen(signed, data, bound))
    return HttpResponse(b"done")


def handle_own(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    """`handle` for `own_transaction=True`: steps 1-4 have committed, so it runs in no transaction
    and binds the agency itself (TEN-09)."""
    if connection.in_atomic_block:
        raise AssertionError("an own_transaction handler ran inside a transaction")
    with with_agency(signed.agency_id):
        return handle(request, signed, data)


def scope_ids(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    """The ids scoped() gives on each probe table (M4r-4c); the tables exist only while a
    test module's `scope_probe.table()` does."""
    found = {m._meta.db_table: scoped(m, signed).values_list("pk", flat=True) for m in PROBES}
    return JsonResponse({table: sorted(map(str, ids)) for table, ids in found.items()})


action = authorized_action(schema=note_only, permission="auth.factors", line="any")(handle)
# The role step's routes: every route code on line `any`, and four on a business line; each also
# under own/ with `own_transaction=True`.
LINED: list[tuple[str, ActionLine]] = [(code, "any") for code in sorted(ROUTE_CODES)]
LINED += [("client.view", "insurance"), ("client.view", "investment")]
LINED += [("outbox.approve", "insurance"), ("device.revoke", "insurance")]

urlpatterns = [
    path("write", write),
    path("awrite", awrite),
    path("read", read),
    path("action", action),
    path("stepup", stepup),  # the real POST /api/auth/stepup view
    *(
        path(
            f"scope/{line}",
            authorized_action(schema=note_only, permission="client.view", line=line)(scope_ids),
        )
        for line in ACTION_LINES
    ),
    *(
        path(
            f"{route}/{code}/{line}",
            authorized_action(schema=note_only, permission=code, line=line, own_transaction=own)(
                handle_own if own else handle
            ),
        )
        for code, line in LINED
        for route, own in (("to", False), ("own", True))
    ),
]
