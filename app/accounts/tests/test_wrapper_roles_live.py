"""The wrapper's role step on the real middleware, session store and database (plan row M4r-3,
split M4r-3a; slice spec Decisions 6, 7, 8, 26, flow 5.1; §7 rows "A signed-in user reaches an
action the agency's ticks do not grant" and "Line split bypassed on an action"). Grants are written
as test_access_grants_live writes them, committed in a fresh agency whose user signs in there.
Until M4r-3b checks step-up, every grant that needs one is dropped, so a code held only through
such grants is 403 `stepup-required` here."""

import json
import types
from typing import cast

import pytest
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from accounts.access.catalogue import ACTION_LINES, ROUTE_CODES, SELF_SERVICE, Scope
from accounts.access.grants import QUERY, Grant
from accounts.access.tables import LINES, Line
from accounts.auth.wrapper import authorized_action
from accounts.session import SessionStore
from accounts.tests.test_access_audit_live import CHILD, ROLE, ROOT, TEAM, Ids, app, fresh_agency
from accounts.tests.test_access_audit_live import ids as new_ids
from accounts.tests.test_access_catalogue import SPEC_6_1
from accounts.tests.test_access_grants_live import HOLD, PAIR, UNTICK, write

from .conftest import committed_user
from .test_action_wrapper import DECISION_26
from .test_action_wrapper_live import call, signed_in
from .urls import SEEN, handle, note_only

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db"),
    pytest.mark.urls("accounts.tests.urls"),
]
type Outcome = tuple[int, str | frozenset[Grant]]  # 200 and the handler's access, or the 403 code
SPEC = cast(dict[str, dict[Scope, str | None]], SPEC_6_1)
PAIRS = sorted((code, scope) for code, scopes in SPEC.items() for scope in scopes)
CODES = sorted(ROUTE_CODES)
FORBIDDEN, STEPUP = (403, "forbidden"), (403, "stepup-required")


def agency(steps: bool = False) -> Ids:
    """A fresh agency with a root, a unit, a team under it and role r (no tick)."""
    p = new_ids(fresh_agency(steps))
    write(p, *((sql, {}) for sql in (ROOT, CHILD, TEAM, ROLE)))
    return p


def member(p: Ids, line: Line | None = None) -> str:
    """A new active user of p's agency, p's user from now on, signed in; assigned role r at the
    unit on `line` unless None. The session cookie."""
    user = committed_user(agency=p["a"])
    p["user_id"] = user.id
    if line is not None:
        write(p, (HOLD, {"line": line}))
    return signed_in(user)


def tick(code: str, scope: Scope, **extra: object) -> tuple[str, dict[str, object]]:
    return PAIR, {"code": code, "scope": scope, **extra}


def ok(*access: Grant) -> Outcome:
    return 200, frozenset(access)


def outcome(cookie: str, code: str, line: str = "any", body: bytes = b"{}") -> Outcome:
    SEEN.clear()
    response = call(cookie, path=f"/to/{code}/{line}", body=body)
    if response.status_code != 200:
        return response.status_code, json.loads(response.content)["error"]
    [seen] = SEEN
    return 200, seen.signed.access


def outcomes(cookie: str) -> dict[str, Outcome]:
    return {code: outcome(cookie, code) for code in CODES}


def expected(held: set[tuple[str, Scope]], p: Ids, line: Line) -> dict[str, Outcome]:
    """Decision 7 by hand from SPEC_6_1, for one assignment at p's unit on a line that matches."""
    found: dict[str, Outcome] = {}
    for code in CODES:
        scopes = {scope for c, scope in held if c == code}
        kept = frozenset(
            Grant(s, p["org_unit_id"], line, None) for s in scopes if not SPEC[code][s]
        )
        found[code] = (
            (200, kept) if kept or code in SELF_SERVICE else STEPUP if scopes else FORBIDDEN
        )
    return found


@pytest.mark.parametrize("alone", [True, False], ids=["each-pair-alone", "all-but-each-pair"])
def test_each_pair_alone_and_every_pair_but_one_give_exact_outcomes_on_every_code(
    alone: bool,
) -> None:
    """One session throughout: each tick and untick holds from the next request (AUTH-12)."""
    p = agency()
    cookie = member(p, "insurance")
    for pair in PAIRS:
        held = {pair} if alone else set(PAIRS) - {pair}
        write(p, (UNTICK, {}), *(tick(code, scope) for code, scope in sorted(held)))
        assert (pair, outcomes(cookie)) == (pair, expected(held, p, "insurance"))
    assert len(PAIRS) == 31 and len(CODES) == 20


def test_no_role_and_an_empty_role_give_only_self_service() -> None:
    p = agency(steps=True)  # the seeded Owner role holds every pair; this user does not hold it
    cookie = member(p)
    nothing = expected(set(), p, "both")
    assert outcomes(cookie) == nothing
    write(p, (HOLD, {"line": "both"}))  # role r, with no tick
    assert outcomes(cookie) == nothing


