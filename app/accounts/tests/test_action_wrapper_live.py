"""`authorized_action` on the real middleware, session store and database (plan M3 §4 M3d: AUTH-01
order, idle 30 min, absolute 12 h, revocation, TEN-11 variant (i), forged agency). Users are
committed and kept (TEN-03); session rows a test adds are deleted by `live_db`."""

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.db import IntegrityError, connection
from django.test import Client, RequestFactory

from accounts.auth import revoke
from accounts.auth.login import AGENCY, FACTOR, SEEN_AT, login
from accounts.revocation_model import SessionRevocation
from accounts.session import SessionStore, stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import COOKIE, Clock, assert_deleted, committed_user, row_deadline
from .test_session_hmac_live import data_of, set_data, started
from .urls import SEEN, Seen, action

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]
Row = tuple[Any, ...]


@pytest.fixture(autouse=True)
def seen() -> Iterator[list[Seen]]:
    SEEN.clear()
    yield SEEN
    SEEN.clear()


def idle() -> timedelta:
    return timedelta(minutes=settings.SKIW_SESSION_IDLE_MIN)


def signed_in(user: AppUser, cookie: str | None = None, factor: str = "passkey") -> str:
    """login() as the login view would call it, on a fresh store for `cookie`; the new cookie."""
    request = RequestFactory().get("/")
    request.session = SessionStore(cookie)
    login(request, user, factor=factor)
    request.session.save()
    return str(request.session.session_key)


def call(
    cookie: str | None,
    method: str = "POST",
    body: bytes = b"{}",
    content_type: str = "application/json",
    path: str = "/action",
    headers: dict[str, str] | None = None,
) -> "_MonkeyPatchedWSGIResponse":
    client = Client()
    if cookie is not None:
        client.cookies[COOKIE] = cookie
    return client.generic(method, path, body, content_type=content_type, headers=headers)


def assert_refused(response: "_MonkeyPatchedWSGIResponse", status: int, code: str) -> None:
    assert (response.status_code, json.loads(response.content)) == (status, {"error": code})


def saved_row(cookie: str) -> Row:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM django_session WHERE session_key = %s", [stored_key(cookie)])
        row = cursor.fetchone()
    assert row is not None
    return tuple(row)


def put_back(row: Row) -> None:
    """The attack the marker stops: skiw_app SQL re-inserts a row it saved before the logout."""
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO django_session VALUES (%s, %s, %s)", list(row))


def markers(user: AppUser) -> list[str | None]:
    with with_agency(user.agency_id):
        rows = SessionRevocation.objects.filter(user_id=user.id).order_by("revoked_at")
        return list(rows.values_list("session_key_hash", flat=True))


def set_factor(cookie: str, factor: str | None) -> None:
    """Through the store, which re-seals the row: not an attack, a session state to test."""
    store = SessionStore(cookie)
    store.update({FACTOR: factor}) if factor is not None else store.pop(FACTOR)
    store.save()


def test_a_signed_in_request_reaches_the_handler_as_the_session_says(seen: list[Seen]) -> None:
    user = committed_user()
    assert call(signed_in(user, factor="totp"), body=b'{"note": "x"}').status_code == 200
    [only] = seen
    assert (only.signed.user_id, only.signed.agency_id, only.bound) == (user.id,) + (
        user.agency_id,
    ) * 2
    assert (only.signed.factor, only.data) == ("totp", {"note": "x"})
    assert vars(action)["skiw_action"] == "test.action"  # the permission the view names


@pytest.mark.parametrize("session", ["none", "no-login"])
def test_without_a_completed_login_the_request_is_401(session: str, seen: list[Seen]) -> None:
    assert_refused(call(None if session == "none" else started()), 401, "signed-out")
    assert not seen


STEPS = ("tenant", "role", "input")
ANSWERS = {"tenant": (401, "signed-out"), "role": (403, "forbidden"), "input": (400, "invalid")}


@pytest.mark.parametrize("first", [*STEPS, None], ids=[*STEPS, "none"])
def test_the_first_failing_step_answers_and_the_handler_never_runs(
    first: str | None, seen: list[Seen]
) -> None:
    """AUTH-01: the request fails `first` and every step after it, so only the order decides."""
    failing = STEPS[STEPS.index(first) :] if first else ()
    user = committed_user("disabled" if "tenant" in failing else "active")
    cookie = signed_in(user)
    if "role" in failing:
        set_factor(cookie, None)
    response = call(cookie, body=b'{"other": 1}' if "input" in failing else b"{}")
    if first is None:
        assert response.status_code == 200 and len(seen) == 1
        return
    assert_refused(response, *ANSWERS[first])
    assert not seen
    assert (row_deadline(cookie) is None) == (first == "tenant")  # only the tenant step logs out


@pytest.mark.parametrize("status", ["invited", "disabled"])
def test_a_user_who_is_not_active_is_logged_out(status: str, seen: list[Seen]) -> None:
    response = call(signed_in(committed_user(status)))
    assert_refused(response, 401, "signed-out")
    assert_deleted(response)
    assert not seen


