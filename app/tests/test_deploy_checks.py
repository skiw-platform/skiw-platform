"""`manage.py check --deploy` with host-like settings (spec §9 M2, UNI-17; plan M2a)."""

import base64
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parent.parent
# The variables infra/host/compose.yml x-app-env gives web and worker (no password file: the
# deploy checks open no connection).
HOST_ENV = {
    "DATABASE_URL": "postgres://skiw_app@db:5432/skiw",
    "DJANGO_ALLOWED_HOSTS": "skiw.test",
    "DJANGO_BEHIND_CADDY": "1",
    **REQUIRED,
}
CHECK = ["check", "--deploy", "--fail-level", "WARNING"]
ALLOWED = {
    "security.W008": "no SECURE_SSL_REDIRECT: Caddy answers plain HTTP with a 308 to HTTPS, and "
    "the internal /readyz probes reach web over plain HTTP",
    "security.W005": "HSTS without includeSubDomains (owner Q1 (a), 2026-10-27)",
    "security.W021": "HSTS without preload (owner Q1 (a), 2026-10-27)",
}


def fired(env: dict[str, str]) -> set[str]:
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "manage.py"), *CHECK],
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(APP_DIR), **HOST_ENV, **env},
        capture_output=True,
        text=True,
        check=False,
    )
    ids = set(re.findall(r"\((security\.[EW]\d+)\)", result.stderr + result.stdout))
    assert ids or result.returncode == 0, result.stderr[-3000:]
    return ids


def test_deploy_check_fires_only_the_named_ids() -> None:
    assert fired({"DJANGO_SECRET_KEY": secrets.token_urlsafe(50)}) == set(ALLOWED)


def test_debug_on_is_caught() -> None:
    env = {"DJANGO_SECRET_KEY": secrets.token_urlsafe(50), "DJANGO_DEBUG": "1"}
    assert "security.W018" in fired(env)


def host_key_file(tmp_path: Path, size: int) -> dict[str, str]:
    key = tmp_path / "django_secret_key"
    key.write_text("v1:" + base64.b64encode(secrets.token_bytes(size)).decode() + "\n")
    return {"DJANGO_SECRET_KEY_FILE": str(key)}


def test_host_key_file_fires_w009_only_as_a_character_count(tmp_path: Path) -> None:
    # Django's W009 counts characters (50); a host key line is 32 random bytes = 44 characters.
    # Strength is enforced in bytes by config.env (MIN_KEY_BYTES), tested just below.
    assert fired(host_key_file(tmp_path, 32)) == set(ALLOWED) | {"security.W009"}


def test_host_key_file_below_32_bytes_is_refused(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "manage.py"), "check"],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(APP_DIR),
            **HOST_ENV,
            **host_key_file(tmp_path, 31),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "too short" in result.stderr
