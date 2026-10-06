import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
GOOD = {
    "DJANGO_SECRET_KEY": "test-only-not-a-secret",
    "DATABASE_URL": "postgres://u:p@localhost:5432/db",
}


def import_settings(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(APP_DIR), **overrides}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_settings_import_with_required_values() -> None:
    assert import_settings(GOOD).returncode == 0


@pytest.mark.parametrize("missing", ["DJANGO_SECRET_KEY", "DATABASE_URL"])
def test_settings_fail_closed_when_required_value_missing(missing: str) -> None:
    result = import_settings({k: v for k, v in GOOD.items() if k != missing})
    assert result.returncode != 0
    assert missing in result.stderr


def test_settings_reject_non_postgres_database_url() -> None:
    result = import_settings({**GOOD, "DATABASE_URL": "sqlite:///x.db"})
    assert result.returncode != 0
