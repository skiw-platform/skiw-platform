"""`scoped()` as skiw_app (plan row M4r-4, M4r-4b; slice spec Decisions 9, 27, flow 5.2; §7 rows "A
role-holder reads outside their book/subtree" and "Subtree query never ends or widens on a corrupt
tree"): each registered case's generated visibility check, then the walk on `scope_probe`. A
corrupt tree is planted by the owner with the tree guard off, committed (skiw_app reads only
committed rows), and undone the same way."""

import os
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.access.scope import ORG_MAX_DEPTH, ScopeIntegrityError, scoped
from accounts.tests import scope_probe
from accounts.tests.scope_harness import HOLD, UNIT, grant, registry, signed, tree, visibility
from accounts.tests.scope_probe import ScopeProbe
from accounts.tests.test_access_audit_live import app, fresh_agency
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db", "probe")]

CASES = registry()
MOVE = "UPDATE org_unit SET parent_id = %s WHERE id = %s"


@pytest.fixture(scope="module")
def probe() -> Iterator[None]:
    with scope_probe.table():
        yield


@pytest.mark.parametrize("model", CASES, ids=lambda model: model._meta.label)
def test_visibility(model: type) -> None:
    visibility(CASES[model])


@contextmanager
def planted(sql: str, params: list[object], undo: list[object]) -> Iterator[None]:
    """`sql` committed by the owner with the tree guard off (FORCE lifted for the write and its
    event), and the move `undo` after the test in the same way."""

    def commit(statement: str, values: list[object]) -> None:
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
            conn.execute("SELECT set_config('skiw.operator', 'test-operator', true)")
            for table in ("org_unit", "security_event"):
                conn.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            conn.execute("ALTER TABLE org_unit DISABLE TRIGGER org_unit_tree_guard")
            conn.execute(statement, values)
            conn.execute("ALTER TABLE org_unit ENABLE TRIGGER org_unit_tree_guard")
            for table in ("org_unit", "security_event"):
                conn.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    commit(sql, params)
    try:
        yield
    finally:
        commit(MOVE, undo)


def owners(agency: uuid.UUID, user: uuid.UUID, *units: uuid.UUID) -> set[uuid.UUID | None]:
    """The probe rows' owners that team grants at `units` see, under a statement timeout."""
    with with_agency(agency), connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '10s'")
        access = [grant("team", unit) for unit in units]
        return set(
            scoped(ScopeProbe, signed(user, agency, *access)).values_list(
                ScopeProbe.SCOPE_OWNER, flat=True
            )
        )


def one_row_each(agency: uuid.UUID, ids: dict[str, uuid.UUID], *people: str) -> None:
    with app(agency) as cursor:
        for person in people:
            scope_probe.insert(cursor, agency, ids[person])


def test_one_walk_for_every_team_grant_none_without_and_no_role_table() -> None:
    a = fresh_agency()
    ids = tree(a)
    access = [grant("own", ids["X"]), grant("team", ids["X"]), grant("team", ids["V"])]
    with with_agency(a), CaptureQueriesContext(connection) as made:
        scoped(ScopeProbe, signed(ids["me"], a, *access[:1]))
        assert len(made) == 0
        rows = scoped(ScopeProbe, signed(ids["me"], a, *access))
        assert len(made) == 1
        list(rows)
    assert not [q for q in made if re.search(r"\brole\b|role_permission", q["sql"])]


def test_each_call_reads_the_tree_again() -> None:
    a = fresh_agency()
    ids = tree(a)
    one_row_each(a, ids, "me", "other")
    assert owners(a, ids["me"], ids["X"]) == {ids["me"]}
    with app(a) as cursor:
        cursor.execute(HOLD, [a, ids["other"], ids["role"], ids["X1"]])
    assert owners(a, ids["me"], ids["X"]) == {ids["me"], ids["other"]}


def test_a_planted_cycle_raises_logs_only_ids_and_ends(
    security_log: pytest.LogCaptureFixture,
) -> None:
    """X moved under its child X1: a walk from X finds the cycle; U, its old parent, no longer
    reaches X, so its subtree narrows."""
    a = fresh_agency()
    ids = tree(a)
    one_row_each(a, ids, "me", "mate", "sib", "boss")
    with planted(MOVE, [ids["X1"], ids["X"]], [ids["U"], ids["X"]]):
        with pytest.raises(ScopeIntegrityError, match=r"^cycle$"):
            owners(a, ids["me"], ids["Y"], ids["X"])
        assert owners(a, ids["me"], ids["U"]) == {ids["sib"], ids["boss"]}
    assert [r.getMessage() for r in security_log.records if r.name == "django.security.scope"] == [
        f"scope integrity: cycle, agency {a}, unit {ids['X']}"
    ]
    assert owners(a, ids["me"], ids["U"]) == {ids["me"], ids["mate"], ids["sib"], ids["boss"]}


def test_32_levels_are_walked_and_a_33rd_raises(security_log: pytest.LogCaptureFixture) -> None:
    a = fresh_agency()
    ids = tree(a)
    chain = [ids["R"]]
    with app(a) as cursor:
        for _ in range(ORG_MAX_DEPTH - 1):
            chain.append(uuid.uuid4())
            cursor.execute(UNIT, [chain[-1], a, chain[-2], "unit"])
        cursor.execute(HOLD, [a, ids["me"], ids["role"], chain[-1]])
    one_row_each(a, ids, "me")
    assert owners(a, ids["sib"], chain[0]) == {ids["me"]}
    deeper = uuid.uuid4()
    with planted(UNIT, [deeper, a, chain[-1], "unit"], [ids["R"], deeper]):
        assert owners(a, ids["sib"], chain[1]) == {ids["me"]}
        with pytest.raises(ScopeIntegrityError, match=r"^depth$"):
            owners(a, ids["sib"], chain[0])
    assert [r.getMessage() for r in security_log.records if r.name == "django.security.scope"] == [
        f"scope integrity: depth, agency {a}, unit {chain[0]}"
    ]


def test_a_unit_rls_cannot_see_raises() -> None:
    a, b = fresh_agency(), fresh_agency()
    ids, elsewhere = tree(a), tree(b)
    for unit in (elsewhere["X"], uuid.uuid4()):
        with pytest.raises(ScopeIntegrityError, match=r"^anchor$"):
            owners(a, ids["me"], ids["X"], unit)
    with with_agency(b), pytest.raises(ScopeIntegrityError, match=r"^anchor$"):
        scoped(ScopeProbe, signed(ids["me"], a, grant("team", ids["X"])))
