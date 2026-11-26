"""The remaining DML forms on the four roles tables (plan row M4r-1h, split M4r-1h-ii; slice spec
Decisions 3, 28, 30, 31, 32, 33; the §7 row "A role, tick, assignment or org change commits with
no record"): multi-row, INSERT … SELECT, MERGE … INSERT, MERGE … DELETE and ON CONFLICT DO NOTHING
(inserted and not inserted) as skiw_app inside with_agency(), committed for real in fresh agencies
(kept, as in test_access_audit_live, which has the single-statement forms and the helpers); then
the §7 scan of every event row for the emails and names they stored. Owner decisions 2026-11-25
(DECISIONS "M4r-1h-ii"): a statement that writes no row succeeds without a valid operator; COPY
FROM is refused as skiw_app (RLS), and its trigger path is shown as the owner with FORCE lifted,
rolled back. The races are test_roles_races_live."""

import os
import uuid
from collections.abc import Sequence

import psycopg
import pytest
from django.db import connection

from accounts.tests.test_access_audit_live import (
    BAD_OPERATORS,
    ROOT,
    ROWS,
    SUBJECT,
    USER,
    Event,
    Events,
    Ids,
    app,
    build,
    ev,
    fresh_agency,
    ids,
    refusal,
)
from accounts.tests.test_roles_audit_live import NO_OPERATOR, Log, ordered
from accounts.tests.test_roles_guards_live import LIFTED, Cursor, owner
from tenancy import seed

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

type Step = tuple[str, list[Event], int]  # a statement, its events and the rows it writes
USER2 = (
    "INSERT INTO app_user (id, agency_id, email, display_name)"
    " VALUES (%(user2)s, %(a)s, %(email2)s, 'U')"
)
SENTINELS = ("em", "rn", "un")  # p's keys of the email, role-name and unit-name sentinels
COPY_HINT = "Use INSERT statements instead."
COPY_REFUSED = ("0A000", "COPY FROM not supported with row-level security", COPY_HINT)
MERGE_ROOT = (
    "MERGE INTO org_unit t USING (VALUES (%(root)s::uuid)) s (id) ON t.id = s.id"
    " WHEN NOT MATCHED THEN INSERT (id, agency_id, parent_id, kind, name)"
    " VALUES (s.id, %(a)s, NULL, 'agency', %(un)s || ' Root')"
)
UNIT_SKIP = (  # u1 is stored already
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) VALUES"
    " (%(u3)s, %(a)s, %(root)s, 'unit', %(un)s || ' U3'),"
    " (%(u1)s, %(a)s, %(root)s, 'unit', %(un)s || ' Dup')"
    " ON CONFLICT DO NOTHING"
)
ROLE_SKIP = (  # r7's name is r1's (lower(name) is unique per agency)
    "INSERT INTO role (id, agency_id, name) VALUES (%(r6)s, %(a)s, %(rn)s || ' Other'),"
    " (%(r7)s, %(a)s, %(rn)s || ' adviser') ON CONFLICT DO NOTHING"
)
TICK_SKIP = (  # k7 is k1's pair of r1 again
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope) VALUES"
    " (%(k6)s, %(a)s, %(r2)s, 'staff.view', 'agency'),"
    " (%(k7)s, %(a)s, %(r1)s, 'client.view', 'own') ON CONFLICT DO NOTHING"
)
ASSIGN_SKIP = (  # s7 is s1's (user, role, unit) again
    "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line) VALUES"
    " (%(s6)s, %(a)s, %(user_id)s, %(r1)s, %(u2)s, 'investment'),"
    " (%(s7)s, %(a)s, %(user_id)s, %(r1)s, %(u1)s, 'both') ON CONFLICT DO NOTHING"
)
MOVE_RENAME = (
    "UPDATE org_unit SET parent_id = %(u3)s, name = CASE id WHEN %(t1)s THEN %(un)s || ' Moved'"
    " ELSE name END WHERE id IN (%(t1)s, %(t2)s)"
)
RENAME = (
    "UPDATE role SET name = CASE id WHEN %(r5)s THEN name ELSE name || ' 2' END"
    " WHERE id IN (%(r3)s, %(r4)s, %(r5)s)"
)
ROLE_MERGE = (  # r1 is stored already
    "MERGE INTO role t USING (VALUES (%(r1)s::uuid), (%(r5)s::uuid)) s (id) ON t.id = s.id"
    " WHEN NOT MATCHED THEN INSERT (id, agency_id, name) VALUES (s.id, %(a)s, %(rn)s || ' Spare')"
)
TICK_MERGE = (  # k1 is stored already
    "MERGE INTO role_permission t USING (VALUES (%(k1)s::uuid, 'own'),"
    " (%(k5)s::uuid, 'team')) s (id, scope) ON t.id = s.id WHEN NOT MATCHED THEN INSERT"
    " (id, agency_id, role_id, permission_code, scope)"
    " VALUES (s.id, %(a)s, %(r1)s, 'client.view', s.scope)"
)
ASSIGN_MERGE = (  # s1 is stored already
    "MERGE INTO user_role t USING (VALUES (%(s1)s::uuid, %(u1)s::uuid),"
    " (%(s5)s::uuid, %(u2)s::uuid)) s (id, unit) ON t.id = s.id WHEN NOT MATCHED THEN"
    " INSERT (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (s.id, %(a)s, %(user2)s, %(r1)s, s.unit, 'investment')"
)
AFTER = {  # what an UPDATE changed, true after its commit
    MOVE_RENAME: "(SELECT array_agg(name ORDER BY name) FROM org_unit WHERE parent_id = %(u3)s)"
    " = ARRAY[%(un)s || ' Moved', %(un)s || ' Team']",
    RENAME: "(SELECT array_agg(name ORDER BY name) FROM role WHERE id IN (%(r3)s, %(r4)s, %(r5)s))"
    " = ARRAY[%(rn)s || ' Adviser copy 2', %(rn)s || ' Manager copy 2', %(rn)s || ' Spare']",
}
FIELDS = {  # the Decision 30 keys of each kind, after operator
    "org.added": ("org_unit_id", "parent_id", "unit_kind"),
    "org.moved": ("org_unit_id", "old_parent_id", "new_parent_id"),
    "org.renamed": ("org_unit_id",),
    **dict.fromkeys(("role.created", "role.renamed", "role.deleted"), ("role_id",)),
    **dict.fromkeys(
        ("permission.set", "permission.unset"),
        ("role_permission_id", "role_id", "permission_code", "scope"),
    ),
    **dict.fromkeys(
        ("role.assigned", "role.unassigned"),
        ("user_role_id", "user_id", "role_id", "org_unit_id", "line"),
    ),
}

