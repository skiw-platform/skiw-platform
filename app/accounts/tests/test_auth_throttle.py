"""Client IP rule, throttle keys and the event writer's input checks (plan M3c). No database: each
check here runs before any query."""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Iterator

import pytest
from django.test import RequestFactory
from pytest_django import Settings

from accounts.auth import throttle
from accounts.auth.events import record_event


@pytest.fixture(autouse=True)
def source_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("TENANT_SOURCE_KEY_FILE", raising=False)
    monkeypatch.setenv(
        "TENANT_SOURCE_KEY", "v1:" + base64.b64encode(secrets.token_bytes(32)).decode()
    )
    yield


def ip(behind_caddy: bool, settings: Settings, **meta: str) -> str:
    settings.SKIW_BEHIND_CADDY = behind_caddy
    request = RequestFactory().get("/")
    request.META.update(meta)
    return throttle.client_ip(request)


def test_a_client_sent_forwarded_for_is_ignored_without_caddy(settings: Settings) -> None:
    meta = {"REMOTE_ADDR": "192.0.2.7", "HTTP_X_FORWARDED_FOR": "198.51.100.9"}
    assert ip(False, settings, **meta) == "192.0.2.7"
    assert ip(True, settings, **meta) == "198.51.100.9"
    assert ip(True, settings, HTTP_X_FORWARDED_FOR="2001:DB8:0:0::1") == "2001:db8::1"


@pytest.mark.parametrize("value", ["", " ", "198.51.100.9, 192.0.2.7", "unknown", "1", "::g"])
def test_a_malformed_address_counts_under_one_fixed_key(settings: Settings, value: str) -> None:
    assert ip(True, settings, REMOTE_ADDR="192.0.2.7", HTTP_X_FORWARDED_FOR=value) == "malformed"
    assert ip(False, settings, REMOTE_ADDR=value, HTTP_X_FORWARDED_FOR="192.0.2.7") == "malformed"
    assert ip(True, settings, REMOTE_ADDR="192.0.2.7") == "malformed"  # never REMOTE_ADDR


def test_keys_follow_the_normalised_email_and_keep_the_labels_apart() -> None:
    keys = throttle.keys("adviser@example.test", "192.0.2.7")
    assert throttle.keys("  \uff21DVISER@Example.TEST ", "192.0.2.7") == keys  # NFKC, strip, lower
    assert throttle.keys("other@example.test", "192.0.2.7").account != keys.account
    assert len({keys.account, keys.ip, keys.lock, throttle.keys("192.0.2.7", "x").account}) == 4
    assert all(len(key) == 32 for key in (keys.account, keys.ip, keys.lock))


def test_keys_are_hmacs_under_the_newest_key_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """So a tenant_source_key rotation starts every counter afresh (DECISIONS M3c-2)."""
    newest, older = secrets.token_bytes(32), base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("TENANT_SOURCE_KEY", f"v1:{older}\nv2:{base64.b64encode(newest).decode()}")
    expected = hmac.new(newest, b"skiw-throttle-account-v1adviser@example.test", hashlib.sha256)
    assert throttle.keys("adviser@example.test", "192.0.2.7").account == expected.digest()


@pytest.mark.parametrize(
    ("kind", "details"),
    [
        ("login.unknown", {}),
        ("account.locked", {"email": "adviser@example.test"}),
        ("account.locked", {"consecutive": 1.5}),
        ("account.locked", {"Consecutive": 10}),
    ],
)
def test_an_event_takes_listed_kinds_and_number_details_only(
    kind: str, details: dict[str, int]
) -> None:
    with pytest.raises(ValueError, match="security event"):
        record_event(kind, None, None, details)
