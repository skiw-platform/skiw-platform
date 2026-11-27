"""AUTH-01 order on a catalogue-code route (split M4r-3c; slice spec Decision 7: the role step is
inside the step-2 `with_agency()`, after the tenant checks and the second factor, before input,
with no logout on a 403). test_action_wrapper_live pins the order on a self-service route, which
reads no grant; these pin it where the role step reads grants and step-up evidence, in both
transaction modes of `authorized_action`."""

from datetime import timedelta

import pytest

from accounts.access.catalogue import Scope
from accounts.access.grants import Grant
from accounts.auth import revoke
from accounts.tests.test_access_grants_live import write

from .conftest import Clock, row_deadline
from .test_action_wrapper_live import idle, set_factor, signed_in
from .test_session_hmac_live import data_of
from .test_wrapper_roles_live import (
    FORBIDDEN,
    STEPUP,
    agency,
    counted,
    expected,
    member,
    ok,
    outcome,
    recorded,
    tick,
    with_totp,
)
from .urls import LINED, SEEN

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]
NONE = (0, 0)  # no grant read, no step-up read


def test_session_tenant_and_factor_refusals_come_before_any_grant_or_step_up_read(
    clock: Clock,
) -> None:
    """outbox.approve `own` (step-up) held on insurance. With fresh evidence it is 200, one read of
    each (the control). No login, no second factor, a revoked user (a second holder) and an idle
    session are each refused with neither read."""
    p = agency()
    write(p, tick("outbox.approve", "own"))
    member(p, "insurance")
    factor, _ = with_totp(p)

    def fresh() -> str:
        cookie = signed_in(p["user"])
        recorded(p, cookie, factor, "outbox.approve", timedelta())
        return cookie

    grant = Grant("own", p["org_unit_id"], "insurance", "outbox.approve")
    found = [counted(fresh(), "outbox.approve"), counted(None, "outbox.approve")]
    no_factor, idle_cookie = fresh(), fresh()
    set_factor(no_factor, None)
    found.append(counted(no_factor, "outbox.approve"))
    revoked = member(p, "insurance")  # signed in on the frozen clock, before the marker
    revoke.revoke_user(p["a"], p["user_id"])
    found.append(counted(revoked, "outbox.approve"))
    clock.advance(idle())
    found.append(counted(idle_cookie, "outbox.approve"))
    assert found == [
        (ok(grant), (1, 1)),
        ((401, "signed-out"), NONE),
        (FORBIDDEN, NONE),
        ((401, "signed-out"), NONE),
        ((401, "idle"), NONE),
    ]


def test_a_role_step_refusal_leaves_the_session_as_it_was(clock: Clock) -> None:
    """Two minutes after login, past the once-a-minute idle clock write: `forbidden` (client.edit,
    not held) and `stepup-required` (outbox.approve, no evidence) neither log out nor write the
    session row; the 200 that follows (client.view) does write it, the control."""
    p = agency()
    write(p, tick("client.view", "own"), tick("outbox.approve", "own"))
    cookie = member(p, "insurance")
    clock.advance(timedelta(minutes=2))
    before = data_of(cookie)
    assert [outcome(cookie, "client.edit"), outcome(cookie, "outbox.approve")] == [
        FORBIDDEN,
        STEPUP,
    ]
    assert row_deadline(cookie) is not None and data_of(cookie) == before
    assert outcome(cookie, "client.view") == ok(Grant("own", p["org_unit_id"], "insurance", None))
    assert data_of(cookie) != before


def test_with_own_transaction_every_outcome_and_the_order_are_the_same() -> None:
    """Every test route under own/ (`own_transaction=True`: the handler runs after steps 1-4 have
    committed, in no transaction) gives the same status, code and exact `access` as under to/, for
    a user of r on insurance holding a kept, a dropped and a stepped-up grant; the same bad body is
    still 403 before 400 there."""
    p = agency()
    held: set[tuple[str, Scope]] = {("client.view", "own"), ("outbox.approve", "own")}
    held |= {("device.revoke", "own"), ("device.revoke", "agency")}
    write(p, *(tick(code, scope) for code, scope in sorted(held)))
    cookie = member(p, "insurance")
    recorded(p, cookie, with_totp(p)[0], "device.revoke", timedelta())
    found = {
        f"{code}/{line}": (outcome(cookie, code, line), outcome(cookie, code, line, route="own"))
        for code, line in LINED
    }
    assert [route for route, (default, own) in found.items() if default != own] == []
    by_code = expected(held, p, "insurance", {"device.revoke"})
    assert {code: found[f"{code}/any"][1] for code in by_code} == by_code
    bad = b'{"other": 1}'
    codes = ("client.edit", "outbox.approve", "client.view")
    found_bad = [outcome(cookie, code, body=bad, route="own") for code in codes]
    assert found_bad == [FORBIDDEN, STEPUP, (400, "invalid")]
    assert not SEEN