# The ticks of each role and the assignments of each user that the steps store, as events() rows.
TICKS = {
    "r1": ("k1 r1 client.view own", "k2 r1 client.edit own", "k5 r1 client.view team"),
    "r2": ("k3 r2 client.view own", "k4 r2 client.edit own", "k6 r2 staff.view agency"),
}
HELD = {
    "user_id": (
        "s1 user_id r1 u1 insurance",
        "s2 user_id r2 u1 both",
        "s6 user_id r1 u2 investment",
    ),
    "user2": ("s3 user2 r1 u1 insurance", "s4 user2 r2 u1 both", "s5 user2 r1 u2 investment"),
}
STORED = (  # every row of the four tables, whole, by id
    "SELECT id::text, to_jsonb(t) FROM role t WHERE agency_id = %(a)s UNION ALL"
    " SELECT id::text, to_jsonb(t) FROM role_permission t WHERE agency_id = %(a)s UNION ALL"
    " SELECT id::text, to_jsonb(t) FROM user_role t WHERE agency_id = %(a)s UNION ALL"
    " SELECT id::text, to_jsonb(t) FROM org_unit t WHERE agency_id = %(a)s"
)
COLUMNS = {
    "org_unit": "id, agency_id, parent_id, kind, name",
    "role": "id, agency_id, name",
    "role_permission": "id, agency_id, role_id, permission_code, scope",
    "user_role": "id, agency_id, user_id, role_id, org_unit_id, line",
}


def agency_ids(agency: uuid.UUID) -> Ids:
    """ids() plus units u1..u3, teams t1, t2, roles r1..r7, ticks k1..k7, assignments s1..s7 and
    a second user, made up front (r7, k7 and s7 are never stored); and the sentinels, unique per
    call, that begin every email (em), role name (rn) and unit name (un) the steps write."""
    p = ids(agency)
    more = ["u1", "u2", "u3", "t1", "t2", "user2", *(f"{x}{n}" for x in "rks" for n in range(1, 8))]
    p |= {key: uuid.uuid4() for key in more} | {k: k + uuid.uuid4().hex[:16] for k in SENTINELS}
    return p | {"email": f"{p['em']}-1@audit.test", "email2": f"{p['em']}-2@audit.test"}


