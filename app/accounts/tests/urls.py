"""TEST ONLY: views that write and read the session through the real middleware. Mounted only by
the accounts tests (`pytest.mark.urls`), never by config.urls."""

import secrets

from django.http import HttpRequest, HttpResponse
from django.urls import path


def write(request: HttpRequest) -> HttpResponse:
    request.session["probe"] = secrets.token_hex(8)
    return HttpResponse(request.session["probe"])


async def awrite(request: HttpRequest) -> HttpResponse:
    value = secrets.token_hex(8)
    await request.session.aset("probe", value)
    return HttpResponse(value)


def read(request: HttpRequest) -> HttpResponse:
    return HttpResponse(request.session.get("probe", ""))


urlpatterns = [path("write", write), path("awrite", awrite), path("read", read)]
