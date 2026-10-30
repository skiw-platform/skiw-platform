import json
from pathlib import Path

import pytest

from shell.verify_dist import problems


def build(dist: Path, manifest: object) -> Path:
    (dist / ".vite").mkdir()
    (dist / "assets").mkdir()
    (dist / "assets" / "index-abc.js").write_text("x")
    (dist / "assets" / "index-abc.css").write_text("x")
    (dist / "assets" / "icon-BOq3obf_.svg").write_text("x")
    (dist / ".vite" / "manifest.json").write_text(
        manifest if isinstance(manifest, str) else json.dumps(manifest)
    )
    return dist


GOOD = {
    "index.html": {
        "file": "assets/index-abc.js",
        "css": ["assets/index-abc.css"],
        "assets": ["assets/icon-BOq3obf_.svg"],
    }
}


def test_a_complete_build_has_no_problems(tmp_path: Path) -> None:
    assert problems(build(tmp_path, GOOD)) == []


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    assert "missing" in problems(tmp_path)[0]


@pytest.mark.parametrize("manifest", ["{not json", "[]", {"other.html": {"file": "a.js"}}])
def test_a_bad_manifest_is_reported(tmp_path: Path, manifest: object) -> None:
    assert problems(build(tmp_path, manifest))


def test_a_named_file_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    missing = {"index.html": {**GOOD["index.html"], "css": ["assets/gone.css"]}}
    assert problems(build(tmp_path, missing)) == [
        "assets/gone.css is named by the manifest but missing"
    ]


def test_a_build_without_a_hashed_icon_is_reported(tmp_path: Path) -> None:
    manifest = {"index.html": {**GOOD["index.html"], "assets": []}}
    assert "no hashed icon" in problems(build(tmp_path, manifest))[0]