def events(p: Ids, kind: str, *rows: str) -> list[Event]:
    """One `kind` event per row, given as its key values: p's key for an id ('-': null), else
    the code itself."""
    values = [zip(FIELDS[kind], row.split(), strict=True) for row in rows]
    return [ev(kind, p, **{k: p.get(w) if k.endswith("_id") else w for k, w in v}) for v in values]


def multi_row(p: Ids) -> dict[str, Step]:
    """The multi-row INSERT of each table; the COPY tests copy the same rows."""
    return {
        "org_unit": (
            "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) VALUES"
            " (%(u1)s, %(a)s, %(root)s, 'unit', %(un)s || ' U1'),"
            " (%(u2)s, %(a)s, %(root)s, 'unit', %(un)s || ' U2')",
            events(p, "org.added", "u1 root unit", "u2 root unit"),
            2,
        ),
        "role": (
            "INSERT INTO role (id, agency_id, name)"
            " VALUES (%(r1)s, %(a)s, %(rn)s || ' Adviser'), (%(r2)s, %(a)s, %(rn)s || ' Manager')",
            events(p, "role.created", "r1", "r2"),
            2,
        ),
        "role_permission": (
            "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope) VALUES"
            " (%(k1)s, %(a)s, %(r1)s, 'client.view', 'own'),"
            " (%(k2)s, %(a)s, %(r1)s, 'client.edit', 'own')",
            events(p, "permission.set", *TICKS["r1"][:2]),
            2,
        ),
        "user_role": (
            "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line) VALUES"
            " (%(s1)s, %(a)s, %(user_id)s, %(r1)s, %(u1)s, 'insurance'),"
            " (%(s2)s, %(a)s, %(user_id)s, %(r2)s, %(u1)s, 'both')",
            events(p, "role.assigned", *HELD["user_id"][:2]),
            2,
        ),
    }


