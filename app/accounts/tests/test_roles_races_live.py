"""Two skiw_app sessions racing on the roles tables (plan row M4r-1h, split M4r-1h-i; slice spec
Decisions 27, 28; the §7 rows "Concurrent opposing moves create a cycle", "Two unassigners remove
the last Owner" and "Concurrent role edits leave an inconsistent state"). The first session runs on
this thread's Django connection, the second on its own thread (its own Django connection); the
first ends only once pg_locks shows the second waiting on the agency's roles lock. Every statement
is raw SQL (no operator command exists yet, M4r-5); each race also runs with the commands' explicit
lock taken first (Decision 12). Lock and statement timeouts make a hang fail. Fresh agencies, kept
as in test_access_audit_live. The owner-run single-transaction cases are test_roles_guards_live and
test_roles_tree_owner_live; the remaining DML forms are M4r-1h-ii."""

import contextlib
import threading
import time
import uuid
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection

from accounts.tests.test_access_audit_live import Events, app, ev, fresh_agency, state
from accounts.tests.test_roles_audit_live import ordered
from accounts.tests.test_roles_guards_live import FIRST_WRITE, LEVELS, NOT_READ_COMMITTED, Cursor
from accounts.tests.test_roles_guards_live import MIGRATION as LOCKS
from accounts.tests.test_roles_tree_owner_live import CYCLE, NO_HOLDER

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

BOUND_S = 10  # how long a session may take to start, wait or finish before the test fails
TIMEOUTS = (
    "SELECT set_config('lock_timeout', '15s', true), set_config('statement_timeout', '20s', true)"
)
LOCK_FIRST = f"SELECT pg_advisory_xact_lock({LOCKS.ROLES_LOCK_CLASS}, hashtext(%(a)s::text))"
WAITING = (
    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted AND pid = %s"
    " AND objsubid = 2 AND classid = %s::oid AND objid = hashtext(%s::text)::oid"
)
UNIT = "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) VALUES (%s, %s, %s, %s, 'U')"
USER = "INSERT INTO app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, 'U')"
ASSIGN = (
    "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (%(ura)s, %(a)s, %(user_id)s, %(r)s, %(unit)s, 'both')"
)
TICK = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (%(tick)s, %(a)s, %(r)s, 'client.view', 'own')"
)
type Outcome = tuple[str, str, str] | None  # None: committed; else (stage, SQLSTATE, message)


class Second:
    """The second session: `statements` in one with_agency() transaction on a thread of its own,
    then COMMIT. `outcome`: None if committed, else where it was refused ("statement" or "commit")
    with the SQLSTATE and message."""

    def __init__(self, p: dict[str, Any], statements: list[str]) -> None:
        self.pid, self.started, self.finished = 0, threading.Event(), False
        self.outcome: Outcome = ("unfinished", "", "")  # None only once its COMMIT returned
        self.thread = threading.Thread(target=self.run, args=(p, statements))
        self.thread.start()

    def run(self, p: dict[str, Any], statements: list[str]) -> None:
        stage = "statement"
        try:
            with app(p["a"]) as cursor:
                cursor.execute(TIMEOUTS)
                [(self.pid,)] = cursor.execute("SELECT pg_backend_pid()").fetchall()
                self.started.set()
                for sql in statements:
                    cursor.execute(sql, p)
                stage = "commit"
            self.outcome = None
        except (psycopg.Error, DatabaseError) as error:
            cause = error if isinstance(error, psycopg.Error) else error.__cause__
            assert isinstance(cause, psycopg.Error)
            self.outcome = (stage, str(cause.sqlstate), str(cause.diag.message_primary))
        finally:
            self.finished = True
            self.started.set()
            connection.close()

    def waits_on_the_roles_lock(self, cursor: Cursor, agency: uuid.UUID) -> None:
        """Returns once pg_locks shows this session waiting on `agency`'s roles lock (polled with
        a bound; the poll interval is not the synchronisation)."""
        assert self.started.wait(BOUND_S), "the second session never started"
        deadline = time.monotonic() + BOUND_S
        while time.monotonic() < deadline and not self.finished:
            if cursor.execute(
                WAITING, [self.pid, LOCKS.ROLES_LOCK_CLASS, str(agency)]
            ).fetchone() == (1,):
                return
            time.sleep(0.01)
        pytest.fail(f"the second session did not wait on the roles lock: {self.outcome}")


class Rollback(Exception):
    pass


def race(
    p: dict[str, Any], first: list[str], second: list[str], commit: bool, lock: bool
) -> Outcome:
    """`first` runs and stays open; `second` starts and must wait on the roles lock; then the first
    commits (or rolls back, `commit` false). The second session's outcome. `lock`: each session
    takes the operator commands' explicit roles lock as its first statement."""
    lead = [LOCK_FIRST] if lock else []
    other: Second | None = None
    try:
        with contextlib.suppress(Rollback), app(p["a"]) as cursor:
            cursor.execute(TIMEOUTS)
            for sql in lead + first:
                cursor.execute(sql, p)
            other = Second(p, lead + second)
            other.waits_on_the_roles_lock(cursor, p["a"])
            if not commit:
                raise Rollback
    finally:
        if other is not None:
            other.thread.join(BOUND_S)
    assert other is not None and not other.thread.is_alive(), "the second session never finished"
    return other.outcome


