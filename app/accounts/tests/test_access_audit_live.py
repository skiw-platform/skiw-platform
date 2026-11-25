"""Single-statement writes to the four roles tables as skiw_app (plan row M4r-1g, split M4r-1g-ii;
slice spec Decisions 3, 28, 30, 32, 33; the §7 rows "A role, tick, assignment or org change commits
with no record" and "Agency B reads or writes agency A's change events"). Every write runs on the
real Django connection inside with_agency() and commits for real, in a fresh agency the migrator
adds and keeps (skiw_app has no DELETE on org_unit or security_event; the TEN-08 harness keeps its
rows too). The same statements as the owner and the multi-row forms are in test_roles_audit_live and
test_org_audit_live, the seed in test_access_seed_live, the grants and every migration prefix in
test_write_grants_live, the other TEN-08 checks in the harness (accounts/tests/isolation_cases.py).
COPY, MERGE, INSERT … SELECT, ON CONFLICT DO NOTHING and the races are M4r-1h."""

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from accounts.tests.test_roles_audit_live import NO_OPERATOR, REFUSED_WRITES, STATE, ordered
from accounts.tests.test_roles_guards_live import REFUSED, Cursor
from accounts.tests.test_roles_tree_owner_live import INCOMPLETE, NO_HOLDER
from tenancy import seed
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

OPERATOR = "test-operator"
type Event = tuple[str, uuid.UUID, dict[str, str | None]]  # details_json: JSON strings and nulls
# Any: the named-parameter mapping psycopg takes (UUIDs and the user's email); the tests index it
# for the agency id in many places, which a union of the two would force them to cast.
type Ids = dict[str, Any]
EVENTS = (
    "SELECT id, kind, agency_id, details_json::text, at FROM security_event WHERE agency_id = %s"
)
USER = (
    "INSERT INTO app_user (id, agency_id, email, display_name)"
    " VALUES (%(user_id)s, %(a)s, %(email)s, 'U')"
)
ROLE = "INSERT INTO role (id, agency_id, name) VALUES (%(r)s, %(a)s, 'Adviser')"
TICK = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " VALUES (%(tick)s, %(a)s, %(r)s, 'client.view', 'own')"
)
ASSIGN = (
    "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (%(ura)s, %(a)s, %(user_id)s, %(r)s, %(org_unit_id)s, 'insurance')"
)


ROOT = (
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (%(root)s, %(a)s, NULL, 'agency', 'Root')"
)
CHILD = (  # org_unit_id: the key REFUSED_WRITES names it by
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (%(org_unit_id)s, %(a)s, %(root)s, 'unit', 'Unit')"
)
TEAM = (
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (%(team)s, %(a)s, %(org_unit_id)s, 'team', 'Team')"
)


def fresh_agency(steps: bool = False) -> uuid.UUID:
    """An agency the migrator commits and keeps; `steps`: with its seeded Owner role (M4r-1f)."""
    agency = uuid.uuid4()
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        seed.insert_agency(cursor, agency, "Audit test", steps=steps)
    return agency


@contextmanager
def app(agency: uuid.UUID | None, operator: str | None = OPERATOR) -> Iterator[Cursor]:
    """One skiw_app transaction bound to `agency` (None: no token), committed on a clean exit, with
    `operator` set as skiw.operator (None: the session's value is left as it is). The driver cursor
    under Django's wrapper: the same connection and transaction, psycopg's errors and rows."""
    with with_agency(agency) if agency else transaction.atomic(), connection.cursor() as wrapper:
        cursor = cast(Cursor, wrapper.cursor)
        if operator is not None:
            cursor.execute("SELECT set_config('skiw.operator', %s, true)", [operator])
        yield cursor


def refusal(
    agency: uuid.UUID | None, sql: str, p: Ids, operator: str | None = OPERATOR
) -> tuple[str, str]:
    """`sql` in its own skiw_app transaction; the SQLSTATE and message it is refused with."""
    with pytest.raises(psycopg.Error) as caught, app(agency, operator) as cursor:
        cursor.execute(sql, p)
    return str(caught.value.sqlstate), str(caught.value.diag.message_primary)