def steps(p: Ids) -> list[Step]:
    """Each form on each table, ordered so that every row a statement names exists; a repeated
    ON CONFLICT DO NOTHING or MERGE meets only stored rows and writes no row (0)."""
    many = multi_row(p)
    return [
        (MERGE_ROOT, events(p, "org.added", "root - agency"), 1),
        (MERGE_ROOT, [], 0),
        many["org_unit"],
        (
            "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) SELECT CASE id WHEN"
            " %(u1)s THEN %(t1)s::uuid ELSE %(t2)s::uuid END, agency_id, id, 'team',"
            " %(un)s || ' Team'"
            " FROM org_unit WHERE kind = 'unit'",
            events(p, "org.added", "t1 u1 team", "t2 u2 team"),
            2,
        ),
        (UNIT_SKIP, events(p, "org.added", "u3 root unit"), 1),
        (UNIT_SKIP, [], 0),
        (
            MOVE_RENAME,
            [
                *events(p, "org.moved", "t1 u1 u3", "t2 u2 u3"),
                *events(p, "org.renamed", "t1"),
            ],
            2,
        ),
        (
            "UPDATE org_unit SET parent_id = parent_id, name = name WHERE id IN (%(t1)s, %(t2)s)",
            [],
            2,
        ),
        many["role"],
        (
            "INSERT INTO role (id, agency_id, name) SELECT CASE id WHEN %(r1)s THEN"
            " %(r3)s::uuid ELSE %(r4)s::uuid END, agency_id, name || ' copy' FROM role",
            events(p, "role.created", "r3", "r4"),
            2,
        ),
        (ROLE_MERGE, events(p, "role.created", "r5"), 1),
        (ROLE_MERGE, [], 0),
        (ROLE_SKIP, events(p, "role.created", "r6"), 1),
        (ROLE_SKIP, [], 0),
        (RENAME, events(p, "role.renamed", "r3", "r4"), 3),  # r5's name unchanged: no event
        ("UPDATE role SET name = name WHERE id IN (%(r3)s, %(r4)s)", [], 2),
        (
            "MERGE INTO role t USING (VALUES (%(r3)s::uuid), (%(r4)s::uuid), (%(r7)s::uuid))"
            " s (id) ON t.id = s.id WHEN MATCHED THEN DELETE",
            events(p, "role.deleted", "r3", "r4"),
            2,
        ),
        ("DELETE FROM role WHERE id IN (%(r5)s, %(r6)s)", events(p, "role.deleted", "r5", "r6"), 2),
        many["role_permission"],
        (
            "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
            " SELECT CASE id WHEN %(k1)s THEN %(k3)s::uuid ELSE %(k4)s::uuid END, agency_id,"
            " %(r2)s::uuid, permission_code, scope FROM role_permission WHERE role_id = %(r1)s",
            events(p, "permission.set", *TICKS["r2"][:2]),
            2,
        ),
        (TICK_MERGE, events(p, "permission.set", TICKS["r1"][2]), 1),
        (TICK_MERGE, [], 0),
        (TICK_SKIP, events(p, "permission.set", TICKS["r2"][2]), 1),
        (TICK_SKIP, [], 0),
        many["user_role"],
        (
            "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
            " SELECT CASE id WHEN %(s1)s THEN %(s3)s::uuid ELSE %(s4)s::uuid END, agency_id,"
            " %(user2)s::uuid, role_id, org_unit_id, line FROM user_role"
            " WHERE user_id = %(user_id)s",
            events(p, "role.assigned", *HELD["user2"][:2]),
            2,
        ),
        (ASSIGN_MERGE, events(p, "role.assigned", HELD["user2"][2]), 1),
        (ASSIGN_MERGE, [], 0),
        (ASSIGN_SKIP, events(p, "role.assigned", HELD["user_id"][2]), 1),
        (ASSIGN_SKIP, [], 0),
        (
            "MERGE INTO role_permission t USING (VALUES (%(r2)s::uuid)) s (role_id)"
            " ON t.role_id = s.role_id WHEN MATCHED THEN DELETE",
            events(p, "permission.unset", *TICKS["r2"]),
            3,
        ),
        (
            "DELETE FROM role_permission WHERE role_id = %(r1)s",
            events(p, "permission.unset", *TICKS["r1"]),
            3,
        ),
        (
            "MERGE INTO user_role t USING (VALUES (%(user2)s::uuid)) s (user_id)"
            " ON t.user_id = s.user_id WHEN MATCHED THEN DELETE",
            events(p, "role.unassigned", *HELD["user2"]),
            3,
        ),
        (
            "DELETE FROM user_role WHERE user_id = %(user_id)s",
            events(p, "role.unassigned", *HELD["user_id"]),
            3,
        ),
    ]


def with_users() -> Ids:
    """A fresh agency with two users (app_user: no change event), committed."""
    p = agency_ids(fresh_agency())
    with app(p["a"]) as cursor:
        cursor.execute(USER, p)
        cursor.execute(USER2, p)
    return p


def snapshot(p: Ids) -> dict[str, object]:
    """Every row of the four tables, all its values, by id (one scoped read)."""
    with app(p["a"], None) as cursor:
        return dict(cursor.execute(STORED, p).fetchall())


def commit(p: Ids, log: Events, step: Step, present: set[str]) -> None:
    """`step` committed with a valid operator; then the rows it wrote (by its RETURNING), its
    events, each with `at` = the statement's own statement_timestamp(), and the change present."""
    sql, expected, rows = step
    with app(p["a"]) as cursor:
        returned = cursor.execute(f"{sql} RETURNING statement_timestamp()", p).fetchall()
    stamps = {stamp for (stamp,) in returned}
    assert (sql, len(returned), log.new()) == (sql, rows, ordered(expected))
    assert (sql, log.at) == (sql, stamps if expected else set()) and len(stamps) <= 1
    for kind, _, details in expected:
        if kind in SUBJECT:
            present ^= {str(details[SUBJECT[kind]])}  # added, or (unset, unassigned, deleted) gone
    assert (sql, set(snapshot(p))) == (sql, present)
    if sql in AFTER:
        with app(p["a"], None) as cursor:
            assert cursor.execute(f"SELECT {AFTER[sql]}", p).fetchone() == (True,), sql


def test_each_form_commits_with_exactly_its_events() -> None:
    p = with_users()
    log, present = Events(p["a"]), set[str]()
    for step in steps(p):
        commit(p, log, step, present)


