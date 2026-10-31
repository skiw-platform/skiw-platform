# Fixture for `semgrep --test semgrep/` (rule urls-route-only).
from django import urls
from django.urls import path, re_path

from config.routes import route


def view(request):
    return None


urlpatterns = [
    # ruleid: urls-route-only
    path("a", view, name="a"),
    # ruleid: urls-route-only
    re_path(r"^b$", view, name="b"),
    # ruleid: urls-route-only
    urls.path("c", view),
    # ok: urls-route-only
    route("d", view, name="d", methods=("GET",), auth="cookie"),
]
