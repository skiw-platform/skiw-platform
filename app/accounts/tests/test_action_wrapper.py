"""`authorized_action` refuses a registration it cannot enforce (no database)."""

from collections.abc import Mapping
from typing import Any

import pytest
from django.contrib.sessions.backends.signed_cookies import SessionStore as CookieStore
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from accounts.auth.wrapper import Signed, authorized_action


def anything(body: Mapping[str, Any]) -> Mapping[str, Any]:
    return body


def handler(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    """Docstring the view keeps."""
    return HttpResponse()


def test_the_view_names_its_permission_and_keeps_the_handlers_name() -> None:
    view = authorized_action(schema=anything, permission="clients.view")(handler)
    assert vars(view)["skiw_action"] == "clients.view"
    assert (view.__name__, view.__doc__) == ("handler", "Docstring the view keeps.")


def test_an_empty_permission_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match="permission"):
        authorized_action(schema=anything, permission="")


def test_an_async_handler_is_refused() -> None:
    async def later(request: HttpRequest, signed: Signed, data: object) -> HttpResponse:
        return HttpResponse()

    with pytest.raises(ImproperlyConfigured, match="sync handlers only"):
        # The registration the types already forbid, made anyway: the runtime check is the subject.
        authorized_action(schema=anything, permission="x")(later)  # type: ignore[arg-type]


def test_another_session_store_is_refused() -> None:
    request = RequestFactory().post("/")
    request.session = CookieStore()
    view = authorized_action(schema=anything, permission="x")(handler)
    with pytest.raises(TypeError, match="accounts session store"):
        view(request)