def commit_refusal(agency: uuid.UUID, *statements: str, p: Ids) -> tuple[str, str]:
    """`statements` in one skiw_app transaction whose COMMIT (a deferred check) refuses it."""
    with pytest.raises(DatabaseError) as caught, app(agency) as cursor:
        for sql in statements:
            cursor.execute(sql, p)
    cause = cast(psycopg.Error, caught.value.__cause__)
    return str(cause.sqlstate), str(cause.diag.message_primary)


def holds(agency: uuid.UUID, condition: str, p: Ids) -> bool:
    with app(agency, None) as cursor:
        row = cursor.execute(f"SELECT {condition}", p).fetchone()
    return bool(row and row[0])


def state(agency: uuid.UUID) -> object:
    with app(agency, None) as cursor:
        return cursor.execute(STATE, {"a": agency}).fetchone()


class Events:
    """skiw_app's view, under the agency's own token, of its change events new since the last
    call (their `at` values in `at`); each call is a transaction of its own, so only committed
    events are seen."""

    def __init__(self, agency: uuid.UUID) -> None:
        self.agency, self.seen, self.at = agency, set[uuid.UUID](), set[datetime]()

    def new(self) -> list[Event]:
        with app(self.agency, None) as cursor:
            rows = cursor.execute(EVENTS, [self.agency]).fetchall()
        fresh = [row for row in rows if row[0] not in self.seen]
        self.seen.update(row[0] for row in fresh)
        self.at = {row[4] for row in fresh}
        return ordered([(k, a, json.loads(d)) for _, k, a, d, _ in fresh])


def ev(kind: str, p: Ids, **values: object) -> Event:
    """A `kind` event of agency p["a"] by OPERATOR with these Decision 30 key values."""
    details = {key: None if value is None else str(value) for key, value in values.items()}
    return (kind, p["a"], {"operator": OPERATOR, **details})


def ids(agency: uuid.UUID) -> Ids:
    """Every row id a test needs, made up front (keys as REFUSED_WRITES names them)."""
    p: Ids = {k: uuid.uuid4() for k in ("root", "org_unit_id", "team", "r", "spare", "tick")}
    p |= {"ura": uuid.uuid4(), "user_id": uuid.uuid4(), "a": agency}
    return p | {"email": f"{p['user_id']}@audit.test"}


ROWS = (
    "SELECT id FROM role WHERE agency_id = %(a)s UNION ALL SELECT id FROM role_permission"
    " WHERE agency_id = %(a)s UNION ALL SELECT id FROM user_role WHERE agency_id = %(a)s"
    " UNION ALL SELECT id FROM org_unit WHERE agency_id = %(a)s"
)
SUBJECT = {"org.added": "org_unit_id", "role.created": "role_id", "role.deleted": "role_id"}
SUBJECT |= {"permission.set": "role_permission_id", "permission.unset": "role_permission_id"}
SUBJECT |= {"role.assigned": "user_role_id", "role.unassigned": "user_role_id"}


