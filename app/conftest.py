"""Fixtures shared by the app test packages."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pytest_django import Settings

from accounts.tests import event_probe


@pytest.fixture(scope="session", autouse=True)
def security_event_probe(request: pytest.FixtureRequest) -> Iterator[None]:
    """The test-only probe trigger (accounts.tests.event_probe) for a live run: the accounts tests
    and the TEN-08 harness plant change rows through it. Removed afterwards, also a leftover."""
    live = any(item.get_closest_marker("live") for item in request.session.items)
    if live:
        event_probe.install()
    yield
    if live:
        event_probe.remove()


@pytest.fixture
def clear_change_events() -> Callable[[], None]:
    """accounts.tests.event_probe.clear_change_events, for a package that may not import accounts
    (tenancy) and migrates back past accounts.0022."""
    return event_probe.clear_change_events


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
