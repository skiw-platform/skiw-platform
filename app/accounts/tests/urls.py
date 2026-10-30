"""TEST ONLY: views that write and read the session through the real middleware. Mounted only by
the accounts tests (`pytest.mark.urls`), never by config.urls."""

import secrets

from django.http import HttpRequest, HttpResponse
from django.urls import path


def write(request: HttpRequest) -> HttpResponse:
    request.session["probe"] = secrets.token_hex(8)
    return HttpResponse()


async def awrite(request: HttpRequest) -> HttpResponse:
    await request.session.aset("probe", secrets.token_hex(8))
    return HttpResponse()


def read(request: HttpRequest) -> HttpResponse:
    return HttpResponse(b"set" if "probe" in request.session else b"")


urlpatterns = [path("write", write), path("awrite", awrite), path("read", read)]
