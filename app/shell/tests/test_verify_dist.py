import json
from pathlib import Path

import pytest

from shell.verify_dist import problems


def build(dist: Path, manifest: object) -> Path:
    (dist / ".vite").mkdir()
    (dist / "assets").mkdir()
    (dist / "assets" / "index-abc.js").write_text("x")
    (dist / "assets" / "index-abc.css").write_text("x")
    (dist / ".vite" / "manifest.json").write_text(
        manifest if isinstance(manifest, str) else json.dumps(manifest)
    )
    return dist


GOOD = {"index.html": {"file": "assets/index-abc.js", "css": ["assets/index-abc.css"]}}


def test_a_complete_build_has_no_problems(tmp_path: Path) -> None:
    assert problems(build(tmp_path, GOOD)) == []


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    assert "missing" in problems(tmp_path)[0]


@pytest.mark.parametrize("manifest", ["{not json", "[]", {"other.html": {"file": "a.js"}}])
def test_a_bad_manifest_is_reported(tmp_path: Path, manifest: object) -> None:
    assert problems(build(tmp_path, manifest))


def test_a_named_file_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    missing = {"index.html": {"file": "assets/index-abc.js", "css": ["assets/gone.css"]}}
    assert problems(build(tmp_path, missing)) == [
        "assets/gone.css is named by the manifest but missing"
    ]
