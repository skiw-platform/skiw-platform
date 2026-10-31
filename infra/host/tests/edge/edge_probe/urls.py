"""TEST ONLY: the app's routes plus probes of what Django sees behind Caddy (UNI-17 test) and of a
session across a restart and a redeploy of `web` (test_session_live.py, plan M2d)."""

import secrets

from django.http import HttpRequest, HttpResponse, JsonResponse

from config.routes import route
from config.urls import urlpatterns as app_urlpatterns

VALUE = "X-Probe-Value"


def probe(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"secure": request.is_secure(), "forwarded_for": request.headers.get("X-Forwarded-For")}
    )


def session_set(request: HttpRequest) -> HttpResponse:
    value = secrets.token_hex(16)
    request.session["probe"] = value
    response = HttpResponse(status=204)
    response[VALUE] = value  # made here, never taken from the request
    return response


def session_get(request: HttpRequest) -> HttpResponse:
    """204 if the session holds the value the test names, 409 if another, 404 if none. Nothing
    from the request or the session is echoed."""
    stored = request.session.get("probe")
    if stored is None:
        return HttpResponse(status=404)
    expected = request.headers.get(VALUE, "")
    same = secrets.compare_digest(stored.encode(), expected.encode())
    return HttpResponse(status=204 if same else 409)


urlpatterns = [
    route("edge-probe", probe, name="edge-probe", methods=("GET",), auth="cookie"),
    route(
        "probe/session/set", session_set, name="probe-session-set", methods=("GET",), auth="cookie"
    ),
    route(
        "probe/session/get", session_get, name="probe-session-get", methods=("GET",), auth="cookie"
    ),
    *app_urlpatterns,
]
