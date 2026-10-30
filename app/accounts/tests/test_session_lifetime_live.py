"""The absolute session lifetime does not slide (spec D6, §8.1 `session.absolute_h`; owner Q2 (a);
plan M2b "Absolute lifetime that cannot slide"). Frozen clock; rows are real, as skiw_app."""

from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import alogin, login
from django.test import AsyncClient, Client, RequestFactory

from accounts.session import SessionStore

from .conftest import Clock, absolute, assert_deleted, cookie_expires, row_deadline, session_cookie

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]


def get(path: str, client: Client | None = None) -> tuple[Client, str]:
    client = client or Client()
    response = client.get(path)
    assert response.status_code == 200
    return client, session_cookie(response).value


@pytest.mark.parametrize("path", ["/write", "/awrite"])
def test_first_response_cookie_expires_equals_the_new_row(clock: Clock, path: str) -> None:
    # The middleware asks for the expiry before it saves, so no row exists yet at that moment.
    client = async_to_sync(AsyncClient().get) if path == "/awrite" else Client().get
    response = client(path)
    cookie = session_cookie(response)
    assert cookie_expires(response) == row_deadline(cookie.value) == clock.now + absolute()
    assert cookie["max-age"] == absolute().total_seconds()


def test_saves_before_the_deadline_keep_it_and_after_it_the_session_is_gone(clock: Clock) -> None:
    client, cookie = get("/write")
    deadline = clock.now + absolute()
    for _ in range(71):  # a save every 10 minutes up to T0 + 11 h 50 min
        clock.advance(timedelta(minutes=10))
        response = client.get("/write")
        assert cookie_expires(response) == row_deadline(cookie) == deadline
    clock.advance(timedelta(minutes=9))  # T0 + 11 h 59 min
    response = client.get("/write")
    assert cookie_expires(response) == row_deadline(cookie) == deadline
    clock.advance(timedelta(minutes=1, seconds=1))
    response = client.get("/read")
    assert response.content == b""
    assert_deleted(response)


def test_an_expired_row_loads_as_absent(clock: Clock) -> None:
    _, cookie = get("/write")
    clock.advance(absolute())
    store = SessionStore(cookie)
    assert store.load() == {} and store.session_key is None


def started_at_t0(clock: Clock) -> str:
    _, cookie = get("/write")
    clock.advance(timedelta(hours=11))
    return cookie


def test_cycle_key_preserves_the_deadline(clock: Clock) -> None:
    cookie = started_at_t0(clock)
    deadline = clock.now - timedelta(hours=11) + absolute()
    store = SessionStore(cookie)
    for _ in range(10):
        old = store.session_key
        store.cycle_key()
        assert store.session_key != old
        assert row_deadline(str(store.session_key)) == deadline and row_deadline(str(old)) is None


def test_acycle_key_preserves_the_deadline(clock: Clock) -> None:
    cookie = started_at_t0(clock)
    deadline = clock.now - timedelta(hours=11) + absolute()
    store = SessionStore(cookie)

    async def rotate() -> None:
        for _ in range(10):
            await store.acycle_key()

    async_to_sync(rotate)()
    assert row_deadline(str(store.session_key)) == deadline and row_deadline(cookie) is None


class StubUser:
    """Just what login()/alogin() read when given a backend: pk and _meta.pk.value_to_string."""

    pk = 7
    _meta = SimpleNamespace(pk=SimpleNamespace(value_to_string=lambda user: str(user.pk)))


USER = cast("AbstractBaseUser", StubUser())  # UNI-01: django.contrib.auth is not installed (M3)
BACKEND = "django.contrib.auth.backends.ModelBackend"


def sync_login(store: SessionStore) -> None:
    request = RequestFactory().get("/")
    request.session = store
    store.start_new_lifetime()
    login(request, USER, backend=BACKEND)  # SESSION_KEY in session (lazy load), then cycle_key
    store.save()


def async_login(store: SessionStore) -> None:
    request = RequestFactory().get("/")
    request.session = store

    async def run() -> None:
        await store.astart_new_lifetime()
        await alogin(request, USER, backend=BACKEND)
        await store.asave()

    async_to_sync(run)()


@pytest.mark.parametrize("log_in", [sync_login, async_login])
@pytest.mark.parametrize("loaded", [False, True])
def test_start_new_lifetime_then_login_gives_a_fresh_deadline(
    clock: Clock, log_in: Callable[[SessionStore], None], loaded: bool
) -> None:
    cookie = started_at_t0(clock)
    store = SessionStore(cookie)  # fresh: no session cache, as the middleware makes it
    if loaded:
        assert store.get("probe")
    log_in(store)
    assert store.session_key != cookie and row_deadline(cookie) is None
    assert row_deadline(str(store.session_key)) == clock.now + absolute()  # T0 + 23 h
    assert store.get_expiry_date() == clock.now + absolute()


def test_flush_starts_the_next_session_with_a_fresh_deadline(clock: Clock) -> None:
    store = SessionStore(started_at_t0(clock))
    assert store.get("probe")
    store.flush()
    assert store.session_key is None
    store["probe"] = "new"
    store.save()
    assert row_deadline(str(store.session_key)) == clock.now + absolute()


def test_the_deadline_cannot_be_moved(clock: Clock) -> None:
    store = SessionStore(started_at_t0(clock))
    for value in (None, 0, 3600, timedelta(hours=1), clock.now + absolute()):
        with pytest.raises(NotImplementedError):
            store.set_expiry(value)
        with pytest.raises(NotImplementedError):
            async_to_sync(store.aset_expiry)(value)
    with pytest.raises(TypeError):
        store.get_expiry_date(expiry=3600)


def test_clear_on_an_unread_session_is_refused(clock: Clock) -> None:
    """clear() skips the load; the save after it would give the old row a fresh deadline."""
    cookie = started_at_t0(clock)
    with pytest.raises(RuntimeError):
        SessionStore(cookie).clear()
    store = SessionStore(cookie)
    assert store.get("probe")
    store.clear()
    store.save()
    assert row_deadline(cookie) == clock.now - timedelta(hours=11) + absolute()