def test_each_granted_change_commits_with_exactly_its_events() -> None:
    """One committed statement per step; then, each in a later transaction, its events (the one
    event-count rule, Decision 32), each with `at` = the statement_timestamp() of the change (read
    by its own RETURNING, so the same statement; any other statement of the transaction has
    another), and the change: the rows present, and the moved or renamed row's new values."""
    p = ids(fresh_agency())
    log = Events(p["a"])
    with app(p["a"]) as cursor:
        cursor.execute(USER, p)  # app_user: no change event
    root, child, team, role = p["root"], p["org_unit_id"], p["team"], p["r"]
    tick = {"role_permission_id": p["tick"], "role_id": role, "permission_code": "client.view"}
    tick |= {"scope": "own"}
    held = {"user_role_id": p["ura"], "user_id": p["user_id"], "role_id": role}
    held |= {"org_unit_id": child, "line": "insurance"}
    unit = "SELECT FROM org_unit WHERE id = %(team)s AND"
    steps: list[tuple[str, list[Event], str]] = [
        (ROOT, [ev("org.added", p, org_unit_id=root, parent_id=None, unit_kind="agency")], ""),
        (CHILD, [ev("org.added", p, org_unit_id=child, parent_id=root, unit_kind="unit")], ""),
        (TEAM, [ev("org.added", p, org_unit_id=team, parent_id=child, unit_kind="team")], ""),
        (
            "UPDATE org_unit SET parent_id = %(root)s WHERE id = %(team)s",
            [ev("org.moved", p, org_unit_id=team, old_parent_id=child, new_parent_id=root)],
            f"EXISTS ({unit} parent_id = %(root)s AND name = 'Team')",
        ),
        (
            "UPDATE org_unit SET name = 'Renamed' WHERE id = %(team)s",
            [ev("org.renamed", p, org_unit_id=team)],
            f"EXISTS ({unit} parent_id = %(root)s AND name = 'Renamed')",
        ),
        (
            "UPDATE org_unit SET parent_id = %(org_unit_id)s, name = 'Both' WHERE id = %(team)s",
            [
                ev("org.moved", p, org_unit_id=team, old_parent_id=root, new_parent_id=child),
                ev("org.renamed", p, org_unit_id=team),
            ],
            f"EXISTS ({unit} parent_id = %(org_unit_id)s AND name = 'Both')",
        ),
        (
            "UPDATE org_unit SET parent_id = parent_id, name = 'Both' WHERE id = %(team)s",
            [],
            f"EXISTS ({unit} parent_id = %(org_unit_id)s AND name = 'Both')",
        ),
        (ROLE, [ev("role.created", p, role_id=role)], ""),
        (
            "UPDATE role SET name = 'Senior' WHERE id = %(r)s",
            [ev("role.renamed", p, role_id=role)],
            "(SELECT name FROM role WHERE id = %(r)s) = 'Senior'",
        ),
        ("UPDATE role SET name = 'Senior' WHERE id = %(r)s", [], ""),
        ("UPDATE role SET name = name WHERE id = %(r)s", [], ""),
        (TICK, [ev("permission.set", p, **tick)], ""),
        (ASSIGN, [ev("role.assigned", p, **held)], ""),
        (
            "DELETE FROM role_permission WHERE id = %(tick)s",
            [ev("permission.unset", p, **tick)],
            "",
        ),
        ("DELETE FROM user_role WHERE id = %(ura)s", [ev("role.unassigned", p, **held)], ""),
        ("DELETE FROM role WHERE id = %(r)s", [ev("role.deleted", p, role_id=role)], ""),
    ]
    present: set[str] = set()
    for sql, expected, condition in steps:
        with app(p["a"]) as cursor:
            stamps = cursor.execute(f"{sql} RETURNING statement_timestamp()", p).fetchall()
            assert cursor.rowcount == 1, sql
        [(stamp,)] = stamps
        assert (sql, log.new()) == (sql, ordered(expected))
        assert (sql, log.at) == (sql, {stamp} if expected else set())
        for kind, _, details in expected:
            if kind in SUBJECT:
                present ^= {
                    str(details[SUBJECT[kind]])
                }  # added, or (unset, unassigned, deleted) gone
        with app(p["a"], None) as cursor:
            assert {str(row) for (row,) in cursor.execute(ROWS, p)} == present, sql
            assert not condition or cursor.execute(f"SELECT {condition}", p).fetchone() == (True,)


def build(p: Ids) -> None:
    """A root, a unit, a team under it, a user, a role with one tick and one assignment, and a
    spare role, committed as skiw_app with a valid operator (the refusal tests' rows)."""
    spare = "INSERT INTO role (id, agency_id, name) VALUES (%(spare)s, %(a)s, 'Spare')"
    with app(p["a"]) as cursor:
        for sql in (ROOT, CHILD, TEAM, USER, ROLE, TICK, ASSIGN, spare):
            cursor.execute(sql, p)


