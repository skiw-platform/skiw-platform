import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from config.env import InvalidSettingError, MissingSettingError, database_from_url

APP_DIR = Path(__file__).resolve().parent.parent
BASE = "postgres://u:p%40ss@db.example:5433/skiw"


def test_plain_url_has_no_tls_options() -> None:
    config = database_from_url(BASE)
    assert config["USER"] == "u"
    assert config["PASSWORD"] == "p@ss"
    assert config["HOST"] == "db.example"
    assert config["PORT"] == "5433"
    assert config["NAME"] == "skiw"
    assert config["OPTIONS"] == {}


def test_tls_parameters_reach_the_django_options() -> None:
    url = f"{BASE}?sslmode=verify-full&sslrootcert=/etc/ssl/rds-ca.pem"
    config = database_from_url(url, require_tls=True)
    assert config["OPTIONS"] == {"sslmode": "verify-full", "sslrootcert": "/etc/ssl/rds-ca.pem"}


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer", "require"])
def test_require_tls_rejects_weak_modes(mode: str) -> None:
    with pytest.raises(InvalidSettingError):
        database_from_url(f"{BASE}?sslmode={mode}", require_tls=True)


def test_require_tls_rejects_missing_mode() -> None:
    with pytest.raises(InvalidSettingError):
        database_from_url(BASE, require_tls=True)


@pytest.mark.parametrize(
    "query", ["sslmode=bogus", "application_name=x", "sslmode=require&sslmode=verify-full"]
)
def test_unknown_invalid_or_repeated_options_are_rejected(query: str) -> None:
    with pytest.raises(InvalidSettingError):
        database_from_url(f"{BASE}?{query}")


def test_non_postgres_url_is_rejected() -> None:
    with pytest.raises(MissingSettingError):
        database_from_url("sqlite:///x.db")


def test_settings_pass_tls_options_through_to_databases() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(APP_DIR),
        "DJANGO_SECRET_KEY": "test-only-not-a-secret",
        "DJANGO_REQUIRE_DB_TLS": "1",
        "DATABASE_URL": f"{BASE}?sslmode=verify-full&sslrootcert=/etc/ssl/rds-ca.pem",
        "SKIW_SESSION_ABSOLUTE_H": "12",
        "SKIW_SESSION_IDLE_MIN": "30",
    }
    code = "import json, config.settings as s; print(json.dumps(s.DATABASES['default']['OPTIONS']))"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "sslmode": "verify-full",
        "sslrootcert": "/etc/ssl/rds-ca.pem",
    }