def test_the_seeded_owner_role_without_step_up_keeps_every_grant_that_needs_none() -> None:
    p = agency(steps=True)
    cookie = member(p)
    with app(p["a"], None) as cursor:
        (owner,) = cursor.execute("SELECT id FROM role WHERE is_system").fetchone() or (None,)
    write(p, (HOLD, {"r": owner, "line": "both"}))
    found = outcomes(cookie)
    assert found == expected(set(PAIRS), p, "both")
    assert found["device.revoke"] == ok(Grant("own", p["org_unit_id"], "both", None))
    assert found["outbox.approve"] == STEPUP


def test_the_nine_line_pairs_and_a_step_up_grant_on_another_line() -> None:
    """client.view own opens exactly the Decision 26 pairs; outbox.approve own (step-up) is
    `stepup-required` on a matching line and `forbidden` on another: a line refusal never asks
    for a step-up."""
    p = agency()
    write(p, tick("client.view", "own"), tick("outbox.approve", "own"))
    found = {}
    for held in LINES:
        cookie = member(p, held)
        grant = ok(Grant("own", p["org_unit_id"], held, None))
        for line in ACTION_LINES:
            match = (held, line) in DECISION_26
            found[held, line] = outcome(cookie, "client.view", line)
            assert found[held, line] == (grant if match else FORBIDDEN)
        for line in ("insurance", "any"):
            match = (held, line) in DECISION_26
            assert outcome(cookie, "outbox.approve", line) == (STEPUP if match else FORBIDDEN)
    assert len(found) == 9


def test_mixed_assignments_keep_only_the_grants_on_the_actions_line() -> None:
    """Decision 8: r (client.view team) at the team on insurance, the spare role (client.view own)
    at the unit on investment. Each grant keeps its own unit and line."""
    p = agency()
    cookie = member(p)
    spare = {"r": p["spare"]}
    write(
        p,
        (ROLE.replace("%(r)s", "%(spare)s").replace("'Adviser'", "'Spare'"), {}),
        tick("client.view", "team"),
        (HOLD, {"org_unit_id": p["team"], "line": "insurance"}),
        tick("client.view", "own", **spare),
        (HOLD, {**spare, "line": "investment"}),
    )
    x = Grant("team", p["team"], "insurance", None)
    y = Grant("own", p["org_unit_id"], "investment", None)
    found = [outcome(cookie, "client.view", line) for line in ACTION_LINES]
    assert found == [ok(x), ok(y), ok(x, y)]


def test_an_assignment_a_scope_change_and_an_unassignment_hold_from_the_next_request() -> None:
    p = agency()
    cookie = member(p)
    write(p, tick("client.view", "own"))
    assert outcome(cookie, "client.view") == FORBIDDEN  # ticked, not assigned
    write(p, (HOLD, {"line": "insurance"}))
    own = ok(Grant("own", p["org_unit_id"], "insurance", None))
    assert outcome(cookie, "client.view") == own
    write(p, (UNTICK, {}), tick("client.view", "agency"))
    assert outcome(cookie, "client.view") == ok(
        Grant("agency", p["org_unit_id"], "insurance", None)
    )
    write(p, ("DELETE FROM user_role WHERE user_id = %(user_id)s", {}))
    assert outcome(cookie, "client.view") == FORBIDDEN


def test_a_catalogue_route_reads_grants_once_per_request_and_self_service_never() -> None:
    p = agency()
    cookie = member(p, "insurance")
    write(p, tick("client.view", "own"))
    reads = []
    for code in ("client.view", "client.view", "auth.factors"):
        with CaptureQueriesContext(connection) as captured:
            assert outcome(cookie, code)[0] == 200
        query = QUERY.split(" WHERE")[0]
        reads.append(sum(q["sql"].startswith(query) for q in captured.captured_queries))
    assert reads == [1, 1, 0]


def test_the_role_step_answers_before_the_input_is_read() -> None:
    """AUTH-01: the same bad body is 403 without a grant and with a step-up grant only, and 400
    (the control) with a grant the step keeps; the handler never runs."""
    p = agency()
    cookie = member(p, "insurance")
    write(p, tick("client.view", "own"), tick("outbox.approve", "own"))
    bad = b'{"other": 1}'
    found = [outcome(cookie, c, body=bad) for c in ("client.edit", "outbox.approve", "client.view")]
    assert found == [FORBIDDEN, STEPUP, (400, "invalid")]
    assert not SEEN


@pytest.mark.parametrize("value", ["Insurance", "both", "", None, "any"])
def test_a_line_tampered_after_registration_matches_nothing(value: object) -> None:
    """The route's line changed in the view's closure at run time: outside the table, no grant
    matches (Decision 26). `any` is the control. A permission changed to a code outside the
    catalogue reaches grants(), which raises: no access is given."""
    p = agency()
    cookie = member(p, "both")
    write(p, tick("client.view", "own"))
    decorate = authorized_action(schema=note_only, permission="client.view", line="investment")
    view = cast(types.FunctionType, decorate(handle))
    cells = dict(zip(view.__code__.co_freevars, view.__closure__ or (), strict=True))
    cells["line"].cell_contents = value
    request = RequestFactory().post("/", b"{}", content_type="application/json")
    request.session = SessionStore(cookie)
    response = view(request)
    assert (response.status_code, response.content) == (
        (200, b"done") if value == "any" else (403, b'{"error": "forbidden"}')
    )
    cells["line"].cell_contents, cells["permission"].cell_contents = "any", "auth.other"
    with pytest.raises(ValueError, match="catalogue code"):
        view(request)
