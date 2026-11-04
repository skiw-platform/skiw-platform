"""TEST ONLY: config.urls plus two cookie-auth POST routes, so the CSRF gate's mutating cases run
before the first real mutating route exists (plan M2d): `csrf-probe`, a plain view, and
`action-probe`, an `authorized_action` handler (plan M3d: the gate with a logged-in session).
Mounted only by the gate tests."""

from collections.abc import Mapping
from typing import Any

from django.http import HttpRequest, HttpResponse

from accounts.auth.wrapper import Signed, authorized_action
from config.routes import route
from config.urls import urlpatterns as app_urlpatterns


def csrf_probe(request: HttpRequest) -> HttpResponse:
    return HttpResponse(b"done")


def any_object(body: Mapping[str, Any]) -> Mapping[str, Any]:
    return body


@authorized_action(schema=any_object, permission="test.action-probe")
def action_probe(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    return HttpResponse(b"done")


urlpatterns = [
    route("csrf-probe", csrf_probe, name="csrf-probe", methods=("POST",), auth="cookie"),
    route("action-probe", action_probe, name="action-probe", methods=("POST",), auth="cookie"),
    *app_urlpatterns,
]
