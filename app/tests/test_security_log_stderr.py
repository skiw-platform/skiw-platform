"""A `django.security` warning reaches the process's real stderr with DEBUG off (plan M3 (a)).

Django's default LOGGING sends `django.*` to the console only when DEBUG is on, so without the
project LOGGING the M2c SuspiciousSession warning reached nothing in production. The subprocess
has only the variables set here: no DJANGO_DEBUG, a key made per run, no reachable database."""

import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TAMPER = """
import django
django.setup()
from datetime import UTC, datetime
from accounts.source_key import seal, unseal
when = datetime(2026, 10, 31, tzinfo=UTC)
sealed = seal("stored-key", when, "signed-blob")
assert unseal("stored-key", when, sealed[:-1] + "X") is None
print(sealed)
"""


def test_a_rejected_session_row_logs_one_line_to_stderr_without_secrets() -> None:
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    result = subprocess.run(
        [sys.executable, "-c", TAMPER],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(APP_DIR),
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": "test-only-not-a-secret",
            "DATABASE_URL": "postgres://u:p@127.0.0.1:9/db",
            "SKIW_SESSION_ABSOLUTE_H": "12",
            "SKIW_SESSION_IDLE_MIN": "30",
            "TENANT_SOURCE_KEY": f"v1:{key}",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    sealed = result.stdout.strip()
    mac = sealed.split(":")[1]
    lines = result.stderr.splitlines()
    assert lines == [
        "WARNING django.security.SuspiciousSession session row rejected: its MAC does not match"
    ]
    for secret in (key, mac, "signed-blob", "stored-key"):
        assert secret not in result.stderr
