"""`django.security` warnings and `django.request` errors reach the process's real stderr with
DEBUG off (plan M3 (a); PR 77 review residual risk, M3b).

Django's default LOGGING sends `django.*` to the console only when DEBUG is on, and 5xx records
to `mail_admins` (no ADMINS here), so without the project LOGGING the M2c SuspiciousSession
warning and every 500 traceback reached nothing in production. The subprocess has only the
variables set here: no DJANGO_DEBUG, a key made per run, no reachable database."""

import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path

from tests.settings_env import REQUIRED

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
# A URLconf made inside the subprocess only: nothing is added to config.urls.
FAIL = """
import sys, types
import django
django.setup()
from django.test import Client, override_settings
from django.urls import path
def boom(request):
    raise RuntimeError("planted failure")
sys.modules["boom_urls"] = types.SimpleNamespace(urlpatterns=[path("boom", boom)])
with override_settings(ROOT_URLCONF="boom_urls"):
    client = Client(raise_request_exception=False)
    answer = client.post(
        "/boom?q=planted-query", {"field": "planted-body"}, HTTP_COOKIE="c=planted-cookie"
    )
    assert answer.status_code == 500
    assert client.get("/missing").status_code == 404
"""


def run(code: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
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


def test_a_rejected_session_row_logs_one_line_to_stderr_without_secrets() -> None:
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    result = run(TAMPER, TENANT_SOURCE_KEY=f"v1:{key}")
    assert result.returncode == 0, result.stderr[-2000:]
    sealed = result.stdout.strip()
    mac = sealed.split(":")[1]
    lines = result.stderr.splitlines()
    assert lines == [
        "WARNING django.security.SuspiciousSession session row rejected: its MAC does not match"
    ]
    for secret in (key, mac, "signed-blob", "stored-key"):
        assert secret not in result.stderr


def test_a_500_logs_its_path_and_traceback_to_stderr_but_no_request_data() -> None:
    result = run(FAIL, DJANGO_ALLOWED_HOSTS="testserver")
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stderr.splitlines()
    assert lines[0] == "ERROR django.request Internal Server Error: /boom"
    assert lines[1] == "Traceback (most recent call last):"
    assert lines[-1] == "RuntimeError: planted failure"
    assert not [line for line in lines if line.startswith(("ERROR", "WARNING"))][1:]  # no 404
    for planted in ("planted-query", "planted-body", "planted-cookie"):
        assert planted not in result.stderr
