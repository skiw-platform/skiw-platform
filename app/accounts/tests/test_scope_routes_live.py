"""`scoped()` behind the real wrapper (plan row M4r-4, split M4r-4c; slice spec Decisions 9, 26,
36, flow 5.2; §7 rows "Line split bypassed on an action" and "Authorization branches on a role
name"): the test routes `scope/<line>` on `client.view` answer the ids `scoped()` gives on each
probe table, so the action line and the model line both apply, and every outcome holds from the
next request and under any role names."""

import json
import secrets
import uuid
from collections.abc import Iterator

import pytest

from accounts.access.catalogue import ACTION_LINES
from accounts.tests import scope_probe
from accounts.tests.conftest import committed_user
from accounts.tests.test_access_audit_live import Ids, app
from accounts.tests.test_access_grants_live import HOLD, UNTICK, write
from accounts.tests.test_action_wrapper_live import call
from accounts.tests.test_wrapper_roles_live import RENAME, SPARE, agency, member, role_names, tick

pytestmark = [
    pytest.mark.live,
    pytest.mark.usefixtures("live_db", "probe"),
    pytest.mark.urls("accounts.tests.urls"),
]
type Seen = dict[str, set[uuid.UUID]] | int  # the ids per probe table, or the refusal's status
NONE, INS, INV = scope_probe.TABLES
SIDE = (
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (%(side)s, %(a)s, %(root)s, 'unit', 'Side')"
)
UNASSIGN = "DELETE FROM user_role WHERE user_id = %(user_id)s"


@pytest.fixture(scope="module")
def probe() -> Iterator[None]:
    with scope_probe.table():
        yield


def rows(p: Ids, *owners: uuid.UUID | None) -> dict[uuid.UUID | None, dict[str, uuid.UUID]]:
    """One row per owner in each probe table: its id by owner, then by table."""
    with app(p["a"]) as cursor:
        return {
            o: {t: scope_probe.insert(cursor, p["a"], o, t) for t in scope_probe.TABLES}
            for o in owners
        }


def seen(cookie: str, line: str) -> Seen:
    response = call(cookie, path=f"/scope/{line}")
    if response.status_code != 200:
        return response.status_code
    return {t: set(map(uuid.UUID, ids)) for t, ids in json.loads(response.content).items()}


def of(
    made: dict[uuid.UUID | None, dict[str, uuid.UUID]], **owners: list[uuid.UUID | None]
) -> Seen:
    """The ids of `owners`' rows per table, every probe table listed."""
    return {t: {made[o][t] for o in owners.get(t, [])} for t in scope_probe.TABLES}


def test_lines_on_the_route_and_the_model_and_renaming_every_role_change_nothing() -> None:
    """Decision 36's `scoped()` half. A seeded agency: the Owner (role Owner, both lines); a mixed
    user (role r: client.view team on insurance at the unit; the spare role: client.view own on
    investment at the team); a user with no role. Same outcome on every route under the seeded,
    random and swapped names."""
    p = agency(steps=True)
    spare = {"r": p["spare"]}
    write(p, (SPARE, {}), tick("client.view", "team"), tick("client.view", "own", **spare))
    (owner_role,) = set(role_names(p)) - {p["r"], p["spare"]}
    cookies = {"owner": member(p)}
    owner = p["user_id"]
    write(p, (HOLD, {"r": owner_role, "line": "both"}))
    cookies["mixed"] = member(p, "insurance")
    mixed = p["user_id"]
    write(p, (HOLD, {**spare, "org_unit_id": p["team"], "line": "investment"}))
    cookies["none"] = member(p)
    made = rows(p, owner, mixed, p["user_id"], None)
    team, own = [owner, mixed], [mixed]
    want: dict[str, dict[str, Seen]] = {
        "owner": {
            line: of(made, **{t: list(made) for t in scope_probe.TABLES}) for line in ACTION_LINES
        },
        "mixed": {
            "insurance": of(made, **{NONE: team, INS: team}),
            "investment": of(made, **{NONE: own, INV: own}),
            "any": of(made, **{NONE: team, INS: team, INV: own}),
        },
        "none": dict.fromkeys(ACTION_LINES, 403),
    }
    names = role_names(p)
    random = {role: secrets.token_urlsafe(24) for role in names}
    swapped = {owner_role: "staff", p["r"]: "Owner", p["spare"]: "Unit manager"}
    for phase, new in (("seeded", {}), ("random", random), ("swapped", swapped)):
        write(p, *((RENAME, {"role": role, "name": name}) for role, name in new.items()))
        names |= new
        assert role_names(p) == names
        found = {u: {line: seen(c, line) for line in ACTION_LINES} for u, c in cookies.items()}
        assert (phase, found) == (phase, want)


def test_a_tick_an_assignment_and_a_move_hold_from_the_next_request() -> None:
    """On the untagged table: the agency tick becomes team; another user's unit beside the unit
    moves under it, then that user is reassigned to the root; then own; then the unassignment."""
    p = agency()
    side = uuid.uuid4()
    write(p, (SIDE, {"side": side}))
    cookie = member(p, "both")
    me, other = p["user_id"], committed_user(agency=p["a"]).id
    write(p, (HOLD, {"user_id": other, "org_unit_id": side, "line": "both"}))
    made = rows(p, me, other)

    def untagged() -> set[uuid.UUID] | int:
        found = seen(cookie, "any")
        return found if isinstance(found, int) else found[NONE]

    write(p, tick("client.view", "agency"))
    assert untagged() == {made[me][NONE], made[other][NONE]}
    write(p, (UNTICK, {}), tick("client.view", "team"))
    assert untagged() == {made[me][NONE]}
    write(
        p, ("UPDATE org_unit SET parent_id = %(org_unit_id)s WHERE id = %(side)s", {"side": side})
    )
    assert untagged() == {made[me][NONE], made[other][NONE]}
    write(
        p,
        (UNASSIGN, {"user_id": other}),
        (HOLD, {"user_id": other, "org_unit_id": p["root"], "line": "both"}),
    )
    assert untagged() == {made[me][NONE]}
    write(p, (UNTICK, {}), tick("client.view", "own"))
    assert untagged() == {made[me][NONE]}
    write(p, (UNASSIGN, {}))
    assert untagged() == 403
