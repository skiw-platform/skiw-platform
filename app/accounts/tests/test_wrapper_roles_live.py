"""The wrapper's role step on the real middleware, session store and database (plan row M4r-3,
split M4r-3a; slice spec Decisions 6, 7, 8, 26, flow 5.1; §7 rows "A signed-in user reaches an
action the agency's ticks do not grant" and "Line split bypassed on an action"). Grants are written
as test_access_grants_live writes them, committed in a fresh agency whose user signs in there.
Split M4r-3b: a grant that needs a step-up is kept only with fresh evidence of this session for its
purpose (Decision 7 (iv); §7 row "S action without fresh re-verification"), written by the real
POST /api/auth/stepup route or, for evidence that must be stale, by `stepup.record`.
Split M4r-3c: rename invariance (Decision 36, §7 row "Authorization branches on a role name"; the
`scoped()` half is M4r-4's) and the step-up read on a mixed-line case; the AUTH-01 order cases are
in test_wrapper_roles_order_live."""

import json
import secrets
import types
import uuid
from collections.abc import Collection
from datetime import timedelta
from typing import cast

import pytest
from django.conf import settings
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.access.catalogue import ACTION_LINES, ROUTE_CODES, SELF_SERVICE, Scope
from accounts.access.grants import QUERY, Grant
from accounts.access.tables import LINES, Line
from accounts.auth import blob, stepup, totp
from accounts.auth.wrapper import authorized_action
from accounts.factor_model import UserFactor
from accounts.session import SessionStore
from accounts.tests.test_access_audit_live import CHILD, ROLE, ROOT, TEAM, Ids, app, fresh_agency
from accounts.tests.test_access_audit_live import ids as new_ids
from accounts.tests.test_access_catalogue import SPEC_6_1
from accounts.tests.test_access_grants_live import HOLD, PAIR, UNTICK, write
from tenancy.binding import with_agency

from .conftest import committed_user
from .test_action_wrapper import DECISION_26
from .test_action_wrapper_live import call, signed_in
from .test_second_factor_live import STEP
from .urls import LINED, SEEN, handle, note_only

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
S_PAIRS = [(code, scope) for code, scope in PAIRS if SPEC[code][scope]]
STALE = timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN, seconds=1)
SPARE = ROLE.replace("%(r)s", "%(spare)s").replace("'Adviser'", "'Spare'")


def agency(steps: bool = False) -> Ids:
    """A fresh agency with a root, a unit, a team under it and role r (no tick)."""
    p = new_ids(fresh_agency(steps))
    write(p, *((sql, {}) for sql in (ROOT, CHILD, TEAM, ROLE)))
    return p


def member(p: Ids, line: Line | None = None) -> str:
    """A new active user of p's agency, p's user from now on, signed in; assigned role r at the
    unit on `line` unless None. The session cookie."""
    user = committed_user(agency=p["a"])
    p["user"], p["user_id"], p["step"] = user, user.id, STEP
    if line is not None:
        write(p, (HOLD, {"line": line}))
    return signed_in(user)


def with_totp(p: Ids) -> tuple[uuid.UUID, bytes]:
    """A TOTP factor for p's user: its id and secret."""
    factor, secret = uuid.uuid4(), totp.new_secret()
    sealed = blob.seal_factor_secret(secret, factor, p["user_id"], p["a"])
    with with_agency(p["a"]):
        UserFactor.objects.create(
            id=factor, agency_id=p["a"], user_id=p["user_id"], kind="totp", secret_ct=sealed
        )
    return factor, secret


def step_up(p: Ids, cookie: str, secret: bytes, purpose: str) -> None:
    """POST /stepup (the real POST /api/auth/stepup view) with the code of the next unused step."""
    p["step"] += 1
    body = json.dumps({"purpose": purpose, "code": totp.code(secret, p["step"])}).encode()
    with pytest.MonkeyPatch.context() as clock:
        clock.setattr(
            totp, "time", types.SimpleNamespace(time=lambda: (p["step"] + 0.5) * totp.PERIOD)
        )
        assert call(cookie, path="/stepup", body=body).status_code == 200


def recorded(p: Ids, cookie: str, factor: uuid.UUID, purpose: str, ago: timedelta) -> None:
    """Evidence written by `stepup.record` for this session, `ago` before now."""
    request = RequestFactory().post("/")
    request.session = SessionStore(cookie)
    then = types.SimpleNamespace(now=lambda: timezone.now() - ago)
    with pytest.MonkeyPatch.context() as clock, with_agency(p["a"]):
        clock.setattr(stepup, "timezone", then)
        stepup.record(request, factor, purpose)


def tick(code: str, scope: Scope, **extra: object) -> tuple[str, dict[str, object]]:
    return PAIR, {"code": code, "scope": scope, **extra}


def ok(*access: Grant) -> Outcome:
    return 200, frozenset(access)


def outcome(
    cookie: str | None, code: str, line: str = "any", body: bytes = b"{}", route: str = "to"
) -> Outcome:
    SEEN.clear()
    response = call(cookie, path=f"/{route}/{code}/{line}", body=body)
    if response.status_code != 200:
        return response.status_code, json.loads(response.content)["error"]
    [seen] = SEEN
    return 200, seen.signed.access


