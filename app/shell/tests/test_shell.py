import re
from pathlib import Path

import pytest
from django.test import Client
from pytest_django import Settings

from shell.views import ASSET_CACHE_SECONDS


def test_shell_links_the_built_assets_from_the_manifest(dist: Path) -> None:
    response = Client().get("/")
    body = response.content.decode()
    assert response.status_code == 200
    assert '<html lang="en-MY">' in body
    assert '<div id="root">' in body
    assert body.count("<main") == 1
    assert body.count("<h1>") == 1
    assert "<nav" not in body  # signed-out first render: loading state, no navigation
    assert '<p role="status">Checking your session</p>' in body
    assert 'src="/assets/index-abc.js"' in body
    assert 'href="/assets/index-abc.css"' in body
    assert '<link rel="icon" href="/assets/icon-BOq3obf_.svg" type="image/svg+xml">' in body


def test_shell_refuses_a_build_without_a_hashed_icon(dist: Path) -> None:
    manifest = dist / ".vite" / "manifest.json"
    manifest.write_text(manifest.read_text().replace("icon-BOq3obf_", "icon"))
    response = Client().get("/")
    assert response.status_code == 503
    assert b"hashed icon" in response.content


def test_shell_reports_a_missing_build_clearly(tmp_path: Path, settings: Settings) -> None:
    settings.WEB_DIST_DIR = tmp_path
    response = Client().get("/")
    assert response.status_code == 503
    assert b"make web-build" in response.content


def test_assets_are_served_with_long_immutable_caching(dist: Path) -> None:
    response = Client().get("/assets/index-abc.js")
    assert response.status_code == 200
    assert "immutable" in response["Cache-Control"]
    assert f"max-age={ASSET_CACHE_SECONDS}" in response["Cache-Control"]


@pytest.mark.parametrize(
    "path",
    ["/assets/../.vite/manifest.json", "/assets/..%2f.vite%2fmanifest.json", "/assets/missing.js"],
)
def test_assets_cannot_escape_the_assets_folder(dist: Path, path: str) -> None:
    assert Client().get(path).status_code in {400, 404}


def test_the_invite_path_serves_the_same_shell_and_headers(dist: Path) -> None:
    """The invite link is /enrol#<token> (accounts_invite). A browser never sends the fragment,
    and Referrer-Policy same-origin keeps even the path off other origins (DECISIONS M3i-0)."""
    varying = re.compile(r'(nonce|content)="[\w-]{22,}"|nonce-[\w-]{22}')
    home, enrol = Client().get("/"), Client().get("/enrol#token")
    assert enrol.status_code == 200 and enrol.wsgi_request.get_full_path() == "/enrol"
    assert {k: varying.sub("", v) for k, v in enrol.items()} == {
        k: varying.sub("", v) for k, v in home.items()
    }
    assert varying.sub("", enrol.content.decode()) == varying.sub("", home.content.decode())
    assert (enrol["Cache-Control"], enrol["Referrer-Policy"]) == ("no-store", "same-origin")


def test_shell_and_assets_accept_get_only(dist: Path) -> None:
    assert Client().post("/").status_code == 405
    assert Client().post("/enrol").status_code == 405
    assert Client().post("/assets/index-abc.js").status_code == 405