def rows(p: dict[str, Any], sql: str) -> Any:
    with app(p["a"], None) as cursor:
        return cursor.execute(sql, p).fetchall()


def subtree(p: dict[str, Any], unit: str) -> set[uuid.UUID]:
    """`unit` and every unit below it; UNION ends on a cycle too."""
    sql = (
        "WITH RECURSIVE s(id) AS (SELECT %(top)s::uuid UNION SELECT o.id FROM org_unit o"
        " JOIN s ON o.parent_id = s.id) SELECT id FROM s"
    )
    return {row for (row,) in rows({**p, "top": p[unit]}, sql)}


def tree(p: dict[str, Any]) -> dict[str, Any]:
    """A root with two units, ua and ub, under it; a user; with p's agency and operator."""
    p |= {k: uuid.uuid4() for k in ("root", "ua", "ub", "user_id")}
    with app(p["a"]) as cursor:
        cursor.execute(UNIT, [p["root"], p["a"], None, "agency"])
        for unit in ("ua", "ub"):
            cursor.execute(UNIT, [p[unit], p["a"], p["root"], "unit"])
        p["unit"] = p["ua"]  # where assignments are made
        cursor.execute(USER, [p["user_id"], p["a"], f"{p['user_id']}@race.test"])
    return p


MOVE = "UPDATE org_unit SET parent_id = %({0})s WHERE id = %({1})s"
BOTH = pytest.mark.parametrize("lock", [False, True], ids=["raw", "lock-first"])
ENDS = pytest.mark.parametrize("commit", [True, False], ids=["first-commits", "first-rolls-back"])


@BOTH
@ENDS
def test_opposing_moves_never_make_a_cycle(commit: bool, lock: bool) -> None:
    """ua under ub (open) against ub under ua: the second waits, then sees the first's move with a
    fresh snapshot and is refused as a cycle; or, the first rolled back, commits."""
    p = tree({"a": fresh_agency()})
    log = Events(p["a"])
    log.new()
    outcome = race(p, [MOVE.format("ub", "ua")], [MOVE.format("ua", "ub")], commit, lock)
    top, low = ("ub", "ua") if commit else ("ua", "ub")  # the unit that stays under the root
    assert outcome == (("statement", *CYCLE) if commit else None)
    assert subtree(p, "root") == {p["root"], p["ua"], p["ub"]}
    assert subtree(p, top) == {p[top], p[low]} and subtree(p, low) == {p[low]}
    moved = ev("org.moved", p, org_unit_id=p[low], old_parent_id=p["root"], new_parent_id=p[top])
    assert log.new() == [moved]


def owners(p: dict[str, Any]) -> dict[str, Any]:
    """The seeded Owner role (M4r-1f) held by two users, u0 and u1 (assignments o0 and o1)."""
    tree(p)
    with app(p["a"]) as cursor:
        [(p["r"],)] = cursor.execute("SELECT id FROM role WHERE is_system").fetchall()
        for n in (0, 1):
            p[f"u{n}"], p[f"o{n}"] = p["user_id"] if n == 0 else uuid.uuid4(), uuid.uuid4()
            if n:
                cursor.execute(USER, [p["u1"], p["a"], f"{p['u1']}@race.test"])
            cursor.execute(ASSIGN, {**p, "ura": p[f"o{n}"], "user_id": p[f"u{n}"]})
    return p


def unassigned(p: dict[str, Any], n: int) -> object:
    held = {"user_role_id": p[f"o{n}"], "user_id": p[f"u{n}"], "role_id": p["r"]}
    return ev("role.unassigned", p, **held, org_unit_id=p["unit"], line="both")


@BOTH
@ENDS
def test_two_unassigners_never_remove_the_last_owner(commit: bool, lock: bool) -> None:
    """Each session removes one of two Owner assignments: the second waits, deletes after the first
    commits and is refused at its own COMMIT (the deferred check, not the DELETE); or, the first
    rolled back, commits. One assignment remains either way."""
    p = owners({"a": fresh_agency(steps=True)})
    log = Events(p["a"])
    log.new()
    unassign = "DELETE FROM user_role WHERE id = %({})s"
    outcome = race(p, [unassign.format("o0")], [unassign.format("o1")], commit, lock)
    assert outcome == (("commit", *NO_HOLDER) if commit else None)
    left = "o1" if commit else "o0"
    assert rows(p, "SELECT id FROM user_role WHERE agency_id = %(a)s") == [(p[left],)]
    assert log.new() == [unassigned(p, 0 if commit else 1)]


def a_role(p: dict[str, Any]) -> dict[str, Any]:
    """tree() and a role r with one tick."""
    tree(p)
    p |= {"r": uuid.uuid4(), "tick": uuid.uuid4(), "ura": uuid.uuid4()}
    with app(p["a"]) as cursor:
        cursor.execute("INSERT INTO role (id, agency_id, name) VALUES (%(r)s, %(a)s, 'Race')", p)
        cursor.execute(TICK, p)
    return p


