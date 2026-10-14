"""TEST ONLY: the app's routes plus a probe of what Django sees behind Caddy (UNI-17 test)."""

from django.http import HttpRequest, JsonResponse
from django.urls import path

from config.urls import urlpatterns as app_urlpatterns


def probe(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"secure": request.is_secure(), "forwarded_for": request.headers.get("X-Forwarded-For")}
    )


urlpatterns = [path("edge-probe", probe), *app_urlpatterns]
