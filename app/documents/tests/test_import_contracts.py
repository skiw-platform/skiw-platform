"""The files-volume (plan §3 M1i) and session-store (plan M2b; the config.urls -> accounts.views
edge, plan M3a, owner Q10 (a)) import-linter contracts fail on a planted import (UNI-04, TEN-10).

lint-imports runs with this repository's own pyproject.toml on a stub tree that has every root
package, so the contract text under test is exactly the one CI uses."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ROOTS = ("config", "health", "shell", "jobs", "documents", "accounts", "skiw_host")
STORAGE = "Only documents may import documents.storage, the files volume module (UNI-04)"
NO_DB = "documents.storage and documents.clamd touch no database (TEN-10)"
SESSION = "Only accounts may import the session store and its model (TEN-10)"


def lint(tmp_path: Path, plant: dict[str, str]) -> str:
    shutil.copy(REPO / "pyproject.toml", tmp_path / "pyproject.toml")
    for root in ROOTS:
        (tmp_path / root).mkdir()
        (tmp_path / root / "__init__.py").write_text("")
    for name in ("storage", "clamd"):
        (tmp_path / "documents" / f"{name}.py").write_text("")
    (tmp_path / "accounts" / "session_model.py").write_text("")
    (tmp_path / "accounts" / "session.py").write_text("from accounts import session_model\n")
    (tmp_path / "accounts" / "models.py").write_text("from accounts.session_model import *\n")
    (tmp_path / "jobs" / "uses.py").write_text("import psycopg\nimport procrastinate\n")
    for path, source in plant.items():
        (tmp_path / path).write_text(source)
    command = [str(Path(sys.executable).parent / "lint-imports"), "--no-cache"]
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    return result.stdout + result.stderr


def test_the_stub_tree_keeps_every_contract(tmp_path: Path) -> None:
    out = lint(tmp_path, {})
    assert f"{STORAGE} KEPT" in out and f"{NO_DB} KEPT" in out and f"{SESSION} KEPT" in out
    assert "0 broken" in out


@pytest.mark.parametrize("root", ["config", "health", "shell", "jobs"])
def test_a_planted_storage_import_breaks_the_contract(tmp_path: Path, root: str) -> None:
    out = lint(tmp_path, {f"{root}/planted.py": "from documents import storage\n"})
    assert f"{STORAGE} BROKEN" in out


@pytest.mark.parametrize("module", ["storage", "clamd"])
def test_a_planted_db_import_breaks_the_contract(tmp_path: Path, module: str) -> None:
    out = lint(tmp_path, {f"documents/{module}.py": "import psycopg\n"})
    assert f"{NO_DB} BROKEN" in out


@pytest.mark.parametrize("root", ["config", "health", "shell", "jobs", "documents", "skiw_host"])
@pytest.mark.parametrize(
    "target", ["accounts.session", "accounts.session_model", "accounts.models"]
)
def test_a_planted_session_store_import_breaks_the_contract(
    tmp_path: Path, root: str, target: str
) -> None:
    out = lint(tmp_path, {f"{root}/planted.py": f"import {target}\n"})
    assert f"{SESSION} BROKEN" in out


# accounts.views stands in for the login views: it reaches the store, as accounts.auth will.
VIEWS = {"accounts/views.py": "import accounts.session\n"}


def test_config_urls_may_import_accounts_views(tmp_path: Path) -> None:
    out = lint(tmp_path, {**VIEWS, "config/urls.py": "from accounts import views\n"})
    assert f"{SESSION} KEPT" in out and "0 broken" in out


@pytest.mark.parametrize(
    "source",
    [
        "import accounts.session\n",
        "from accounts import models\n",
        "from accounts import views\nfrom accounts.session import SessionStore\n",
        "from accounts import views\nimport accounts.models\n",
    ],
    ids=["store", "models", "views-and-store", "views-and-models"],
)
def test_config_urls_reaching_the_store_another_way_breaks_the_contract(
    tmp_path: Path, source: str
) -> None:
    assert f"{SESSION} BROKEN" in lint(tmp_path, {**VIEWS, "config/urls.py": source})


@pytest.mark.parametrize("module", ["config/other.py", "shell/planted.py", "jobs/planted.py"])
def test_accounts_views_outside_config_urls_breaks_the_contract(
    tmp_path: Path, module: str
) -> None:
    assert f"{SESSION} BROKEN" in lint(tmp_path, {**VIEWS, module: "from accounts import views\n"})
