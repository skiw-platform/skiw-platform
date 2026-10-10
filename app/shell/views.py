import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from django.views.static import serve

ENTRY = "index.html"
ASSET_CACHE_SECONDS = 31_536_000  # one year, hashed immutable assets


def read_entry(dist: Path) -> dict[str, Any] | None:
    manifest = dist / ".vite" / "manifest.json"
    if not manifest.is_file():
        return None
    entry: dict[str, Any] = json.loads(manifest.read_text())[ENTRY]
    return entry


@require_GET
def shell(request: HttpRequest) -> HttpResponse:
    entry = read_entry(settings.WEB_DIST_DIR)
    if entry is None:
        return HttpResponse(
            "Web build missing. Run `make web-build`.",
            status=503,
            content_type="text/plain",
        )
    context = {
        "script": f"/{entry['file']}",
        "styles": [f"/{name}" for name in entry.get("css", [])],
    }
    return render(request, "shell/shell.html", context)


@require_GET
@cache_control(max_age=ASSET_CACHE_SECONDS, immutable=True)
def asset(request: HttpRequest, path: str) -> HttpResponseBase:
    return serve(request, path, document_root=str(settings.WEB_DIST_DIR / "assets"))
