"""Grant evaluation as skiw_app (plan row M4r-2a; slice spec Decisions 6, 7 (ii)-(iii), 8, 36; §7
rows "A signed-in user reaches an action the agency's ticks do not grant", "Revoked assignment or
unticked permission still works" and "Authorization branches on a role name"). Rows are written
as test_access_audit_live writes them: committed for real in a fresh agency, with an operator."""

import json
import uuid
from collections.abc import Mapping
from typing import cast

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test.utils import CaptureQueriesContext

from accounts.access import grants as module
from accounts.access.catalogue import CATALOGUE, SELF_SERVICE, Scope
from accounts.access.grants import QUERY, Grant, grants
from accounts.access.tables import LINES, Line
from accounts.tests.test_access_audit_live import (
    ASSIGN,
    CHILD,
    ROLE,
    ROOT,
    USER,
    Ids,
    app,
    build,
    fresh_agency,
    ids,
)
from accounts.tests.test_access_catalogue import SPEC_6_1

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

PAIR = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (gen_random_uuid(), %(a)s, %(r)s, %(code)s, %(scope)s)"
)
UNTICK = "DELETE FROM role_permission WHERE role_id = %(r)s"
HOLD = ASSIGN.replace("%(ura)s", "gen_random_uuid()").replace("'insurance'", "%(line)s")


def write(p: Ids, *statements: tuple[str, Mapping[str, object]]) -> None:
    with app(p["a"]) as cursor:
        for sql, extra in statements:
            cursor.execute(sql, {**p, **extra})


def seen(p: Ids, user: uuid.UUID | None = None) -> dict[str, frozenset[Grant]]:
    """Every catalogue code's grants for `user` (default p's), in one new transaction."""
    with app(p["a"], None):
        return {code: grants(user or p["user_id"], code) for code in CATALOGUE}


def only(code: str, *found: Grant) -> dict[str, frozenset[Grant]]:
    return {c: frozenset(found if c == code else ()) for c in CATALOGUE}


NOTHING = only("client.view")


@pytest.mark.parametrize("line", LINES)
def test_each_catalogue_pair_on_each_line_grants_exactly_itself(line: Line) -> None:
    """One tick at a time on a role assigned at the unit: that code alone gives exactly one grant,
    with the step-up of slice spec §6.1 (copied by hand into SPEC_6_1, not read from the code)."""
    p = ids(fresh_agency())
    write(p, *((sql, {}) for sql in (ROOT, CHILD, USER, ROLE)), (HOLD, {"line": line}))
    assert seen(p) == NOTHING
    spec = cast(dict[str, dict[Scope, str | None]], SPEC_6_1)
    pairs = [(code, scope, s) for code, scopes in spec.items() for scope, s in scopes.items()]
    for code, scope, stepup in pairs:
        write(p, (PAIR, {"code": code, "scope": scope}))
        expected = Grant(scope, p["org_unit_id"], line, stepup)
        assert (code, scope, seen(p)) == (code, scope, only(code, expected))
        write(p, (UNTICK, {}))
    assert len(pairs) == 31


def test_a_user_with_no_role_or_an_unticked_role_gets_nothing_for_every_code() -> None:
    p = ids(fresh_agency(steps=True))  # the seeded Owner role holds every pair; p has none of it
    write(p, (USER, {}))
    assert seen(p) == NOTHING
    write(p, *((sql, {}) for sql in (ROOT, CHILD, ROLE)), (HOLD, {"line": "both"}))
    assert seen(p) == NOTHING


def test_another_users_another_codes_and_another_agencys_rows_never_appear() -> None:
    """p holds client.view own; q (same agency) client.view agency; client.edit team is ticked
    on p's role; agency b has a user with client.view agency."""
    p, b = ids(fresh_agency()), ids(fresh_agency())
    build(p)  # p's role r: client.view own, assigned at the unit, line insurance
    q = {"user_id": uuid.uuid4(), "r": p["spare"], "line": "investment"}
    q["email"] = f"{q['user_id']}@audit.test"
    write(p, (PAIR, {"code": "client.edit", "scope": "team"}), (USER, q), (HOLD, q))
    write(p, (PAIR, q | {"code": "client.view", "scope": "agency"}))
    build(b)
    write(b, (PAIR, {"code": "client.view", "scope": "agency"}))
    own = Grant("own", p["org_unit_id"], "insurance", None)
    team = Grant("team", p["org_unit_id"], "insurance", None)
    assert seen(p) == only("client.view", own) | {"client.edit": frozenset({team})}
    assert seen(p, q["user_id"])["client.view"] == {
        Grant("agency", p["org_unit_id"], "investment", None)
    }
    assert seen(p, b["user_id"]) == NOTHING
    assert seen(b, p["user_id"]) == NOTHING
    assert seen(b)["client.view"] == {
        Grant("own", b["org_unit_id"], "insurance", None),
        Grant("agency", b["org_unit_id"], "insurance", None),
    }


