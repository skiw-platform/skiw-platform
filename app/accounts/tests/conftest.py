import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import Morsel
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.contrib.sessions import middleware
from django.db import connection
from django.http.response import HttpResponseBase
from django.utils import timezone
from pytest_django import DjangoDbBlocker

from accounts.session import stored_key
from accounts.source_key import require_key

COOKIE = "__Host-skiw_session"


@pytest.fixture(autouse=True)
def fresh_source_key() -> Iterator[None]:
    """require_key() reads the key once per process; a test that changes it must not leak."""
    require_key.cache_clear()
    yield
    require_key.cache_clear()


@pytest.fixture
def security_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """django.security does not propagate to the root logger (settings LOGGING), where caplog
    listens, so its handler is attached to django.security for the test."""
    logger = logging.getLogger("django.security")
    logger.addHandler(caplog.handler)
    yield caplog
    logger.removeHandler(caplog.handler)


@pytest.fixture(scope="session")
def django_db_setup() -> None:
    """Use the database `make migrate` prepared as skiw_migrator; skiw_app may neither create a
    test database nor TRUNCATE, so tests commit for real and remove their own rows."""


def rows() -> dict[str, datetime]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT session_key, expire_date FROM django_session")
        return dict(cursor.fetchall())


@pytest.fixture
def live_db(django_db_setup: None, django_db_blocker: DjangoDbBlocker) -> Iterator[None]:
    """The real Django connection (skiw_app) in autocommit; rows a test adds are deleted after."""
    with django_db_blocker.unblock():
        before = set(rows())
        yield
        added = list(set(rows()) - before)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM django_session WHERE session_key = ANY(%s)", [added])


@dataclass
class Clock:
    now: datetime

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Freeze timezone.now() and the middleware's time.time() (it builds the cookie Expires from
    it) at a whole second, so cookie and row deadlines compare exactly."""
    frozen = Clock(timezone.now().replace(microsecond=0))
    monkeypatch.setattr(timezone, "now", lambda: frozen.now)
    monkeypatch.setattr(middleware, "time", SimpleNamespace(time=lambda: frozen.now.timestamp()))
    return frozen


def session_cookie(response: HttpResponseBase) -> Morsel[str]:
    return response.cookies[COOKIE]


def cookie_expires(response: HttpResponseBase) -> datetime:
    return parsedate_to_datetime(str(session_cookie(response)["expires"]))


def row_deadline(cookie: str) -> datetime | None:
    return rows().get(stored_key(cookie))


def absolute() -> timedelta:
    return timedelta(hours=settings.SKIW_SESSION_ABSOLUTE_H)


def assert_deleted(response: HttpResponseBase) -> None:
    """The cookie delete a browser honours for a `__Host-` name: Secure, Path=/, no Domain."""
    morsel = session_cookie(response)
    assert morsel.value == "" and morsel["max-age"] == 0
    assert morsel["secure"] is True and morsel["path"] == "/" and morsel["domain"] == ""
