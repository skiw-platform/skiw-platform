"""Session cookie attributes (spec D6, UNI-18; plan M2b). `live`: writing the session saves a
django_session row."""

import pytest
from django.test import Client

from .conftest import COOKIE, session_cookie

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]


def test_set_cookie_is_host_prefixed_secure_httponly_strict() -> None:
    response = Client().get("/write")
    morsel = session_cookie(response)
    assert morsel.key == COOKIE and len(morsel.value) == 32
    assert morsel["secure"] is True and morsel["httponly"] is True
    assert morsel["samesite"] == "Strict" and morsel["path"] == "/" and morsel["domain"] == ""
    header = morsel.OutputString()
    for part in ("; Path=/", "; Secure", "; HttpOnly", "; SameSite=Strict"):
        assert part in header
    assert "Domain" not in header