@pytest.mark.parametrize("bad", BAD_OPERATORS)
def test_without_a_valid_operator_a_form_is_refused_unless_it_writes_no_row(bad: str) -> None:
    """Before each step, the same statement with the bad operator: refused if it writes a row (an
    UPDATE leaving its values unchanged too; single-row ones are in test_access_audit_live), else
    (all-duplicate ON CONFLICT DO NOTHING, a MERGE taking no action) rowcount 0. Either way no
    change and no event; then the step commits as above, so the next one finds its rows."""
    p, value = with_users(), BAD_OPERATORS[bad]
    log, present = Events(p["a"]), set[str]()
    for step in steps(p):
        (sql, _, rows), before = step, snapshot(p)
        if value is None:
            connection.close()  # a new session: skiw.operator never set in it
        with app(p["a"], value) as cursor:
            setting = cursor.execute("SELECT current_setting('skiw.operator', true)")
            assert setting.fetchone() == (value,)
            if not rows:
                assert (sql, cursor.execute(sql, p).rowcount) == (sql, 0)
        if rows:
            assert (sql, refusal(p["a"], sql, p, operator=value)) == (sql, NO_OPERATOR)
        assert (sql, snapshot(p), log.new()) == (sql, before, [])
        commit(p, log, step, present)


MERGES_DENIED = {
    "org_unit": "MERGE INTO org_unit t USING (VALUES (%(team)s::uuid)) s (id) ON t.id = s.id"
    " WHEN MATCHED THEN DELETE",
    "role_permission": "MERGE INTO role_permission t USING (VALUES (%(tick)s::uuid)) s (id)"
    " ON t.id = s.id WHEN MATCHED THEN UPDATE SET scope = 'team'",
    "user_role": "MERGE INTO user_role t USING (VALUES (%(ura)s::uuid)) s (id) ON t.id = s.id"
    " WHEN MATCHED THEN UPDATE SET line = 'both'",
}


def test_a_merge_needing_a_privilege_skiw_app_lacks_is_refused_with_nothing_written() -> None:
    """MERGE … DELETE on org_unit (owner decision 2026-11-25) and MERGE … UPDATE on
    role_permission and user_role: Decision 3 grants no DELETE and no UPDATE there."""
    p = ids(fresh_agency())
    build(p)
    log, before = Events(p["a"]), snapshot(p)
    log.new()
    for table, sql in MERGES_DENIED.items():
        expected = ("42501", f"permission denied for table {table}")
        assert (table, refusal(p["a"], sql, p)) == (table, expected)
    assert snapshot(p) == before and log.new() == []


def copies(p: Ids) -> dict[str, Sequence[tuple[object, ...]]]:
    """The rows of each table's multi-row INSERT, in FK order, for COPY."""
    a, r1, r2, u1, user = p["a"], p["r1"], p["r2"], p["u1"], p["user_id"]
    return {
        "org_unit": [(p[u], a, p["root"], "unit", f"{p['un']} {u.upper()}") for u in ("u1", "u2")],
        "role": [(r1, a, f"{p['rn']} Adviser"), (r2, a, f"{p['rn']} Manager")],
        "role_permission": [
            (p["k1"], a, r1, "client.view", "own"),
            (p["k2"], a, r1, "client.edit", "own"),
        ],
        "user_role": [(p["s1"], a, user, r1, u1, "insurance"), (p["s2"], a, user, r2, u1, "both")],
    }


def test_copy_from_stdin_as_skiw_app_is_refused_on_each_table_by_row_level_security() -> None:
    """After each refusal the same rows commit as the multi-row INSERT, with their events: they
    are valid, so RLS alone refused the COPY (and the next table's rows find theirs)."""
    p = agency_ids(fresh_agency())
    with app(p["a"]) as cursor:
        cursor.execute(ROOT, p)
        cursor.execute(USER, p)
    log, present = Events(p["a"]), set(snapshot(p))
    log.new()
    for table, rows in copies(p).items():
        before = snapshot(p)
        with (
            pytest.raises(psycopg.Error) as caught,
            app(p["a"]) as cursor,
            cursor.copy(f"COPY {table} ({COLUMNS[table]}) FROM STDIN") as copy,
        ):
            for row in rows:
                copy.write_row(row)
        error = caught.value
        found = (str(error.sqlstate), error.diag.message_primary, error.diag.message_hint)
        assert (table, found) == (table, COPY_REFUSED)
        assert snapshot(p) == before and log.new() == []
        commit(p, log, multi_row(p)[table], present)