@BOTH
@ENDS
def test_an_assignment_to_a_role_being_deleted_waits_and_then_fails(
    commit: bool, lock: bool
) -> None:
    """The first unticks and deletes role r, the second assigns a user to it: the second waits,
    then fails the foreign key with no event; or, the first rolled back, commits one assignment."""
    p = a_role({"a": fresh_agency()})
    log = Events(p["a"])
    log.new()
    delete = [
        "DELETE FROM role_permission WHERE role_id = %(r)s",
        "DELETE FROM role WHERE id = %(r)s",
    ]
    outcome = race(p, delete, [ASSIGN], commit, lock)
    tick = {"role_permission_id": p["tick"], "role_id": p["r"], "permission_code": "client.view"}
    if commit:
        assert outcome is not None and outcome[:2] == ("statement", "23503")
        expected = [
            ev("permission.unset", p, **tick, scope="own"),
            ev("role.deleted", p, role_id=p["r"]),
        ]
    else:
        assert outcome is None
        held = {"user_role_id": p["ura"], "user_id": p["user_id"], "role_id": p["r"]}
        expected = [ev("role.assigned", p, **held, org_unit_id=p["unit"], line="both")]
    assigned = rows(p, "SELECT id FROM user_role WHERE agency_id = %(a)s")
    assert assigned == ([] if commit else [(p["ura"],)]) and log.new() == ordered(expected)


@BOTH
@ENDS
def test_two_ticks_of_the_same_pair_write_one_tick_and_one_event(commit: bool, lock: bool) -> None:
    """Both sessions tick client.view own on r: the second waits, then violates the unique key; or,
    the first rolled back, commits. Exactly one tick and one permission.set."""
    p = a_role({"a": fresh_agency()})
    with app(p["a"]) as cursor:
        cursor.execute("DELETE FROM role_permission WHERE id = %(tick)s", p)
    log = Events(p["a"])
    log.new()
    first, second = p["t1"], p["t2"] = uuid.uuid4(), uuid.uuid4()
    ticks = [[TICK.replace("%(tick)s", f"%({t})s")] for t in ("t1", "t2")]
    outcome = race(p, ticks[0], ticks[1], commit, lock)
    assert (outcome[:2] if outcome else None) == (("statement", "23505") if commit else None)
    kept = first if commit else second
    assert rows(p, "SELECT id FROM role_permission WHERE role_id = %(r)s") == [(kept,)]
    tick = {"role_permission_id": kept, "role_id": p["r"], "permission_code": "client.view"}
    assert log.new() == [ev("permission.set", p, **tick, scope="own")]


@pytest.mark.parametrize("level", ["repeatable-read", "serializable"])
@pytest.mark.parametrize("table", LOCKS.TABLES)
def test_a_skiw_app_writer_not_at_read_committed_is_refused_at_its_first_write(
    table: str, level: str
) -> None:
    """As skiw_app inside with_agency(): a fixed snapshot could miss a change committed while it
    waited on the lock (Decision 27), so the first write of any of the four tables is refused."""
    agency = fresh_agency()
    before, log = state(agency), Events(agency)
    connection.ensure_connection()
    connection.connection.isolation_level = LEVELS[level]
    try:
        with pytest.raises(psycopg.Error) as caught, app(agency) as cursor:
            assert cursor.execute("SHOW transaction_isolation").fetchone() == (
                level.replace("-", " "),
            )
            cursor.execute(FIRST_WRITE[table], [agency])
    finally:
        connection.close()  # the next session starts at the server default again
    assert (str(caught.value.sqlstate), caught.value.diag.message_primary) == NOT_READ_COMMITTED
    assert state(agency) == before and log.new() == []


def test_the_last_owner_check_fails_closed_when_the_token_is_cleared_before_commit() -> None:
    """The only Owner assignment removed, then the session's tenant token cleared, as a skiw_app
    writer could (DECISIONS M4r-1d-ii choice 4): at commit the check cannot see the agency's units
    and refuses, rather than miss the system role. The assignment stays and no event exists."""
    p = owners({"a": fresh_agency(steps=True)})
    with app(p["a"]) as cursor:
        cursor.execute("DELETE FROM user_role WHERE id = %(o1)s", p)  # one holder left: o0
    log = Events(p["a"])
    log.new()
    with pytest.raises(DatabaseError) as caught, app(p["a"]) as cursor:
        cursor.execute("DELETE FROM user_role WHERE id = %(o0)s", p)
        # The attack under test is a skiw_app session clearing its own token; the one suppression.
        # nosemgrep: tenancy-token-setting
        cursor.execute("SELECT set_config('app.tenant_token', '', true)")
        assert cursor.execute("SELECT guard.current_agency()").fetchone() == (None,)
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert (str(cause.sqlstate), cause.diag.message_primary) == NO_HOLDER
    assert rows(p, "SELECT id FROM user_role WHERE agency_id = %(a)s") == [(p["o0"],)]
    assert log.new() == []
