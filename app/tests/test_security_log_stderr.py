"""`django.security` warnings and `django.request` errors reach the process's real stderr with
DEBUG off (plan M3 (a); PR 77 review residual risk, M3b), and every other logger reaches it through
the same message-free formatter (PR 103 review R1 P3 #1).

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
def chained(request):
    try:
        raise KeyError("Key (email)=(person@example.test) already exists")
    except KeyError as exc:
        raise ValueError(f"wrapped person@example.test") from exc
sys.modules["boom_urls"] = types.SimpleNamespace(
    urlpatterns=[path("boom", boom), path("chained", chained)]
)
with override_settings(ROOT_URLCONF="boom_urls"):
    client = Client(raise_request_exception=False)
    answer = client.post(
        "/boom?q=planted-query", {"field": "planted-body"}, HTTP_COOKIE="c=planted-cookie"
    )
    assert answer.status_code == 500
    assert client.get("/missing").status_code == 404
    assert client.get("/chained").status_code == 500
"""

# A failed job as procrastinate.worker logs it (ERROR with exc_info), and a plain app logger.
OTHER_LOGGERS = """
import logging
import django
django.setup()
try:
    try:
        raise KeyError("Key (email)=(person@example.test) already exists")
    except KeyError as exc:
        raise ValueError("wrapped person@example.test") from exc
except ValueError:
    logging.getLogger("procrastinate.worker").error("Job failed", exc_info=True)
logging.getLogger("skiw.probe").warning("a plain warning")
logging.getLogger("skiw.probe").info("below the level")
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


def test_a_500_logs_its_path_and_traceback_to_stderr_but_no_request_data_or_messages() -> None:
    result = run(FAIL, DJANGO_ALLOWED_HOSTS="testserver")
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stderr.splitlines()
    first, second = "\n".join(lines).split(
        "\nERROR django.request Internal Server Error: /chained\n"
    )
    first_lines = first.splitlines()
    assert first_lines[0] == "ERROR django.request Internal Server Error: /boom"
    assert first_lines[1] == "Traceback (most recent call last):"
    assert first_lines[-1] == "RuntimeError"  # the class, never the message (PR 78 R1 P2)
    assert "in boom" in first  # the frames are kept
    assert [line for line in lines if line.startswith(("ERROR", "WARNING"))] == [
        "ERROR django.request Internal Server Error: /boom",
        "ERROR django.request Internal Server Error: /chained",
    ]  # no 404
    chain = second.splitlines()
    assert chain[0] == "Traceback (most recent call last):"
    assert "KeyError" in chain
    assert "The above exception was the direct cause of the following exception:" in chain
    assert chain[-1] == "ValueError"
    assert "in chained" in second
    for planted in ("planted-query", "planted-body", "planted-cookie", "planted failure"):
        assert planted not in result.stderr
    assert "person@example.test" not in result.stderr


def test_other_loggers_reach_stderr_through_the_same_formatter() -> None:
    result = run(OTHER_LOGGERS)
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stderr.splitlines()
    assert lines[0] == "ERROR procrastinate.worker Job failed"
    assert "KeyError" in lines
    assert "The above exception was the direct cause of the following exception:" in lines
    assert lines[-2:] == ["ValueError", "WARNING skiw.probe a plain warning"]
    assert "below the level" not in result.stderr
    assert "person@example.test" not in result.stderr
