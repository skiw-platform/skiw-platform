"""TEST ONLY: config.urls plus one cookie-auth POST route, so the CSRF gate's mutating cases run
before the first real mutating route exists (plan M2d). Mounted only by the gate tests."""

from django.http import HttpRequest, HttpResponse

from config.routes import route
from config.urls import urlpatterns as app_urlpatterns


def csrf_probe(request: HttpRequest) -> HttpResponse:
    return HttpResponse(b"done")


urlpatterns = [
    route("csrf-probe", csrf_probe, name="csrf-probe", methods=("POST",), auth="cookie"),
    *app_urlpatterns,
]
