import pytest
from django.test import Client


def test_healthz_returns_ok_without_database_access() -> None:
    # No django_db mark: pytest-django raises if the view touches the database.
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_healthz_rejects_non_get(method: str) -> None:
    response = getattr(Client(), method)("/healthz")
    assert response.status_code == 405


def test_healthz_body_is_exactly_ok_as_plain_text() -> None:
    # The external uptime ping (UptimeRobot, amendment 2026-10-24) checks this body as is.
    response = Client().get("/healthz")
    assert response["Content-Type"] == "text/plain"
    assert response.content.decode("ascii") == "ok"
    assert "Set-Cookie" not in response and not response.cookies
