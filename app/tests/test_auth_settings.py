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