MOVE_AND_RENAME = "UPDATE org_unit SET parent_id = %(root)s, name = 'New' WHERE id = %(team)s"
BAD_OPERATORS = {"unset": None, "empty": "", "capitals": "Bob", "33-characters": "a" * 33}
BAD_OPERATORS |= {"comma": "ops,1"}


@pytest.mark.parametrize("bad", BAD_OPERATORS)
def test_each_change_without_a_valid_operator_is_refused_with_nothing_written(bad: str) -> None:
    """The twelve statements of test_roles_audit_live (every granted form), the combined org move
    and rename and a root insert in a rootless agency, here as skiw_app."""
    p = ids(fresh_agency())
    build(p)
    log, before = Events(p["a"]), state(p["a"])
    log.new()
    value = BAD_OPERATORS[bad]
    connection.close()  # a new session: skiw.operator never set in it ("unset")
    with app(p["a"], value) as cursor:
        assert cursor.execute("SELECT current_setting('skiw.operator', true)").fetchone() == (
            value,
        )
    for name, sql in {**REFUSED_WRITES, "org move and rename": MOVE_AND_RENAME}.items():
        assert (name, refusal(p["a"], sql, p, operator=value)) == (name, NO_OPERATOR)
    assert state(p["a"]) == before and log.new() == []
    rootless = ids(fresh_agency())  # no root yet, so a duplicate-root error cannot mask the refusal
    before, empty = state(rootless["a"]), Events(rootless["a"])
    assert refusal(rootless["a"], ROOT, rootless, operator=value) == NO_OPERATOR
    assert state(rootless["a"]) == before and empty.new() == []


DENIED = "42501"
NOT_GRANTED = {
    "role_permission update": "UPDATE role_permission SET scope = scope WHERE role_id = %(r)s",
    "user_role update": "UPDATE user_role SET line = 'both' WHERE role_id = %(r)s",
    "tick upsert": TICK.replace("%(tick)s", "gen_random_uuid()")
    + " ON CONFLICT ON CONSTRAINT role_permission_tick_uq DO UPDATE SET scope = EXCLUDED.scope",
    "assign upsert": ASSIGN.replace("%(ura)s", "gen_random_uuid()")
    + " ON CONFLICT ON CONSTRAINT user_role_assignment_uq DO UPDATE SET line = EXCLUDED.line",
    "org_unit delete": "DELETE FROM org_unit WHERE id = %(team)s",
    "role id": "UPDATE role SET id = gen_random_uuid() WHERE id = %(r)s",
    "role agency_id": "UPDATE role SET agency_id = agency_id WHERE id = %(r)s",
    "role is_system": "UPDATE role SET is_system = true WHERE id = %(r)s",
    "role created_at": "UPDATE role SET created_at = created_at WHERE id = %(r)s",
    "role name and is_system": "UPDATE role SET name = 'X', is_system = false WHERE id = %(r)s",
    **{f"truncate {t}": f"TRUNCATE {t} CASCADE" for t in ("role", "role_permission", "user_role")},
    "truncate org_unit": "TRUNCATE org_unit CASCADE",
    **{
        f"disable {t}_audit": f"ALTER TABLE {t} DISABLE TRIGGER {t}_audit"
        for t in ("role", "role_permission", "user_role", "org_unit")
    },
    "replica": "SET session_replication_role = replica",
}
ORG_IMMUTABLE = {
    "org_unit id": "UPDATE org_unit SET id = gen_random_uuid() WHERE id = %(team)s",
    "org_unit kind": "UPDATE org_unit SET kind = 'unit' WHERE id = %(team)s",
    "org_unit created_at": "UPDATE org_unit SET created_at = created_at - interval '1 day'"
    " WHERE id = %(team)s",
}


