"""The interim auth values fail closed at settings import (owner Q6 (a), plan M3b; UNI-02, UNI-03,
UNI-16). Settings run in-process with runpy, so the bounds tested are the ones settings.py
passes, without a subprocess per case; the error text is checked, so no value is echoed."""

import runpy
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured

from tests.settings_env import AUTH, AUTH_BOUNDS

# Malformed whatever the bounds; "\u0665" is ARABIC-INDIC DIGIT FIVE, which int() accepts.
# runpy warns that config.settings is already imported; the copy it runs is separate.
pytestmark = pytest.mark.filterwarnings("ignore:'config.settings' found in sys.modules")
MALFORMED = ["", "-1", "+5", " 5", "5 ", "5.0", "1_0", "0x10", "\u0665", "five", "1e2", "007a"]


def load(monkeypatch: pytest.MonkeyPatch, **values: str) -> dict[str, Any]:
    for name, value in {**AUTH, **values}.items():
        monkeypatch.setenv(name, value)
    return runpy.run_module("config.settings")


def test_the_configured_values_load(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = load(monkeypatch)
    assert {name: str(loaded[name]) for name in AUTH} == AUTH


@pytest.mark.parametrize("name", AUTH_BOUNDS)
def test_each_bound_is_inclusive(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for value in AUTH_BOUNDS[name]:
        assert load(monkeypatch, **{name: str(value)})[name] == value


# One step weaker than the spec or owner value, written out here, not taken from AUTH_BOUNDS, so a
# bound widened in settings.py and AUTH_BOUNDS together still fails (PR 78 P2).
WEAKER_THAN_SPEC = {
    "SKIW_ARGON2_MEMORY_KIB": "65535",  # T5: 64 MiB
    "SKIW_ARGON2_TIME_COST": "2",  # T5: t=3
    "SKIW_AUTH_FAILS_PER_ACCOUNT": "6",  # Flow 5.1: 5 per account
    "SKIW_AUTH_FAILS_PER_IP": "21",  # Flow 5.1: 20 per IP
    "SKIW_AUTH_WINDOW_MIN": "14",  # Flow 5.1: per 15 min
    "SKIW_AUTH_LOCK_AFTER": "11",  # Flow 5.1: after 10 failures
    "SKIW_AUTH_LOCK_MIN": "29",  # Flow 5.1: for 30 min
    "SKIW_STEPUP_MAX_AGE_MIN": "6",  # T5, §8.1: ≤ 5 min
    "SKIW_TOTP_SKEW_STEPS": "2",  # Flow 5.1: ±1 step
    "SKIW_ENROL_LINK_MIN": "31",  # owner Q5 (a): 30 min
}


@pytest.mark.parametrize("name", WEAKER_THAN_SPEC)
def test_a_value_weaker_than_the_spec_fails_closed(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ImproperlyConfigured, match=f"^{name} must be a whole number"):
        load(monkeypatch, **{name: WEAKER_THAN_SPEC[name]})


@pytest.mark.parametrize("name", AUTH_BOUNDS)
@pytest.mark.parametrize("case", ["below", "above", "missing", *MALFORMED])
def test_a_value_outside_the_bounds_missing_or_malformed_fails_closed(
    name: str, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    low, high = AUTH_BOUNDS[name]
    value = {"below": str(low - 1), "above": str(high + 1)}.get(case, case)
    with pytest.raises(ImproperlyConfigured) as raised:
        if case == "missing":
            monkeypatch.delenv(name)
            runpy.run_module("config.settings")
        else:
            load(monkeypatch, **{name: value})
    assert str(raised.value) == f"{name} must be a whole number from {low} to {high}"  # no echo