@pytest.mark.parametrize("factor", [None, "password", ""])
def test_a_session_without_a_known_second_factor_is_403(factor: str | None) -> None:
    cookie = signed_in(committed_user())
    set_factor(cookie, factor)
    assert_refused(call(cookie), 403, "forbidden")
    assert row_deadline(cookie) is not None  # still signed in: not a logout


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"[]", "application/json"),
        (b'"x"', "application/json"),
        (b"{", "application/json"),
        (b"\xff", "application/json"),
        (b'{"note": 1}', "application/json"),
        (b'{"note": "x"}', "application/x-www-form-urlencoded"),  # JSON, but not sent as JSON
    ],
    ids=["array", "string", "truncated", "not-utf-8", "schema", "form"],
)
def test_a_body_the_action_does_not_take_is_400(
    body: bytes, content_type: str, seen: list[Seen]
) -> None:
    response = call(signed_in(committed_user()), body=body, content_type=content_type)
    assert_refused(response, 400, "invalid")
    assert not seen


def test_a_safe_method_gives_the_schema_an_empty_body(seen: list[Seen]) -> None:
    assert call(signed_in(committed_user()), "GET", b"note=x").status_code == 200
    assert seen[0].data == {}


def test_a_forged_agency_in_body_query_or_header_is_ignored(
    agency_b: uuid.UUID, seen: list[Seen]
) -> None:
    """TEN-11: the handler's agency and the database binding are the session's."""
    user, forged = committed_user(), str(agency_b)
    response = call(
        signed_in(user),
        path=f"/action?agency_id={forged}",
        body=json.dumps({"agency_id": forged}).encode(),
        headers={"X-Skiw-Agency": forged, "X-Agency-Id": forged, "X-Tenant": forged},
    )
    assert response.status_code == 200
    assert seen[0].signed.agency_id == seen[0].bound == user.agency_id != agency_b


def test_a_row_whose_agency_was_edited_is_logged_out(agency_b: uuid.UUID, seen: list[Seen]) -> None:
    """TEN-11 variant (i) through the wrapper: re-signed with SECRET_KEY, the row fails the MAC."""
    cookie = signed_in(committed_user())
    version, mac, blob = data_of(cookie).split(":", 2)
    store = SessionStore()
    data = store.decode(blob)
    data[AGENCY] = str(agency_b)
    set_data(cookie, f"{version}:{mac}:{store.encode(data)}")
    response = call(cookie)
    assert_refused(response, 401, "signed-out")
    assert_deleted(response)
    assert not seen


def test_idle_for_the_limit_logs_out_and_marks_the_key(clock: Clock, seen: list[Seen]) -> None:
    user = committed_user()
    cookie = signed_in(user)
    clock.advance(idle() - timedelta(microseconds=1))
    assert call(cookie).status_code == 200  # just inside the limit; the idle clock restarts
    clock.advance(idle())
    copy = saved_row(cookie)
    response = call(cookie)
    assert_refused(response, 401, "idle")
    assert_deleted(response)
    assert row_deadline(cookie) is None and markers(user) == [stored_key(cookie)]
    put_back(copy)  # the saved row, with an idle clock that is fresh again at this time
    clock.advance(-idle())
    assert_refused(call(cookie), 401, "signed-out")
    assert len(seen) == 1


def test_the_idle_clock_is_written_at_most_once_a_minute(clock: Clock) -> None:
    cookie = signed_in(committed_user())
    before = data_of(cookie)
    clock.advance(timedelta(seconds=59))
    assert call(cookie).status_code == 200 and data_of(cookie) == before
    clock.advance(timedelta(seconds=1))
    assert call(cookie).status_code == 200
    assert SessionStore(cookie)[SEEN_AT] == clock.now.isoformat(timespec="microseconds")


def test_activity_does_not_move_the_absolute_deadline(clock: Clock) -> None:
    cookie = signed_in(committed_user())
    deadline = row_deadline(cookie)
    assert deadline is not None
    step = idle() - timedelta(minutes=1)
    while clock.now + step < deadline:
        clock.advance(step)
        assert call(cookie).status_code == 200 and row_deadline(cookie) == deadline
    clock.now = deadline
    assert_refused(call(cookie), 401, "signed-out")


def test_a_user_wide_marker_refuses_every_session_signed_in_at_or_before_it(clock: Clock) -> None:
    """AUTH-07 primitive. `_skiw_auth_at` is the web clock, `revoked_at` the database's; the frozen
    web clock is set from the marker's own `revoked_at`, so host clock skew cannot decide it."""
    user = committed_user()
    clock.advance(-timedelta(minutes=1))
    older = [signed_in(user), signed_in(user)]
    copies = [saved_row(cookie) for cookie in older]
    revoke.revoke_user(user.agency_id, user.id)
    with with_agency(user.agency_id):
        mark = SessionRevocation.objects.get(user_id=user.id, session_key_hash__isnull=True)
    clock.now = mark.revoked_at
    tie = signed_in(user)
    for cookie in [*older, tie]:
        assert_refused(call(cookie), 401, "signed-out")  # a tie counts as revoked
    for row in copies:
        put_back(row)
    for cookie in older:
        assert_refused(call(cookie), 401, "signed-out")
    clock.advance(timedelta(microseconds=1))
    assert call(signed_in(user)).status_code == 200


def test_a_failed_idle_marker_leaves_the_session_alive(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = committed_user()
    cookie = signed_in(user)
    clock.advance(idle())
    with monkeypatch.context() as patch:  # the key hash breaks the shape CHECK in the database
        patch.setattr(revoke, "stored_key", lambda raw: "not a key hash")
        with pytest.raises(IntegrityError):
            call(cookie)
    assert row_deadline(cookie) is not None and markers(user) == []
    clock.advance(-idle())
    assert call(cookie).status_code == 200
