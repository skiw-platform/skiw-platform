import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parent.parent
GOOD = {
    "DJANGO_SECRET_KEY": "test-only-not-a-secret",
    "DATABASE_URL": "postgres://u:p@localhost:5432/db",
    **REQUIRED,
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


@pytest.mark.parametrize("missing", list(GOOD))
def test_settings_fail_closed_when_required_value_missing(missing: str) -> None:
    result = import_settings({k: v for k, v in GOOD.items() if k != missing})
    assert result.returncode != 0
    assert missing in result.stderr


def test_settings_reject_non_postgres_database_url() -> None:
    result = import_settings({**GOOD, "DATABASE_URL": "sqlite:///x.db"})
    assert result.returncode != 0


@pytest.mark.parametrize(("value", "trusted"), [(None, False), ("0", False), ("1", True)])
def test_proxy_ssl_header_only_behind_caddy(value: str | None, trusted: bool) -> None:
    behind = {} if value is None else {"DJANGO_BEHIND_CADDY": value}
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(APP_DIR), **GOOD, **behind}
    code = "import config.settings as s; print(getattr(s, 'SECURE_PROXY_SSL_HEADER', None))"
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    expected = "('HTTP_X_FORWARDED_PROTO', 'https')" if trusted else "None"
    assert result.stdout.strip() == expected, result.stderr
