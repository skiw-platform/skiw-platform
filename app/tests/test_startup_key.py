"""The web start-up check for tenant_source_key (plan M2c): config.asgi calls
accounts.source_key.require_key() before require_migrated() and refuses to serve without a valid
key; the settings import itself never reads the key, because `migrate` has none (spec §8.4 H4)."""

import base64
import os
import secrets
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from accounts.source_key import require_key, seal, unseal
from config import env

APP_DIR = Path(__file__).resolve().parent.parent
NAMES = ("TENANT_SOURCE_KEY", "TENANT_SOURCE_KEY_FILE")


@pytest.fixture(autouse=True)
def no_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    require_key.cache_clear()
    yield
    require_key.cache_clear()


def line(size: int = 32, version: int = 1) -> str:
    return f"v{version}:" + base64.b64encode(secrets.token_bytes(size)).decode()


def test_require_key_refuses_a_missing_key() -> None:
    with pytest.raises(env.MissingSettingError, match="TENANT_SOURCE_KEY"):
        require_key()


@pytest.mark.parametrize(
    "value",
    ["v1:not-base64!", line(16), "1:" + line()[3:], "", line(version=1_000_000)],
    ids=["not-base64", "short", "no-v", "empty", "seven-digit-version"],
)
def test_require_key_refuses_a_malformed_key(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("TENANT_SOURCE_KEY", value)
    with pytest.raises((env.InvalidSettingError, env.MissingSettingError)):
        require_key()


def test_require_key_loads_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENANT_SOURCE_KEY", line())
    first = require_key()
    monkeypatch.setenv("TENANT_SOURCE_KEY", line())
    assert require_key() is first and first[0][0] == 1 and len(first[0][1]) == 32


def test_the_highest_version_seals_and_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    """source_key.SEALED takes at most six digits; the key reader is bounded the same (M3 (c))."""
    monkeypatch.setenv("TENANT_SOURCE_KEY", line(version=999_999))
    when = datetime(2026, 10, 31, tzinfo=UTC)
    sealed = seal("stored", when, "blob")
    assert sealed.startswith("v999999:") and unseal("stored", when, sealed) == "blob"


def start(code: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(APP_DIR),
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": "test-only-not-a-secret",
            # Nothing listens here: reaching the migration check would fail on the database.
            "DATABASE_URL": "postgres://u:p@127.0.0.1:9/db",
            "SKIW_SESSION_ABSOLUTE_H": "12",
            "SKIW_SESSION_IDLE_MIN": "30",
            **extra,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_settings_import_needs_no_key() -> None:
    result = start("import django; django.setup(); from django.conf import settings")
    assert result.returncode == 0, result.stderr[-2000:]


@pytest.mark.parametrize("value", [None, "v1:short"])
def test_asgi_refuses_a_bad_key_before_the_migration_check(value: str | None) -> None:
    extra = {} if value is None else {"TENANT_SOURCE_KEY": value}
    result = start("import config.asgi", **extra)
    assert result.returncode != 0
    assert "TENANT_SOURCE_KEY" in result.stderr.splitlines()[-1]
    assert "cannot verify migrations" not in result.stderr


def test_asgi_refuses_a_seven_digit_version_without_echoing_the_key() -> None:
    value = line(version=1_000_000)
    result = start("import config.asgi", TENANT_SOURCE_KEY=value)
    assert result.returncode != 0
    assert "TENANT_SOURCE_KEY: line 1 is not v<n>:<base64>" in result.stderr.splitlines()[-1]
    assert value.partition(":")[2] not in result.stderr


def test_asgi_with_a_valid_key_goes_on_to_the_migration_check() -> None:
    result = start("import config.asgi", TENANT_SOURCE_KEY=line())
    assert result.returncode != 0 and "cannot verify migrations" in result.stderr