def test_copy_from_as_the_table_owner_writes_one_event_per_row_and_is_rolled_back() -> None:
    """The successful COPY exists only here: the owner with FORCE lifted, in owner()'s
    transaction, which always rolls back; afterwards nothing of it is stored and FORCE is on."""
    p = agency_ids(uuid.uuid4())
    with owner(agencies=False) as cursor:
        seed.insert_agency(cursor, p["a"], "COPY test")
        cursor.execute(ROOT, p)
        cursor.execute(USER, p)
        log = Log(cursor, p["a"])
        log.new()
        for table, rows in copies(p).items():
            with cursor.copy(f"COPY {table} ({COLUMNS[table]}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            assert (table, log.new()) == (table, ordered(multi_row(p)[table][1]))
        copied = {str(p[key]) for key in ("root", "u1", "u2", "r1", "r2", "k1", "k2", "s1", "s2")}
        assert {str(row) for (row,) in cursor.execute(ROWS, p)} == copied
    with owner(agencies=False) as cursor:  # FORCE lifted again, so the owner sees every row
        cursor.execute("ALTER TABLE agency NO FORCE ROW LEVEL SECURITY")
        agency = cursor.execute("SELECT id FROM agency WHERE id = %(a)s", p).fetchall()
        logged = cursor.execute("SELECT id FROM security_event WHERE agency_id = %(a)s", p)
        assert (agency, logged.fetchall(), cursor.execute(ROWS, p).fetchall()) == ([], [], [])
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        forced = conn.execute(
            "SELECT relname::text, relforcerowsecurity FROM pg_class"
            " WHERE oid = ANY(%s::regclass[])",
            [["agency", *LIFTED]],
        ).fetchall()
    assert dict(forced) == dict.fromkeys(["agency", *LIFTED], True)


SCAN = (  # every security_event row, any agency or none: those holding a sentinel, any case
    "SELECT array_agg(e::text) FILTER (WHERE e::text ILIKE ANY(%(like)s)),"
    " array_agg(e.kind ORDER BY e.kind) FILTER (WHERE e.agency_id = %(a)s) FROM security_event e"
)
PLANT = (  # a pre-tenant row (agency_id null) with a sentinel, only in a rolled-back transaction
    "INSERT INTO security_event (id, at, kind, agency_id, details_json)"
    " VALUES (gen_random_uuid(), now(), 'probe', NULL, jsonb_build_object('n', upper(%(un)s)))"
)
HOLDING = (  # the stored rows that begin with a sentinel
    "SELECT (SELECT count(*) FROM app_user WHERE starts_with(email::text, %(em)s)),"
    " (SELECT count(*) FROM role WHERE starts_with(name, %(rn)s)),"
    " (SELECT count(*) FROM org_unit WHERE starts_with(name, %(un)s))"
)


def scan(cursor: Cursor, p: Ids) -> tuple[list[str] | None, list[str] | None]:
    """As the owner with FORCE lifted: the whole text of every event row holding one of p's
    sentinels, and the kinds of the events of p's agency."""
    like = [f"%{p[key]}%" for key in SENTINELS]
    row = cursor.execute(SCAN, {**p, "like": like}).fetchone()
    assert row is not None
    return row[0], row[1]


def test_no_change_event_holds_an_email_a_role_name_or_a_unit_name() -> None:
    """§7 "Personal data in a change event", after the commit sequence (all ten kinds) has stored
    the sentinels: no event row anywhere holds one. A planted pre-tenant row with one, rolled
    back, shows the scan finds it."""
    p = with_users()
    log, present = Events(p["a"]), set[str]()
    for step in steps(p):
        commit(p, log, step, present)
    with app(p["a"], None) as cursor:
        assert cursor.execute(HOLDING, p).fetchone() == (2, 2, 6)  # users; r1, r2; six units
    kinds = sorted(kind for _, expected, _ in steps(p) for kind, _, _ in expected)
    assert len(set(kinds)) == 10
    with owner(agencies=False) as cursor:
        cursor.execute(PLANT, p)
        leaked, _ = scan(cursor, p)
        assert leaked is not None and len(leaked) == 1 and p["un"].upper() in leaked[0]
    with owner(agencies=False) as cursor:
        assert scan(cursor, p) == (None, kinds)
