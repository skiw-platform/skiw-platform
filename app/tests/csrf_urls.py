"""TEST ONLY: config.urls plus three cookie-auth POST routes, so the CSRF gate's mutating cases run
before the first real mutating route exists (plan M2d): `csrf-probe`, a plain view,
`action-probe`, an `authorized_action` handler (plan M3d: the gate with a logged-in session), and
`stepup-probe`, a test-only consumer of `stepup.recent()` (M3h-3; the password-change tests still
use it beside the real consumers, the factor changes of M3h-5). Mounted only by tests
(`pytest.mark.urls`), never by config.urls (test_route_registry checks that no probe is served)."""

from collections.abc import Mapping
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

from accounts.auth.stepup import FACTOR_CHANGE, recent
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


@authorized_action(schema=any_object, permission="test.stepup-probe")
def stepup_probe(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    if recent(request, FACTOR_CHANGE) is None:
        return JsonResponse({"error": "stepup-required"}, status=403)
    return HttpResponse(b"done")


urlpatterns = [
    route("csrf-probe", csrf_probe, name="csrf-probe", methods=("POST",), auth="cookie"),
    route("action-probe", action_probe, name="action-probe", methods=("POST",), auth="cookie"),
    route("stepup-probe", stepup_probe, name="stepup-probe", methods=("POST",), auth="cookie"),
    *app_urlpatterns,
]
