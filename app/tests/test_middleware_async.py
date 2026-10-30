"""Spec D26 (1): the bridge long-poll is async, so every MIDDLEWARE entry must be async-capable."""

import pytest
from django.conf import settings
from django.utils.module_loading import import_string


def test_middleware_is_not_empty() -> None:
    assert settings.MIDDLEWARE


@pytest.mark.parametrize("path", settings.MIDDLEWARE)
def test_middleware_is_async_capable(path: str) -> None:
    assert import_string(path).async_capable is True
