"""TEN-09 row-level tests on every registered case, so on the fixture pair (plan M4c-7b; DECISIONS
"M4c-7b"): forged tokens against real rows for all four commands, the leak test on one persistent
connection, and the query plan the policy gives [A5]. M4c-4b tested the same forgeries on
`guard.current_agency()` alone; here they meet RLS."""

import json
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from django.db import connection

from tenancy.binding import with_agency
from tenancy.tests import isolation
from tenancy.tests.isolation import COUNT, DELETE, DENIED, TOUCH, A, B, IsolationCase, refused
from tenancy.tests.test_binding_live import FORGED, current, set_token, setting

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db", "fixture_pair")]

CASES = isolation.registry()
TABLES = sorted(CASES)
OWNERS = "SELECT agency_id FROM {t} WHERE id = ANY(%s)"

Make = Callable[[str], str]


def replayed() -> Make:
    """A genuine B token, captured from B's own committed transaction."""
    with with_agency(B):
        captured = setting()
    return lambda own: captured


def fixed(make: Make) -> Callable[[], Make]:
    return lambda: make


FORGERIES: dict[str, Callable[[], Make]] = {
    **{name: fixed(make) for name, make in FORGED.items()},
    # M4c-4b's version swaps that module's own A; this one swaps this module's A.
    "b-shaped-bad-mac": fixed(lambda own: own.replace(str(A), str(B))),
    "replayed-b": replayed,
}


@contextmanager
def forged(make: Make) -> Iterator[None]:
    """Agency A's transaction, its token then overwritten with `make(A's token)`."""
    with with_agency(A):
        set_token(make(setting()))
        yield


def owners(case: IsolationCase, rows: list[uuid.UUID]) -> set[uuid.UUID]:
    with connection.cursor() as cursor:
        cursor.execute(OWNERS.format(t=case.table), [rows])
        return {agency for (agency,) in cursor.fetchall()}


@pytest.mark.usefixtures("vector_keys")
@pytest.mark.parametrize("forgery", sorted(FORGERIES))
@pytest.mark.parametrize("table", TABLES)
def test_a_forged_token_reaches_no_row(table: str, forgery: str) -> None:
    """Under a forged token, SELECT, UPDATE and DELETE reach neither B's row nor A's own (so the
    forgery did replace A's token; the check is not vacuous), and an INSERT naming B is refused.
    B's row is still there afterwards."""
    case = CASES[table]
    make = FORGERIES[forgery]()
    mine, theirs = isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)
    parents = isolation._parents(CASES, case, B)
    with forged(make):
        assert current() is None
        for row in (mine, theirs):
            assert isolation._sql(case, COUNT, [row]) == 0, f"{table}: {forgery} sees a row"
            if "UPDATE" in case.commands:
                assert isolation._sql(case, TOUCH, [row]) == 0, f"{table}: {forgery} updates"
            if "DELETE" in case.commands:
                assert isolation._sql(case, DELETE, [row]) == 0, f"{table}: {forgery} deletes"
    refusal = refused(DENIED, f"{table}: INSERT as B under {forgery}")
    with refusal, forged(make), connection.cursor() as cursor:
        case.insert(cursor, B, parents)
    with with_agency(B):
        assert isolation._sql(case, COUNT, [theirs]) == 1, f"{table}: B's row is gone"


@pytest.mark.parametrize("table", TABLES)
def test_a_plain_agency_id_setting_does_not_switch_rows(table: str) -> None:
    """`app.agency_id` set to B inside A's transaction changes nothing: A still sees only A."""
    case = CASES[table]
    rows = [isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)]
    with with_agency(A), connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.agency_id', %s, true)", [str(B)])
        assert owners(case, rows) == {A}


@pytest.mark.parametrize("table", TABLES)
def test_commit_begin_without_the_helper_reaches_no_row(table: str) -> None:
    """`COMMIT; BEGIN` inside with_agency(A) ends the bound transaction: A's own row is hidden
    and an INSERT naming A is refused."""
    case = CASES[table]
    row = isolation.make_row(CASES, case, A)
    parents = isolation._parents(CASES, case, A)

    def rebegin() -> None:
        with connection.cursor() as cursor:
            cursor.execute("COMMIT")
            cursor.execute("BEGIN")

    with with_agency(A):
        rebegin()
        assert isolation._sql(case, COUNT, [row]) == 0, f"{table}: a row is visible after BEGIN"
    with refused(DENIED, f"{table}: INSERT after COMMIT; BEGIN"), with_agency(A):
        rebegin()
        with connection.cursor() as cursor:
            case.insert(cursor, A, parents)


def backend() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return int(cursor.fetchone()[0])


@pytest.mark.parametrize("table", TABLES)
def test_two_agencies_in_turn_on_one_connection_see_only_their_own_rows(table: str) -> None:
    """The leak test: A, then B, on the same backend. Each sees only its own row, and nothing of
    the binding is left on the connection afterwards."""
    case = CASES[table]
    rows = [isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)]
    pid = backend()
    for agency in (A, B):
        with with_agency(agency):
            assert backend() == pid
            assert owners(case, rows) == {agency}, f"{table}: under {agency}, another's row"
        assert setting() == "", f"{table}: the token outlived {agency}'s transaction"
    assert current() is None
    assert backend() == pid


def plan(statement: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute(f"EXPLAIN (FORMAT JSON, VERBOSE) {statement}")
        raw = cursor.fetchone()[0]
    document = json.loads(raw) if isinstance(raw, str) else raw
    root: dict[str, Any] = document[0]["Plan"]
    return root


def own(node: dict[str, Any]) -> str:
    """A plan node's own fields as text, without its children."""
    return json.dumps({key: value for key, value in node.items() if key != "Plans"})


def nodes(
    node: dict[str, Any], in_init_plan: bool = False
) -> Iterator[tuple[dict[str, Any], bool]]:
    yield node, in_init_plan
    for child in node.get("Plans", []):
        yield from nodes(child, in_init_plan or child.get("Parent Relationship") == "InitPlan")


PLANNED = [
    (table, command)
    for table in TABLES
    for command in ("SELECT", "UPDATE", "DELETE")
    if command in CASES[table].commands
]
INDEXED = re.compile(r"\(\w+\.agency_id = \(InitPlan \d+\)\.col1\)")
STATEMENTS = {
    "SELECT": "SELECT id FROM {t}",
    "UPDATE": "UPDATE {t} SET agency_id = agency_id",
    "DELETE": "DELETE FROM {t}",
}


@pytest.mark.parametrize(("table", "command"), PLANNED)
def test_the_policy_runs_once_per_statement_and_uses_the_agency_index(
    table: str, command: str
) -> None:
    """[A5] As skiw_app under A: every `guard.current_agency()` call sits in an InitPlan (once per
    statement, not per row), and an index condition on `agency_id` takes that InitPlan's value.
    Seq scans are off, so the plan shows the index is usable, not that it is chosen at any size."""
    with with_agency(A):
        root = plan(STATEMENTS[command].format(t=table))
    found = list(nodes(root))
    calls = [inside for node, inside in found if "current_agency" in own(node)]
    assert calls and all(calls), f"{table}: guard.current_agency() outside an InitPlan ({command})"
    assert not [node for node, _ in found if node["Node Type"] == "Seq Scan"], f"{table}: seq scan"
    conditions = [node["Index Cond"] for node, _ in found if "Index Cond" in node]
    assert any(INDEXED.fullmatch(cond) for cond in conditions), f"{table}: {conditions}"
