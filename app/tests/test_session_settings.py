"""SKIW_SESSION_ABSOLUTE_H / SKIW_SESSION_IDLE_MIN fail closed (spec D6, §8.1; owner Q2 (a);
UNI-02, UNI-03, UNI-16)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env
from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parent.parent
BOUNDS = {"SKIW_SESSION_ABSOLUTE_H": (1, 72), "SKIW_SESSION_IDLE_MIN": (1, 1440)}
# "\u0665" is ARABIC-INDIC DIGIT FIVE, which int() accepts.
BAD = ["0", "-1", "+5", " 5", "5 ", "5.0", "1_0", "0x10", "\u0665", "five", "99999", "1e2", "007a"]


@pytest.mark.parametrize("name", BOUNDS)
def test_values_inside_the_bounds_pass(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    low, high = BOUNDS[name]
    for value in (low, 12, high):
        monkeypatch.setenv(name, str(value))
        assert env.bounded_int(name, low, high) == value


@pytest.mark.parametrize("name", BOUNDS)
@pytest.mark.parametrize("value", [None, "", *BAD])
def test_missing_or_bad_values_fail_closed_without_echo(
    name: str, value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    low, high = BOUNDS[name]
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(ImproperlyConfigured) as raised:
        env.bounded_int(name, low, high)
    assert str(raised.value) == f"{name} must be a whole number from {low} to {high}"  # no echo


@pytest.mark.parametrize(
    ("name", "value"), [("SKIW_SESSION_ABSOLUTE_H", "73"), ("SKIW_SESSION_IDLE_MIN", "1441")]
)
def test_just_above_the_bound_fails(name: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ImproperlyConfigured):
        env.bounded_int(name, *BOUNDS[name])


@pytest.mark.parametrize("name", BOUNDS)
def test_settings_import_refuses_a_bad_value_and_never_prints_it(name: str) -> None:
    good = {
        "DJANGO_SECRET_KEY": "test-only-not-a-secret",
        "DATABASE_URL": "postgres://u:p@localhost:5432/db",
        **REQUIRED,
    }
    marker = "planted-session-value"
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(APP_DIR), **good, name: marker},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert name in result.stderr and "ImproperlyConfigured" in result.stderr
    assert marker not in result.stderr + result.stdout
