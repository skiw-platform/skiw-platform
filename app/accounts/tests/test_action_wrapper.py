"""`authorized_action` refuses a registration it cannot enforce (no database): a permission that is
neither a catalogue nor a self-service code, and a business line outside the three (slice spec
Decision 26; a missing line is Python's TypeError, DECISIONS M4r-2 A)."""

import inspect
from collections.abc import Mapping
from typing import Any, get_args

import pytest
from django.contrib.sessions.backends.signed_cookies import SessionStore as CookieStore
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from accounts.access.catalogue import ACTION_LINES, CATALOGUE, SELF_SERVICE, ActionLine
from accounts.auth.wrapper import Signed, authorized_action


class Equal:
    """Not text, but equal to every value and hashed as `text`: a set or tuple lookup alone
    would let it through."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return hash(self.text)


def anything(body: Mapping[str, Any]) -> Mapping[str, Any]:
    return body


def handler(request: HttpRequest, signed: Signed, data: Mapping[str, Any]) -> HttpResponse:
    """Docstring the view keeps."""
    return HttpResponse()


def test_the_view_names_its_permission_and_line_and_keeps_the_handlers_name() -> None:
    view = authorized_action(schema=anything, permission="client.view", line="insurance")(handler)
    assert (vars(view)["skiw_action"], vars(view)["skiw_line"]) == ("client.view", "insurance")
    assert (view.__name__, view.__doc__) == ("handler", "Docstring the view keeps.")


def test_an_empty_permission_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match="permission"):
        authorized_action(schema=anything, permission="", line="any")


@pytest.mark.parametrize("code", sorted(CATALOGUE.keys() | SELF_SERVICE))
@pytest.mark.parametrize("line", ACTION_LINES)
def test_every_catalogue_and_self_service_code_registers_on_every_line(
    code: str, line: ActionLine
) -> None:
    view = authorized_action(schema=anything, permission=code, line=line)(handler)
    assert (vars(view)["skiw_action"], vars(view)["skiw_line"]) == (code, line)


@pytest.mark.parametrize(
    "code",
    ["clients.view", "Client.view", "client.view ", "auth.*", "test.action", "auth", "client"],
)
def test_a_code_outside_the_catalogue_and_self_service_is_refused(code: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="unknown permission"):
        authorized_action(schema=anything, permission=code, line="any")


@pytest.mark.parametrize(
    "value", [None, 1, ("auth.logout",), ["auth.logout"], {"auth.logout"}, Equal("auth.logout")]
)
def test_a_permission_that_is_not_text_is_refused(value: object) -> None:
    # ignore[arg-type]: a non-`str` permission the types forbid; the runtime check is the subject.
    with pytest.raises(ImproperlyConfigured, match="unknown permission"):
        authorized_action(schema=anything, permission=value, line="any")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "line",
    [
        "Insurance",
        "ANY",
        "both",
        "",
        " any",
        "any ",
        None,
        1,
        ("any",),
        ["any"],
        {"any"},
        Equal("any"),
    ],
)
def test_a_line_outside_the_three_is_refused(line: object) -> None:
    # ignore[arg-type]: a value outside `ActionLine`; the runtime check is the subject.
    with pytest.raises(ImproperlyConfigured, match="line must be one of"):
        authorized_action(
            schema=anything,
            permission="auth.logout",
            line=line,  # type: ignore[arg-type]
        )


def test_a_missing_line_is_a_type_error() -> None:
    # ignore[call-arg]: the omission mypy refuses, made anyway to pin what happens at run time.
    with pytest.raises(TypeError, match="line"):
        authorized_action(schema=anything, permission="auth.logout")  # type: ignore[call-arg]


def test_line_is_keyword_only_with_no_default() -> None:
    parameter = inspect.signature(authorized_action).parameters["line"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_the_three_lines_are_the_types_and_nothing_else() -> None:
    assert ACTION_LINES == get_args(ActionLine) == ("insurance", "investment", "any")


def test_an_async_handler_is_refused() -> None:
    async def later(request: HttpRequest, signed: Signed, data: object) -> HttpResponse:
        return HttpResponse()

    with pytest.raises(ImproperlyConfigured, match="sync handlers only"):
        # The registration the types already forbid, made anyway: the runtime check is the subject.
        decorate = authorized_action(schema=anything, permission="auth.logout", line="any")
        decorate(later)  # type: ignore[arg-type]


def test_another_session_store_is_refused() -> None:
    request = RequestFactory().post("/")
    request.session = CookieStore()
    view = authorized_action(schema=anything, permission="auth.logout", line="any")(handler)
    with pytest.raises(TypeError, match="accounts session store"):
        view(request)
