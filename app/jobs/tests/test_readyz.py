from collections.abc import Callable

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connection
from django.test import Client

from jobs import startup


def raises(exc: Exception) -> Callable[[], None]:
    def fail() -> None:
        raise exc

    return fail


@pytest.mark.parametrize(
    ("role", "pending", "ready"),
    [("skiw_app", [], True), ("skiw_app", ["jobs.0001"], False), ("skiw_migrator", [], False)],
)
def test_ready_only_as_skiw_app_with_nothing_pending(
    monkeypatch: pytest.MonkeyPatch, role: str, pending: list[str], ready: bool
) -> None:
    class Cursor:
        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def execute(self, sql: str) -> None:
            assert sql == "SELECT current_user"

        def fetchone(self) -> tuple[str]:
            return (role,)

    monkeypatch.setattr(connection, "cursor", Cursor)
    monkeypatch.setattr(startup, "pending_migrations", lambda: pending)
    assert startup.database_ready() is ready


@pytest.mark.parametrize("exc", [OperationalError("down"), ImproperlyConfigured("unreadable")])
def test_not_ready_when_the_database_fails(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    monkeypatch.setattr(connection, "cursor", raises(exc))
    assert startup.database_ready() is False


@pytest.mark.parametrize(
    ("ready", "status", "body"), [(True, 200, b"ok"), (False, 503, b"not ready")]
)
def test_readyz_body_says_only_ok_or_not_ready(
    monkeypatch: pytest.MonkeyPatch, ready: bool, status: int, body: bytes
) -> None:
    monkeypatch.setattr("jobs.views.database_ready", lambda: ready)
    response = Client().get("/readyz")
    assert (response.status_code, response.content) == (status, body)


def test_readyz_rejects_post() -> None:
    assert Client().post("/readyz").status_code == 405


@pytest.mark.live
@pytest.mark.usefixtures("live_db")
def test_readyz_is_200_when_fully_migrated() -> None:
    response = Client().get("/readyz")
    assert (response.status_code, response.content) == (200, b"ok")


@pytest.mark.live
@pytest.mark.usefixtures("live_db", "unapplied_jobs_migration")
def test_readyz_is_503_with_an_unapplied_migration() -> None:
    response = Client().get("/readyz")
    assert (response.status_code, response.content) == (503, b"not ready")
