"""TEST ONLY: views that write and read the session through the real middleware. Mounted only by
the accounts tests (`pytest.mark.urls`), never by config.urls."""

import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.urls import path

from accounts.auth.wrapper import InvalidInput, Signed, authorized_action


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


@authorized_action(schema=note_only, permission="test.action")
def action(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    with connection.cursor() as cursor:
        cursor.execute("SELECT guard.current_agency()")
        (bound,) = cursor.fetchone()
    SEEN.append(Seen(signed, data, bound))
    return HttpResponse(b"done")


urlpatterns = [
    path("write", write),
    path("awrite", awrite),
    path("read", read),
    path("action", action),
]
