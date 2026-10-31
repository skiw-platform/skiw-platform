"""`runworker` checks tenant_source_key and login_blob_key before the migration check, as `web`
does (plan M3 (j), M3b).

It reads the keys through settings (SKIW_TENANT_SOURCE_KEYS, SKIW_LOGIN_BLOB_KEYS), so jobs
still imports no accounts.
No database: reaching the migration check fails on the closed port, which proves the order."""

import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parents[2]
KEY = base64.b64encode(secrets.token_bytes(32)).decode()
SHORT = base64.b64encode(secrets.token_bytes(16)).decode()


def runworker(**extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(APP_DIR / "manage.py"), "runworker"],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(APP_DIR),
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": "test-only-not-a-secret",
            "DATABASE_URL": "postgres://u:p@127.0.0.1:9/db",
            **REQUIRED,
            **extra,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.mark.parametrize(
    "value",
    [None, "v1:short", f"v1000000:{KEY}", KEY],
    ids=["missing", "short", "seven-digit-version", "no-version"],
)
def test_runworker_refuses_a_missing_or_malformed_key(value: str | None) -> None:
    result = runworker(**({} if value is None else {"TENANT_SOURCE_KEY": value}))
    assert result.returncode != 0
    assert "TENANT_SOURCE_KEY" in result.stderr.splitlines()[-1]
    assert "cannot verify migrations" not in result.stderr
    assert KEY not in result.stderr


@pytest.mark.parametrize(
    "value",
    [None, f"v1:{SHORT}", f"v65536:{KEY}", KEY],
    ids=["missing", "short", "version-above-65535", "no-version"],
)
def test_runworker_refuses_a_missing_or_malformed_login_blob_key(value: str | None) -> None:
    """Plan M3b: the worker checks login_blob_key too, through settings."""
    extra = {} if value is None else {"LOGIN_BLOB_KEY": value}
    result = runworker(TENANT_SOURCE_KEY=f"v1:{KEY}", **extra)
    assert result.returncode != 0
    assert "LOGIN_BLOB_KEY" in result.stderr.splitlines()[-1]
    assert "cannot verify migrations" not in result.stderr
    assert KEY not in result.stderr and SHORT not in result.stderr


def test_runworker_with_valid_keys_goes_on_to_the_migration_check() -> None:
    result = runworker(TENANT_SOURCE_KEY=f"v1:{KEY}", LOGIN_BLOB_KEY=f"v1:{KEY}")
    assert result.returncode != 0 and "cannot verify migrations" in result.stderr
    assert KEY not in result.stderr
