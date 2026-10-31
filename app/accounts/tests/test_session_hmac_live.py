"""A `django_session` row with edited data, data copied from another row, or an edited deadline
is rejected (logged out) (spec §9 M2, §4.1 `django_session`, TEN-11; plan M2c). Rows are changed
by SQL as skiw_app; every request runs the real middleware and store, sync and async."""

import base64
import logging
import secrets
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from django.db import connection
from django.http.response import HttpResponseBase
from django.test import AsyncClient, Client

from accounts.session import SessionStore, stored_key
from accounts.source_key import require_key

from .conftest import (
    COOKIE,
    Clock,
    absolute,
    assert_deleted,
    cookie_expires,
    row_deadline,
    session_cookie,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedASGIResponse, _MonkeyPatchedWSGIResponse

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]
LOGGER = "django.security.SuspiciousSession"


def data_of(cookie: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT session_data FROM django_session WHERE session_key = %s", [stored_key(cookie)]
        )
        row = cursor.fetchone()
    assert row is not None
    return str(row[0])


def set_data(cookie: str, data: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE django_session SET session_data = %s WHERE session_key = %s",
            [data, stored_key(cookie)],
        )


def get(
    path: str, cookie: str | None = None, asynchronous: bool = False
) -> "_MonkeyPatchedWSGIResponse | _MonkeyPatchedASGIResponse":
    if asynchronous:
        async_client = AsyncClient()
        if cookie is not None:
            async_client.cookies[COOKIE] = cookie
        response: _MonkeyPatchedWSGIResponse | _MonkeyPatchedASGIResponse
        response = async_to_sync(async_client.get)(path)
    else:
        client = Client()
        if cookie is not None:
            client.cookies[COOKIE] = cookie
        response = client.get(path)
    assert response.status_code == 200
    return response


def started() -> str:
    cookie = session_cookie(get("/write")).value
    assert get("/read", cookie).content == b"set"  # positive control: a genuine row verifies
    return cookie


def assert_rejected(cookie: str, asynchronous: bool) -> HttpResponseBase:
    """Logged out: empty session and a cookie delete; a write then mints a new key and leaves
    the rejected row byte-for-byte as it was (never updated in place, plan M2c Risk 2)."""
    tampered = data_of(cookie)
    response = get("/read", cookie, asynchronous)
    assert response.content == b""
    assert_deleted(response)
    written = get("/awrite" if asynchronous else "/write", cookie, asynchronous)
    fresh = session_cookie(written)
    assert fresh.value not in ("", cookie)
    assert data_of(cookie) == tampered and data_of(fresh.value) != tampered
    return written


both = pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])


@both
def test_edited_data_with_a_valid_django_signature_is_rejected(asynchronous: bool) -> None:
    cookie = started()
    version, mac, _ = data_of(cookie).split(":", 2)
    store = SessionStore()
    forged = store.encode({"probe": "forged", "_auth_user_id": "1"})
    assert store.decode(forged) == {"probe": "forged", "_auth_user_id": "1"}  # SECRET_KEY-valid
    set_data(cookie, f"{version}:{mac}:{forged}")
    assert_rejected(cookie, asynchronous)


@both
def test_data_copied_from_another_row_is_rejected(asynchronous: bool) -> None:
    victim, other = started(), started()
    set_data(victim, data_of(other))
    assert_rejected(victim, asynchronous)


@both
@pytest.mark.parametrize("shift", ["1 hour", "-1 microsecond"])
def test_an_edited_expire_date_is_rejected(clock: Clock, asynchronous: bool, shift: str) -> None:
    cookie = started()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE django_session SET expire_date = expire_date + %s::interval"
            " WHERE session_key = %s",
            [shift, stored_key(cookie)],
        )
    clock.advance(timedelta(minutes=1))
    written = assert_rejected(cookie, asynchronous)
    # The new session gets its own deadline; the rejected row's (edited) one is never taken.
    fresh = session_cookie(written).value
    assert row_deadline(fresh) == cookie_expires(written) == clock.now + absolute()


MALFORMED: dict[str, Callable[[str], str]] = {
    "unlisted version": lambda d: "v9" + d[d.index(":") :],
    "leading zero": lambda d: "v0" + d[1:],
    "non-ASCII digit": lambda d: "v" + chr(0xFF11) + d[d.index(":") :],
    "no version": lambda d: d[d.index(":") + 1 :],
    "MAC changed": lambda d: d[:4] + ("A" if d[4] != "A" else "B") + d[5:],
    "MAC cut short": lambda d: d[:4] + d[5:],
    "no blob": lambda d: d[: d.index(":", 3) + 1],
    "plain Django data": lambda d: d.split(":", 2)[2],
    "empty": lambda d: "",
}


@both
@pytest.mark.parametrize("change", MALFORMED)
def test_malformed_or_unlisted_session_data_is_rejected(asynchronous: bool, change: str) -> None:
    cookie = started()
    set_data(cookie, MALFORMED[change](data_of(cookie)))
    assert_rejected(cookie, asynchronous)


def test_saves_and_key_rotation_keep_a_valid_mac() -> None:
    cookie = started()
    for _ in range(3):
        get("/write", cookie)
    assert get("/read", cookie).content == b"set"
    store = SessionStore(cookie)
    store.cycle_key()
    assert SessionStore(store.session_key)["probe"] == store["probe"]


def key_line(version: int) -> str:
    return f"v{version}:" + base64.b64encode(secrets.token_bytes(32)).decode()


@both
def test_an_old_version_verifies_while_listed_and_is_rejected_once_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asynchronous: bool
) -> None:
    v1, v2 = key_line(1), key_line(2)
    key_file = tmp_path / "tenant_source_key"
    monkeypatch.delenv("TENANT_SOURCE_KEY", raising=False)
    monkeypatch.setenv("TENANT_SOURCE_KEY_FILE", str(key_file))

    def listing(*lines: str) -> None:
        key_file.write_text("".join(f"{line}\n" for line in lines))
        require_key.cache_clear()  # what a restart of web does

    listing(v1)
    old, renewed = started(), started()
    assert data_of(old).startswith("v1:")
    listing(v2, v1)
    assert get("/read", old, asynchronous).content == b"set"
    get("/write", renewed)
    assert data_of(renewed).startswith("v2:")  # the newest version signs every save
    listing(v2)
    assert get("/read", renewed, asynchronous).content == b"set"
    assert_rejected(old, asynchronous)


def test_the_warning_carries_no_key_cookie_mac_or_session_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cookie = started()
    version, mac, blob = data_of(cookie).split(":", 2)
    probe = str(SessionStore().decode(blob)["probe"])
    set_data(cookie, f"{version}:{mac}:{SessionStore().encode({'probe': probe, 'role': 'owner'})}")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert get("/read", cookie).content == b""
    records = [r for r in caplog.records if r.name == LOGGER]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    text = caplog.text + records[0].getMessage()
    keys = [base64.b64encode(raw).decode() for _, raw in require_key()]
    for secret in (cookie, stored_key(cookie), mac, blob, probe, *keys):
        assert secret not in text
