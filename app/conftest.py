"""Fixtures shared by the app test packages."""

import json
from pathlib import Path

import pytest
from pytest_django import Settings


@pytest.fixture
def dist(tmp_path: Path, settings: Settings) -> Path:
    (tmp_path / ".vite").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc.js").write_text("console.log('shell')")
    (tmp_path / "assets" / "index-abc.css").write_text("body{}")
    (tmp_path / "assets" / "icon-BOq3obf_.svg").write_text("<svg/>")
    manifest = {
        "index.html": {
            "file": "assets/index-abc.js",
            "css": ["assets/index-abc.css"],
            "assets": ["assets/icon-BOq3obf_.svg"],
        }
    }
    (tmp_path / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    settings.WEB_DIST_DIR = tmp_path
    return tmp_path