def outcomes(cookie: str) -> dict[str, Outcome]:
    return {code: outcome(cookie, code) for code in CODES}


def counted(
    cookie: str | None, code: str, line: str = "any", body: bytes = b"{}"
) -> tuple[Outcome, tuple[int, int]]:
    """The outcome, and how many grant reads and step-up reads the request ran."""
    with CaptureQueriesContext(connection) as captured:
        found = outcome(cookie, code, line, body)
    sql = [q["sql"] for q in captured.captured_queries]
    grant_reads = sum(q.startswith(QUERY.split(" WHERE")[0]) for q in sql)
    return found, (grant_reads, sum('FROM "auth_stepup"' in q for q in sql))


def expected(
    held: set[tuple[str, Scope]], p: Ids, line: Line, fresh: Collection[str] = ()
) -> dict[str, Outcome]:
    """Decision 7 by hand from SPEC_6_1, for one assignment at p's unit on a line that matches,
    with fresh step-up evidence for the purposes in `fresh`."""
    found: dict[str, Outcome] = {}
    for code in CODES:
        scopes = {scope for c, scope in held if c == code}
        kept = frozenset(
            Grant(s, p["org_unit_id"], line, SPEC[code][s])
            for s in scopes
            if SPEC[code][s] in {None, *fresh}
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


def test_the_seeded_owner_role_keeps_a_step_up_grant_only_for_a_freshly_stepped_up_purpose() -> (
    None
):
    """Without step-up the owner revokes their own device only; with a `device.revoke` step-up,
    any device too; with every purpose, every grant."""
    p = agency(steps=True)
    cookie = member(p)
    factor, _ = with_totp(p)
    with app(p["a"], None) as cursor:
        (owner,) = cursor.execute("SELECT id FROM role WHERE is_system").fetchone() or (None,)
    write(p, (HOLD, {"r": owner, "line": "both"}))
    own = Grant("own", p["org_unit_id"], "both", None)
    found = outcomes(cookie)
    assert found == expected(set(PAIRS), p, "both")
    assert (found["device.revoke"], found["outbox.approve"]) == (ok(own), STEPUP)
    recorded(p, cookie, factor, "device.revoke", timedelta())
    found = outcomes(cookie)
    assert found == expected(set(PAIRS), p, "both", {"device.revoke"})
    assert found["device.revoke"] == ok(
        own, Grant("agency", own.org_unit_id, "both", "device.revoke")
    )
    for purpose in stepup.PURPOSES - {"device.revoke"}:
        recorded(p, cookie, factor, purpose, timedelta())
    assert outcomes(cookie) == expected(set(PAIRS), p, "both", stepup.PURPOSES)


def test_each_step_up_pair_needs_fresh_evidence_of_this_session_for_its_own_purpose() -> None:
    """Per pair, in order: none, stale (max age + 1 s), another purpose and the right purpose in
    another session of the same user are 403 `stepup-required`; then fresh is 200 with exactly
    the grant."""
    p = agency()
    for code, scope in S_PAIRS:
        purpose = SPEC[code][scope]
        assert purpose is not None
        write(p, (UNTICK, {}), tick(code, scope))
        cookie = member(p, "insurance")
        factor, secret = with_totp(p)
        refused = [outcome(cookie, code)]
        recorded(p, cookie, factor, purpose, STALE)
        refused.append(outcome(cookie, code))
        step_up(p, cookie, secret, stepup.FACTOR_CHANGE)
        refused.append(outcome(cookie, code))
        step_up(p, signed_in(p["user"]), secret, purpose)  # another session
        refused.append(outcome(cookie, code))
        step_up(p, cookie, secret, purpose)
        grant = Grant(scope, p["org_unit_id"], "insurance", purpose)
        found = (code, scope, refused, outcome(cookie, code))
        assert found == (code, scope, [STEPUP] * 4, ok(grant))
    assert len(S_PAIRS) == 11


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
        (SPARE, {}),
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


def test_a_route_reads_grants_once_and_step_up_once_per_purpose_and_self_service_neither() -> None:
    """Grant and step-up reads per request: outbox.approve is held at two scopes (one purpose);
    on another line it is refused before any step-up read."""
    p = agency()
    cookie = member(p, "investment")
    write(
        p, tick("client.view", "own"), tick("outbox.approve", "own"), tick("outbox.approve", "team")
    )
    view = ok(Grant("own", p["org_unit_id"], "investment", None))
    calls = [("client.view", "any", view)] * 2 + [("outbox.approve", "any", STEPUP)] * 2
    calls += [("outbox.approve", "insurance", FORBIDDEN), ("auth.factors", "any", ok())]
    found = [counted(cookie, code, line) for code, line, _ in calls]
    assert [answer for answer, _ in found] == [answer for _, _, answer in calls]
    assert [reads for _, reads in found] == [(1, 0), (1, 0), (1, 1), (1, 1), (1, 0), (0, 0)]


def test_a_step_up_grant_on_another_line_is_not_read_beside_a_grant_that_matches() -> None:
    """PR 194's gap (purposes taken from every held grant, not the matching ones): device.revoke
    `agency` (step-up) through r on investment, device.revoke `own` through the spare role on
    insurance. On the insurance route only `own` matches: 200 with it, no step-up read. On `any`
    both match: the one purpose is read, `agency` is dropped and `own` kept."""
    p = agency()
    cookie = member(p, "investment")
    spare = {"r": p["spare"]}
    write(
        p,
        (SPARE, {}),
        tick("device.revoke", "agency"),
        tick("device.revoke", "own", **spare),
        (HOLD, {**spare, "line": "insurance"}),
    )
    own = ok(Grant("own", p["org_unit_id"], "insurance", None))
    found = [counted(cookie, "device.revoke", line) for line in ("insurance", "any")]
    assert found == [(own, (1, 0)), (own, (1, 1))]


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


@pytest.mark.parametrize("value", ["Insurance", "both", "", None, ["any"], {"any": "any"}, "any"])
def test_a_line_tampered_after_registration_matches_nothing(value: object) -> None:
    """The route's line changed in the view's closure at run time: outside the table, or not a
    str (an unhashable list or dict included), no grant matches (Decision 26). `any` is the
    control. A permission changed to a code outside the catalogue reaches grants(), which
    raises: no access is given."""
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


RENAME = "UPDATE role SET name = %(name)s WHERE id = %(role)s"


def role_names(p: Ids) -> dict[uuid.UUID, str]:
    with app(p["a"], None) as cursor:
        return dict(cursor.execute("SELECT id, name FROM role").fetchall())


def every_route(cookie: str) -> dict[str, Outcome]:
    return {f"{code}/{line}": outcome(cookie, code, line) for code, line in LINED}


def test_renaming_every_role_changes_no_wrapper_outcome() -> None:
    """Decision 36 (the wrapper half; `scoped()` is M4r-4's). A seeded agency's Owner role, role r
    and the spare role; three users: the Owner (both lines, `device.revoke` stepped up), a user of
    r on insurance at the unit and of the spare role on investment at the team, and a user with no
    role. Every test route gives the same exact outcome under the seeded names, under random
    names, and with r named Owner and the system role named staff (a privileged-looking name
    gained and lost)."""
    p = agency(steps=True)
    spare = {"r": p["spare"]}
    write(
        p,
        (SPARE, {}),
        tick("client.view", "own"),
        tick("outbox.approve", "own"),
        tick("client.edit", "team", **spare),
        tick("device.revoke", "own", **spare),
    )
    (owner,) = set(role_names(p)) - {p["r"], p["spare"]}
    cookies = {"owner": member(p)}
    write(p, (HOLD, {"r": owner, "line": "both"}))
    recorded(p, cookies["owner"], with_totp(p)[0], "device.revoke", timedelta())
    cookies["mixed"] = member(p, "insurance")
    write(p, (HOLD, {**spare, "org_unit_id": p["team"], "line": "investment"}))
    cookies["none"] = member(p)

    by_owner = expected(set(PAIRS), p, "both", {"device.revoke"})
    of_r = expected({("client.view", "own"), ("outbox.approve", "own")}, p, "insurance")
    held: set[tuple[str, Scope]] = {("client.edit", "team"), ("device.revoke", "own")}
    of_spare = expected(held, {**p, "org_unit_id": p["team"]}, "investment")
    by_mixed = {code: of_r[code] if of_r[code] != FORBIDDEN else of_spare[code] for code in CODES}
    view = ok(Grant("own", p["org_unit_id"], "insurance", None))
    lined = ["client.view/insurance", "client.view/investment"]
    lined += ["outbox.approve/insurance", "device.revoke/insurance"]
    want: dict[str, dict[str, Outcome]] = {
        "owner": {route: by_owner[route.split("/")[0]] for route in lined},  # both: every line
        "mixed": dict(zip(lined, [view, FORBIDDEN, STEPUP, FORBIDDEN], strict=True)),
        "none": dict.fromkeys(lined, FORBIDDEN),
    }
    nobody = expected(set(), p, "both")
    for user, codes in {"owner": by_owner, "mixed": by_mixed, "none": nobody}.items():
        want[user] |= {f"{code}/any": codes[code] for code in CODES}
    assert by_mixed["client.edit"] == ok(Grant("team", p["team"], "investment", None))

    names = {owner: "Owner", p["r"]: "Adviser", p["spare"]: "Spare"}
    random = {role: secrets.token_urlsafe(24) for role in names}
    swapped = {owner: "staff", p["r"]: "Owner", p["spare"]: "Unit manager"}
    for phase, new in (("seeded", {}), ("random", random), ("swapped", swapped)):
        write(p, *((RENAME, {"role": role, "name": name}) for role, name in new.items()))
        names |= new
        assert role_names(p) == names
        found = {user: every_route(cookie) for user, cookie in cookies.items()}
        assert (phase, found) == (phase, want)
    assert len(LINED) == 24
