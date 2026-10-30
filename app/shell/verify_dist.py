"""Build-time check of the web build: `python -m shell.verify_dist <dist>` (see Dockerfile)."""

import json
import sys
from pathlib import Path

from shell.views import ENTRY, ICON


def problems(dist: Path) -> list[str]:
    manifest = dist / ".vite" / "manifest.json"
    if not manifest.is_file():
        return [f"{manifest} is missing"]
    try:
        chunks = json.loads(manifest.read_text())
    except ValueError as error:
        return [f"{manifest} is not valid JSON: {error}"]
    if not isinstance(chunks, dict) or not isinstance(chunks.get(ENTRY), dict):
        return [f"{manifest} has no {ENTRY} entry"]
    found = []
    if not any(ICON.fullmatch(name) for name in chunks[ENTRY].get("assets", [])):
        found.append(f"{ENTRY} names no hashed icon (assets/icon-<hash>.svg)")
    for chunk in chunks.values():
        names = [chunk.get("file"), *chunk.get("css", []), *chunk.get("assets", [])]
        found += [
            f"{name} is named by the manifest but missing"
            for name in names
            if not isinstance(name, str) or not (dist / name).is_file()
        ]
    return found


if __name__ == "__main__":
    errors = problems(Path(sys.argv[1]))
    if errors:
        sys.exit("web build verification failed:\n" + "\n".join(errors))