def test_several_assignments_give_separate_grants() -> None:
    """Decision 8: role r at the unit (insurance) and the spare role at the team (investment),
    both with client.view, and r again at the team: one grant per (assignment, tick)."""
    p = ids(fresh_agency())
    build(p)
    spare = {"r": p["spare"], "org_unit_id": p["team"], "line": "investment"}
    write(p, (PAIR, spare | {"code": "client.view", "scope": "team"}), (HOLD, spare))
    write(p, (HOLD, {"org_unit_id": p["team"], "line": "both"}))
    assert seen(p)["client.view"] == {
        Grant("own", p["org_unit_id"], "insurance", None),
        Grant("team", p["team"], "investment", None),
        Grant("own", p["team"], "both", None),
    }


def test_a_tick_an_untick_and_an_unassignment_are_seen_by_the_next_call() -> None:
    p = ids(fresh_agency())
    build(p)
    own = Grant("own", p["org_unit_id"], "insurance", None)
    assert seen(p)["client.view"] == {own}
    write(p, (PAIR, {"code": "client.view", "scope": "agency"}))
    assert seen(p)["client.view"] == {own, Grant("agency", p["org_unit_id"], "insurance", None)}
    write(p, ("DELETE FROM role_permission WHERE role_id = %(r)s AND scope = 'agency'", {}))
    assert seen(p)["client.view"] == {own}
    write(p, ("DELETE FROM user_role WHERE id = %(ura)s", {}))
    assert seen(p) == NOTHING


def test_a_stored_pair_missing_from_the_code_catalogue_is_dropped_and_logged(
    monkeypatch: pytest.MonkeyPatch, security_log: pytest.LogCaptureFixture
) -> None:
    """The FK to `permission` keeps such a pair out of the table, so the code catalogue loses
    device.revoke own instead."""
    p = ids(fresh_agency())
    build(p)
    write(p, *((PAIR, {"code": "device.revoke", "scope": s}) for s in ("own", "agency")))
    monkeypatch.setattr(
        module, "CATALOGUE", {**CATALOGUE, "device.revoke": {"agency": "device.revoke"}}
    )
    with app(p["a"], None):
        found = grants(p["user_id"], "device.revoke")
    assert found == {Grant("agency", p["org_unit_id"], "insurance", "device.revoke")}
    [record] = [r for r in security_log.records if r.name.startswith("django.security")]
    assert (record.name, record.levelname) == ("django.security.grants", "WARNING")
    assert record.getMessage() == "grant dropped: device.revoke own is not a catalogue pair"


def relations(sql: str, params: list[str | uuid.UUID]) -> set[str]:
    """The relations the plan of `sql` reads, from EXPLAIN (FORMAT JSON)."""
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
        (plan,) = cursor.fetchone()
    names, stack = set[str](), [json.loads(plan) if isinstance(plan, str) else plan]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            names |= {node["Relation Name"]} if "Relation Name" in node else set()
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return names


def test_one_query_reads_user_role_and_role_permission_only() -> None:
    p = ids(fresh_agency())
    build(p)
    with app(p["a"], None), CaptureQueriesContext(connection) as captured:
        grants(p["user_id"], "client.view")
    [query] = captured.captured_queries
    with app(p["a"], None):
        assert relations(query["sql"], []) == {"user_role", "role_permission"}
        # Negative control: the same check sees a join to `role`.
        joined = QUERY.replace(
            " JOIN", " JOIN role r ON r.agency_id = ur.agency_id AND r.id = ur.role_id JOIN", 1
        )
        assert "role" in relations(joined, [p["user_id"], "client.view"])


@pytest.mark.parametrize("code", ["client.delete", "", "CLIENT.VIEW", *sorted(SELF_SERVICE)])
def test_a_code_outside_the_catalogue_is_refused(code: str) -> None:
    with transaction.atomic(), pytest.raises(ValueError, match="catalogue code"):
        grants(uuid.uuid4(), code)


def test_outside_an_atomic_block_it_is_refused_and_without_a_binding_it_sees_nothing() -> None:
    p = ids(fresh_agency())
    build(p)
    with pytest.raises(TransactionManagementError):
        grants(p["user_id"], "client.view")
    with app(None, None):
        assert grants(p["user_id"], "client.view") == frozenset()
