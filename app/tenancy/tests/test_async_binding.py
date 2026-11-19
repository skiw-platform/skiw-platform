"""The async pool's size bound (spec D26, §8.1 bridge.async_pool_max; plan M4c-8; UNI-02, UNI-03)
and the pool async_with_agency() builds from it. No database: the pool is built closed."""

import runpy
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from tenancy import async_binding
from tests.settings_env import AUTH

pytestmark = pytest.mark.filterwarnings("ignore:'config.settings' found in sys.modules")
NAME = "SKIW_ASYNC_DB_POOL_MAX"


def load(monkeypatch: pytest.MonkeyPatch, value: str | None) -> Any:
    for name, auth in AUTH.items():
        monkeypatch.setenv(name, auth)
    if value is None:
        monkeypatch.delenv(NAME, raising=False)
    else:
        monkeypatch.setenv(NAME, value)
    return runpy.run_module("config.settings")[NAME]


def test_unset_it_is_four(monkeypatch: pytest.MonkeyPatch) -> None:
    assert load(monkeypatch, None) == 4


@pytest.mark.parametrize("value", [1, 4, 8])
def test_each_value_within_the_bounds_is_taken(value: int, monkeypatch: pytest.MonkeyPatch) -> None:
    assert load(monkeypatch, str(value)) == value


@pytest.mark.parametrize("value", ["0", "9", "", "-1", "+4", " 4", "4.0", "four", "٤"])
def test_a_value_outside_the_bounds_or_malformed_fails_closed(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ImproperlyConfigured) as raised:
        load(monkeypatch, value)
    assert str(raised.value) == f"{NAME} must be a whole number from 1 to 8"  # no echo


@pytest.mark.parametrize("size", [1, 8])
def test_the_pool_is_closed_until_used_and_sized_by_the_setting(size: int) -> None:
    with override_settings(SKIW_ASYNC_DB_POOL_MAX=size):
        pool = async_binding._new_pool()
    assert pool.closed
    assert (pool.min_size, pool.max_size) == (1, size)
    assert isinstance(pool.kwargs, dict)
    assert pool.kwargs["user"] and pool.kwargs["autocommit"] is True
