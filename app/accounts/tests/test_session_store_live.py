"""The stored session key is not the cookie value (spec §9 M2, §4.1 `django_session`, D6; plan
M2b). Rows are real, as skiw_app; queries are read back with CaptureQueriesContext."""

import hashlib

import pytest
from asgiref.sync import async_to_sync
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from accounts.session import SessionStore, stored_key

from .conftest import COOKIE, assert_deleted, rows, session_cookie

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]


def saved() -> SessionStore:
    store = SessionStore()
    store["probe"] = "x"
    store.save()
    return store


def test_the_primary_key_is_sha256_of_the_cookie() -> None:
    cookie = str(saved().session_key)
    assert len(cookie) == 32
    assert stored_key(cookie) == hashlib.sha256(cookie.encode()).hexdigest()
    assert stored_key(cookie) in rows() and cookie not in rows()


def test_an_http_session_cookie_is_never_a_stored_key() -> None:
    cookie = session_cookie(Client().get("/write")).value
    assert stored_key(cookie) in rows() and cookie not in rows()


def sync_lifecycle(issued: list[str]) -> None:
    store = saved()
    issued.append(str(store.session_key))
    again = SessionStore(issued[-1])
    assert again["probe"] == "x"
    again["probe"] = "y"
    again.save()
    again.cycle_key()
    issued.append(str(again.session_key))
    assert again.exists(issued[-1])
    again.delete()
    third = saved()
    issued.append(str(third.session_key))
    third.flush()


async def async_lifecycle(issued: list[str]) -> None:
    store = SessionStore()
    await store.aset("probe", "x")
    await store.asave()
    issued.append(str(store.session_key))
    again = SessionStore(issued[-1])
    assert await again.aget("probe") == "x"
    await again.aset("probe", "y")
    await again.asave()
    await again.acycle_key()
    issued.append(str(again.session_key))
    assert await again.aexists(issued[-1])
    await again.adelete()
    third = SessionStore()
    await third.aset("probe", "z")
    await third.asave()
    issued.append(str(third.session_key))
    await third.aflush()


@pytest.mark.parametrize("asynchronous", [False, True])
def test_the_raw_cookie_never_reaches_sql(asynchronous: bool) -> None:
    issued: list[str] = []
    with CaptureQueriesContext(connection) as queries:
        if asynchronous:  # async_to_sync: the ORM calls run on this thread's connection
            async_to_sync(async_lifecycle)(issued)
        else:
            sync_lifecycle(issued)
    sql = [query["sql"] for query in queries]
    # Positive control: the queries were captured, with their parameters inlined.
    for cookie in issued:
        assert any(stored_key(cookie) in text for text in sql)
        assert not [text for text in sql if cookie in text]
    assert len(issued) == 3 and not set(map(stored_key, issued)) & set(rows())


def test_a_dumped_key_is_not_a_usable_cookie() -> None:
    dumped = stored_key(str(saved().session_key))
    for cookie in (dumped, dumped[:32]):  # the stored key, and one cut to a well-formed length
        client = Client()
        client.cookies[COOKIE] = cookie
        response = client.get("/read")
        assert response.content == b""
        assert_deleted(response)


def test_cycle_key_leaves_only_the_new_row_and_flush_none() -> None:
    store = saved()
    old = str(store.session_key)
    store.cycle_key()
    assert stored_key(old) not in rows() and stored_key(str(store.session_key)) in rows()
    new = str(store.session_key)
    store.flush()
    assert stored_key(new) not in rows() and store.session_key is None


@pytest.mark.parametrize(
    "cookie",
    ["", "a" * 31, "a" * 33, "A" * 32, "a" * 31 + "-", "é" * 32, "a" * 31 + "\x00", "0" * 64],
)
def test_a_malformed_cookie_loads_nothing_and_runs_no_query(cookie: str) -> None:
    store = SessionStore(cookie)
    with CaptureQueriesContext(connection) as queries:
        assert store.get("probe") is None
        store.delete()
        store.delete(cookie)
    assert store.session_key is None and len(queries) == 0
    with CaptureQueriesContext(connection) as queries:
        # A raw header: the client's cookie jar refuses the control character.
        response = Client().get("/read", HTTP_COOKIE=f"{COOKIE}={cookie}")
    assert response.content == b"" and len(queries) == 0


def test_app_role_holds_exactly_the_session_grants() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.privilege_type FROM pg_class c, aclexplode(c.relacl) a"
            " WHERE c.oid = 'django_session'::regclass AND a.grantee = 'skiw_app'::regrole"
        )
        privileges = sorted(privilege for (privilege,) in cursor.fetchall())
        cursor.execute(
            "SELECT count(*) FROM pg_attribute"
            " WHERE attrelid = 'django_session'::regclass AND attacl IS NOT NULL"
        )
        column_grants = cursor.fetchone()
    assert privileges == ["DELETE", "INSERT", "SELECT", "UPDATE"]  # no TRUNCATE, nothing twice
    assert column_grants == (0,)