def test_each_statement_outside_decision_3_is_refused_with_nothing_written() -> None:
    """With a valid operator: no grant (42501 from the privilege check), or for org_unit's fixed
    columns the audit trigger (REFUSED), or for its agency_id RLS's WITH CHECK."""
    p = ids(fresh_agency())
    build(p)
    log, before = Events(p["a"]), state(p["a"])
    log.new()
    found = {name: refusal(p["a"], sql, p)[0] for name, sql in NOT_GRANTED.items()}
    assert found == dict.fromkeys(NOT_GRANTED, DENIED)
    for name, sql in ORG_IMMUTABLE.items():
        assert (name, refusal(p["a"], sql, p)) == (name, REFUSED)
    moved = "UPDATE org_unit SET agency_id = gen_random_uuid() WHERE id = %(team)s"
    assert refusal(p["a"], moved, p)[0] == DENIED
    assert state(p["a"]) == before and log.new() == []


def test_a_change_and_its_events_roll_back_together_before_commit() -> None:
    p = ids(fresh_agency())
    log = Events(p["a"])
    with pytest.raises(RuntimeError), app(p["a"]) as cursor:
        for sql in (ROOT, ROLE, TICK):
            cursor.execute(sql, p)
        raise RuntimeError("before commit")
    assert state(p["a"]) == (None, 0, 0, None) and log.new() == []


def test_an_unassign_failing_owner_remains_at_commit_leaves_no_change_and_no_event() -> None:
    p = ids(fresh_agency(steps=True))  # the seeded Owner role, with no holder yet
    log = Events(p["a"])
    with app(p["a"]) as cursor:
        [(p["r"],)] = cursor.execute("SELECT id FROM role WHERE is_system").fetchall()
        for sql in (ROOT, CHILD, USER, ASSIGN):
            cursor.execute(sql, p)
    log.new()
    unassign = "DELETE FROM user_role WHERE id = %(ura)s"
    assert commit_refusal(p["a"], unassign, p=p) == NO_HOLDER
    assert holds(p["a"], "EXISTS (SELECT FROM user_role WHERE id = %(ura)s)", p)
    assert log.new() == []


def test_an_incomplete_system_role_failing_at_commit_leaves_no_change_and_no_event() -> None:
    p = ids(fresh_agency())  # no seeded Owner role, so a system role may be added
    system = (
        "INSERT INTO role (id, agency_id, name, is_system) VALUES (%(r)s, %(a)s, 'Owner', true)"
    )
    assert commit_refusal(p["a"], system, TICK, p=p) == INCOMPLETE
    assert state(p["a"]) == (None, 0, 0, None) and Events(p["a"]).new() == []


WRONG_AGENCY = {
    "role rename": "UPDATE role SET name = 'Taken' WHERE id = %(r)s",
    "role delete": "DELETE FROM role WHERE id = %(spare)s",
    "untick": "DELETE FROM role_permission WHERE id = %(tick)s",
    "unassign": "DELETE FROM user_role WHERE id = %(ura)s",
    "org rename": "UPDATE org_unit SET name = 'Taken' WHERE id = %(team)s",
    "org move": "UPDATE org_unit SET parent_id = %(root)s WHERE id = %(team)s",
}


@pytest.mark.parametrize("bound", ["other-agency", "no-token"])
def test_another_agency_or_no_token_neither_changes_the_rows_nor_sees_the_events(
    bound: str, agency_b: uuid.UUID
) -> None:
    """TEN-08 for the granted UPDATE and DELETE forms (the harness leaves out role's column-level
    UPDATE of name, DECISIONS "M4r-1g-i"): 0 rows, nothing written; the agency's events, written
    as skiw_app by build(), are visible under its own token only (Decision 33)."""
    p = ids(fresh_agency())
    build(p)
    log, before = Events(p["a"]), state(p["a"])
    written = len(log.new())
    other = agency_b if bound == "other-agency" else None
    with app(other) as cursor:
        changed = {name: cursor.execute(sql, p).rowcount for name, sql in WRONG_AGENCY.items()}
        seen = cursor.execute("SELECT count(*) FROM security_event WHERE agency_id = %s", [p["a"]])
        assert seen.fetchone() == (0,)
    assert changed == dict.fromkeys(WRONG_AGENCY, 0)
    assert state(p["a"]) == before and log.new() == [] and written == 7
