"""The TEN-08 isolation harness (spec §4.2; plan M4c-7a; DECISIONS "M4c-7a"). Apps list tenant
tables as `CASES` in `<app>/tests/isolation_cases.py`; a case's `insert(cursor, agency_id, parents)`
adds one row and returns its id, `parents` mapping each composite-FK column to a parent row id."""

import importlib
import re
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from django.apps import apps
from django.db import DatabaseError, connection, transaction
from django.db.backends.utils import CursorWrapper

from tenancy.binding import with_agency

A = uuid.UUID("aaaaaaaa-0000-4000-8000-0000000000a7")
B = uuid.UUID("bbbbbbbb-0000-4000-8000-0000000000b7")
COMMANDS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})
DENIED, NO_PARENT = "42501", "23503"  # insufficient_privilege (grant or RLS), foreign_key_violation
QUALIFIED = re.compile(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*")
PROJECT = Path(__file__).resolve().parents[2]
COUNT = "SELECT count(*) FROM {t} WHERE id = %s"
TOUCH = "UPDATE {t} SET agency_id = agency_id WHERE id = %s"
MOVE = "UPDATE {t} SET agency_id = %s WHERE id = %s"
DELETE = "DELETE FROM {t} WHERE id = %s"

Insert = Callable[[CursorWrapper, uuid.UUID, Mapping[str, uuid.UUID]], uuid.UUID]


@dataclass(frozen=True)
class IsolationCase:
    table: str  # schema-qualified, e.g. "public.client"
    insert: Insert
    commands: frozenset[str]  # as granted to skiw_app by tenant_table()
    parents: Mapping[str, str] = field(default_factory=dict)  # FK column -> parent table

    def __post_init__(self) -> None:
        if not QUALIFIED.fullmatch(self.table):
            raise ValueError(f"isolation case {self.table!r}: use a schema-qualified name")
        if not {"SELECT", "INSERT"} <= self.commands <= COMMANDS:
            raise ValueError(f"isolation case {self.table}: commands must include SELECT, INSERT")


def registry() -> dict[str, IsolationCase]:
    """Every project app's `tests.isolation_cases.CASES`, by table."""
    found: dict[str, IsolationCase] = {}
    for config in apps.get_app_configs():
        if not Path(config.path).is_relative_to(PROJECT):
            continue
        name = f"{config.name}.tests.isolation_cases"
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name in (name, f"{config.name}.tests"):
                continue
            raise
        for case in module.CASES:
            if case.table in found:
                raise ValueError(f"isolation case {case.table} is registered twice")
            found[case.table] = case
    return found


@contextmanager
def refused(sqlstate: str, what: str) -> Iterator[None]:
    try:
        yield
    except DatabaseError as exc:
        got = getattr(exc.__cause__, "sqlstate", None)
        if got != sqlstate:
            raise AssertionError(f"{what}: expected SQLSTATE {sqlstate}, got {got}") from exc
    else:
        raise AssertionError(f"{what}: expected SQLSTATE {sqlstate}, but it succeeded")


Cases = Mapping[str, IsolationCase]


def make_row(cases: Cases, case: IsolationCase, agency: uuid.UUID) -> uuid.UUID:
    """One committed row of `case` for `agency`, with a fresh parent row (same agency) per FK."""
    return _insert(case, agency, _parents(cases, case, agency), bound=agency)


def _parents(cases: Cases, case: IsolationCase, agency: uuid.UUID) -> dict[str, uuid.UUID]:
    return {column: make_row(cases, cases[table], agency) for column, table in case.parents.items()}


def _insert(
    case: IsolationCase,
    agency: uuid.UUID,
    parents: Mapping[str, uuid.UUID],
    bound: uuid.UUID | None,
) -> uuid.UUID:
    """`case.insert` naming `agency`, in a transaction bound to `bound` (None: no token)."""
    binding = transaction.atomic() if bound is None else with_agency(bound)
    with binding, connection.cursor() as cursor:
        return case.insert(cursor, agency, parents)


def _sql(case: IsolationCase, statement: str, params: list[uuid.UUID]) -> int:
    """`statement` on the case's table (`{t}`): count(*) for a SELECT, else the row count."""
    with connection.cursor() as cursor:
        cursor.execute(statement.format(t=case.table), params)
        return int(cursor.fetchone()[0] if statement.startswith("SELECT") else cursor.rowcount)


def check_read(cases: Cases, case: IsolationCase) -> None:
    """Under A, B's row is invisible; under B (the control) it is there."""
    row = make_row(cases, case, B)
    with with_agency(B):
        assert _sql(case, COUNT, [row]) == 1, f"{case.table}: under B, B's own row is not visible"
    with with_agency(A):
        seen = _sql(case, COUNT, [row])
    assert seen == 0, f"{case.table}: under A, {seen} of B's rows visible"


def check_write(cases: Cases, case: IsolationCase) -> None:
    """Under A, UPDATE and DELETE of B's row affect 0 rows, and the row is still B's."""
    row = make_row(cases, case, B)
    with with_agency(A):
        if "UPDATE" in case.commands:
            changed = _sql(case, TOUCH, [row])
            assert changed == 0, f"{case.table}: under A, UPDATE changed {changed} of B's rows"
        if "DELETE" in case.commands:
            deleted = _sql(case, DELETE, [row])
            assert deleted == 0, f"{case.table}: under A, DELETE removed {deleted} of B's rows"
    with with_agency(B):
        assert _sql(case, COUNT, [row]) == 1, f"{case.table}: B's row is gone after A's writes"


def check_cross_insert(cases: Cases, case: IsolationCase) -> None:
    """Under A, an INSERT naming B (with B's own parents, so no FK fails) is refused by RLS."""
    parents = _parents(cases, case, B)
    with refused(DENIED, f"{case.table}: INSERT as B under A"):
        _insert(case, B, parents, bound=A)


def check_cross_update(cases: Cases, case: IsolationCase) -> None:
    """Under A, moving A's own row to B is refused by the WITH CHECK clause."""
    row = make_row(cases, case, A)
    with refused(DENIED, f"{case.table}: UPDATE from A to B"), with_agency(A):
        _sql(case, MOVE, [B, row])


def check_no_token(cases: Cases, case: IsolationCase) -> None:
    """With no token there are no rows, and an INSERT is refused."""
    row = make_row(cases, case, A)
    parents = _parents(cases, case, A)
    with transaction.atomic():
        assert _sql(case, COUNT, [row]) == 0, f"{case.table}: a row is visible with no token"
    with refused(DENIED, f"{case.table}: INSERT with no token"):
        _insert(case, A, parents, bound=None)


def check_append_only(cases: Cases, case: IsolationCase) -> None:
    """A command skiw_app was not granted is refused even on A's own row (TEN-03)."""
    row = make_row(cases, case, A)
    if "UPDATE" not in case.commands:
        with refused(DENIED, f"{case.table}: UPDATE on an append-only table"), with_agency(A):
            _sql(case, TOUCH, [row])
    if "DELETE" not in case.commands:
        with refused(DENIED, f"{case.table}: DELETE on an append-only table"), with_agency(A):
            _sql(case, DELETE, [row])


def check_cross_fk(cases: Cases, case: IsolationCase, column: str) -> None:
    """Under A, a row of A whose `column` points at B's parent row fails the composite FK. RI
    checks bypass RLS, so only the composite FK can refuse it."""
    parents = _parents(cases, case, A)
    parents[column] = make_row(cases, cases[case.parents[column]], B)
    with refused(NO_PARENT, f"{case.table}.{column}: A child of B's parent"):
        _insert(case, A, parents, bound=A)


Check = Callable[[Cases, IsolationCase], None]
CHECKS: dict[str, tuple[Check, Callable[[IsolationCase], bool]]] = {
    "read": (check_read, lambda case: True),
    "write": (check_write, lambda case: bool({"UPDATE", "DELETE"} & case.commands)),
    "cross_insert": (check_cross_insert, lambda case: True),
    "cross_update": (check_cross_update, lambda case: "UPDATE" in case.commands),
    "no_token": (check_no_token, lambda case: True),
    "append_only": (check_append_only, lambda case: case.commands != COMMANDS),
}
