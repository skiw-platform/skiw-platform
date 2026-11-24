"""The org_unit tree guard, the system-role guards and the deferred checks on the live schema (plan
row M4r-1d, split M4r-1d-ii; slice spec Decisions 2, 27, 28; accounts.0027). As in
test_roles_guards_live: the owner, skiw_migrator, on one connection in one transaction under
transaction-local NO FORCE with a test skiw.operator, rolled back. A deferred check runs where the
test says SET CONSTRAINTS ALL IMMEDIATE (Postgres then runs the pending checks a COMMIT would run);
the refused cases are also shown by a real COMMIT. No seed exists yet (M4r-1f), so each test builds
its own Owner role. The two-connection races are M4r-1h."""

import importlib
import os
import uuid
from collections.abc import Callable

import psycopg
import pytest
from psycopg import IsolationLevel

from accounts.access.catalogue import PAIRS
from accounts.tests.test_access_tables_live import add_role
from accounts.tests.test_org_tables_live import add_root, add_unit, add_user, assign, assignment
from accounts.tests.test_roles_guards_live import (
    LIFTED,
    NOT_READ_COMMITTED,
    REFUSED,
    Cursor,
    X,
    Y,
    owner,
    refusal,
    revoke_writes,
    tick,
)
from tenancy import seed

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

MIGRATION = importlib.import_module("accounts.migrations.0027_tree_system_role_guards")
DEPTH = 32  # ORG_MAX_DEPTH, slice spec §8; a literal, so a changed cap fails here
CYCLE = ("23514", "roles change refused: the org unit tree would have a cycle")
DEEP = ("23514", f"roles change refused: the org unit tree would be deeper than {DEPTH} levels")
PROTECTED = ("42501", "roles change refused: the system role is protected")
INCOMPLETE = ("23514", "roles change refused: the system role must hold every permission")
NO_HOLDER = ("23514", "roles change refused: the system role must keep a holder")
NOW = "SET CONSTRAINTS ALL IMMEDIATE"  # stays IMMEDIATE for the transaction; see checked()
MOVE = "UPDATE org_unit SET parent_id = %s WHERE id = %s"
UNDER = (
    "INSERT INTO org_unit (id, agency_id, parent_id, kind, name)"
    " VALUES (gen_random_uuid(), %s, %s, 'team', 'T')"
)
EVERY_PAIR = (
    "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
    " SELECT gen_random_uuid(), %s, %s, code, scope FROM permission"
)


def checked(cursor: Cursor) -> None:
    """Run the pending deferred checks now, then defer the later ones again."""
    cursor.execute(NOW)
    cursor.execute("SET CONSTRAINTS ALL DEFERRED")


def chain(cursor: Cursor, agency: uuid.UUID, levels: int) -> list[uuid.UUID]:
    """A root and units under each other, `levels` deep (the root is level 1)."""
    units = [add_root(cursor, agency)]
    for _ in range(levels - 1):
        units.append(add_unit(cursor, agency, units[-1]))
    return units


@pytest.mark.parametrize("below", [0, 1, 2], ids=["itself", "its-child", "its-grandchild"])
def test_a_unit_cannot_move_under_itself_or_its_descendants(below: int) -> None:
    """Self-parent, 2- and 3-step cycles by a move (slice spec §7)."""
    with owner() as cursor:
        root, a, *under_a = chain(cursor, X, 4)
        target = [a, *under_a][below]
        assert refusal(cursor, MOVE, [target, a]) == CYCLE
        cursor.execute(MOVE, [root, under_a[-1]])  # a move that keeps the tree acyclic


def test_a_swap_in_one_statement_is_refused() -> None:
    """Row-level BEFORE triggers see the rows the same statement changed before them."""
    with owner() as cursor:
        root = add_root(cursor, X)
        a, b = add_unit(cursor, X, root), add_unit(cursor, X, root)
        swap = "UPDATE org_unit SET parent_id = CASE id WHEN %(a)s THEN %(b)s ELSE %(a)s END"
        assert refusal(cursor, f"{swap} WHERE id IN (%(a)s, %(b)s)", {"a": a, "b": b}) == CYCLE


def test_the_root_rules_hold_beside_the_guard() -> None:
    with owner() as cursor:
        root, unit = chain(cursor, X, 2)
        second = "INSERT INTO org_unit (id, agency_id, kind, name) VALUES (%s, %s, 'agency', 'R')"
        assert refusal(cursor, second, [uuid.uuid4(), X])[0] == "23505"  # one root per agency
        assert refusal(cursor, MOVE, [None, unit])[0] == "23514"  # only the root has no parent
        assert refusal(cursor, MOVE, [unit, root]) == CYCLE  # the root under its own child


def test_a_path_of_32_units_is_accepted_and_a_33rd_level_is_refused() -> None:
    assert MIGRATION.ORG_MAX_DEPTH == DEPTH
    with owner() as cursor:
        units = chain(cursor, X, DEPTH)
        assert refusal(cursor, UNDER, [X, units[-1]]) == DEEP
        add_unit(cursor, X, units[-2])  # a sibling at level 32 is accepted


def test_a_move_counts_the_levels_below_the_moved_unit() -> None:
    with owner() as cursor:
        units = chain(cursor, X, DEPTH - 1)
        top = add_unit(cursor, X, units[0])
        add_unit(cursor, X, top)  # a subtree two levels high
        assert refusal(cursor, MOVE, [units[-1], top]) == DEEP  # its leaf would be at level 33
        cursor.execute(MOVE, [units[-2], top])  # leaf at level 32: accepted


def test_a_planted_cycle_is_found_and_the_walk_ends() -> None:
    """Two units made to point at each other with the guard off (the owner, rolled back): a unit
    added under either is refused as a cycle, not by the depth cap."""
    with owner() as cursor:
        root = add_root(cursor, X)
        p, q = add_unit(cursor, X, root), add_unit(cursor, X, root)
        cursor.execute("ALTER TABLE org_unit DISABLE TRIGGER org_unit_tree_guard")
        cursor.execute(MOVE, [q, p])
        cursor.execute(MOVE, [p, q])
        cursor.execute("ALTER TABLE org_unit ENABLE TRIGGER org_unit_tree_guard")
        unit = add_unit(cursor, Y, add_root(cursor, Y))
        # A unit of agency Y moved under p: the walk stays in Y, so the FK is what refuses it.
        assert refusal(cursor, MOVE, [p, unit])[0] == "23503"
        for parent in (p, q):
            assert refusal(cursor, UNDER, [X, parent]) == CYCLE


def test_the_tree_guard_runs_after_the_roles_lock() -> None:
    """A REPEATABLE READ move that would make a cycle gets the lock trigger's refusal, so the lock
    trigger fired first (the rows are made with it off, in this rolled-back transaction)."""
    with owner(IsolationLevel.REPEATABLE_READ) as cursor:
        cursor.execute("ALTER TABLE org_unit DISABLE TRIGGER org_unit_roles_lock")
        _, a, b = chain(cursor, X, 3)
        cursor.execute("ALTER TABLE org_unit ENABLE TRIGGER org_unit_roles_lock")
        assert refusal(cursor, MOVE, [b, a]) == NOT_READ_COMMITTED


def owner_role(cursor: Cursor, agency: uuid.UUID) -> uuid.UUID:
    """The agency's system role with every catalogue pair, as the M4r-1f seed will make it."""
    role = add_role(cursor, "Owner", agency=agency, is_system=True)
    cursor.execute(EVERY_PAIR, [agency, role])
    return role


UNIQUE = 'duplicate key value violates unique constraint "role_one_system_per_agency"'
OWNER_CHANGES = {
    "delete": ("DELETE FROM role WHERE id = %(r)s", PROTECTED),
    "untick-one": (
        "DELETE FROM role_permission WHERE role_id = %(r)s AND permission_code = 'staff.manage'",
        PROTECTED,
    ),
    "untick-all": ("DELETE FROM role_permission WHERE role_id = %(r)s", PROTECTED),
    "is_system-off": ("UPDATE role SET is_system = false WHERE id = %(r)s", REFUSED),
    "second-system-role": (
        "INSERT INTO role (id, agency_id, name, is_system)"
        " VALUES (gen_random_uuid(), %(a)s, 'Other', true)",
        ("23505", UNIQUE),
    ),
}


@pytest.mark.parametrize("change", OWNER_CHANGES)
def test_the_owner_role_is_protected(change: str) -> None:
    with owner() as cursor:
        role = owner_role(cursor, X)
        sql, expected = OWNER_CHANGES[change]
        assert refusal(cursor, sql, {"r": role, "a": X}) == expected
        cursor.execute("UPDATE role SET name = 'Owners' WHERE id = %s", [role])  # rename: allowed
        other = add_role(cursor, "Staff", agency=X)  # a role that is not the system role
        cursor.execute("DELETE FROM role_permission WHERE id = %s", [tick(cursor, X, other)])
        cursor.execute("DELETE FROM role WHERE id = %s", [other])
        checked(cursor)
        ticks = cursor.execute("SELECT count(*) FROM role_permission WHERE role_id = %s", [role])
        assert ticks.fetchone() == (len(PAIRS),)  # the Owner role still holds every pair


def commit_refusal(build: Callable[[Cursor, uuid.UUID], None]) -> tuple[str, str]:
    """`build` for a fresh agency in an owner transaction that is then committed; the error the
    COMMIT raises. If a COMMIT is accepted (a broken check), FORCE goes back on before the fail."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT set_config('skiw.operator', 'test-operator', true)")
        for table in LIFTED:
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        agency = uuid.uuid4()
        seed.insert_agency(cursor, agency, "Commit test")
        build(cursor, agency)
        try:
            conn.commit()
        except psycopg.Error as error:
            return str(error.sqlstate), str(error.diag.message_primary)
        with conn.transaction():
            for table in LIFTED:
                cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        pytest.fail("the COMMIT was accepted")


def incomplete_owner(cursor: Cursor, agency: uuid.UUID) -> None:
    role = add_role(cursor, "Owner", agency=agency, is_system=True)
    cursor.execute(
        f"{EVERY_PAIR} WHERE (code, scope) <> ('staff.manage', 'agency')", [agency, role]
    )


def last_owner_removed(cursor: Cursor, agency: uuid.UUID) -> None:
    ids = {**assignment(cursor, agency), "role_id": owner_role(cursor, agency)}
    assign(cursor, agency, ids, "both")
    cursor.execute("DELETE FROM user_role WHERE agency_id = %s", [agency])


def test_a_system_role_missing_a_pair_is_refused_at_commit() -> None:
    assert commit_refusal(incomplete_owner) == INCOMPLETE


def test_removing_the_last_owner_assignment_is_refused_at_commit() -> None:
    assert commit_refusal(last_owner_removed) == NO_HOLDER


def test_a_system_role_built_over_several_statements_passes_at_commit() -> None:
    with owner() as cursor:
        role = add_role(cursor, "Owner", agency=X, is_system=True)
        for code, scope in cursor.execute("SELECT code, scope FROM permission").fetchall():
            cursor.execute(
                "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
                " VALUES (gen_random_uuid(), %s, %s, %s, %s)",
                [X, role, code, scope],
            )
        add_role(cursor, "No ticks", agency=X)  # not the system role: no check
        checked(cursor)
        incomplete_owner(cursor, Y)
        assert refusal(cursor, NOW) == INCOMPLETE


def owners(cursor: Cursor, agency: uuid.UUID, holders: int) -> dict[str, uuid.UUID]:
    """The Owner role, a unit and `holders` users who hold the role there (user ids u0, u1, …)."""
    ids = {**assignment(cursor, agency), "role_id": owner_role(cursor, agency)}
    for n in range(holders):
        ids[f"u{n}"] = ids["user_id"] if n == 0 else add_user(cursor, agency)
        assign(cursor, agency, {**ids, "user_id": ids[f"u{n}"]}, "both")
    return ids


UNASSIGN = "DELETE FROM user_role WHERE user_id = %s"


def test_owner_assignments_may_change_while_one_remains() -> None:
    with owner() as cursor:
        two = owners(cursor, X, 2)
        cursor.execute(UNASSIGN, [two["u0"]])  # one of two removed
        checked(cursor)
        one = owners(cursor, Y, 1)
        cursor.execute(UNASSIGN, [one["u0"]])  # the only one removed, then another assigned
        assign(cursor, Y, {**one, "user_id": add_user(cursor, Y)}, "investment")
        checked(cursor)


def test_removing_every_owner_assignment_in_one_statement_is_refused() -> None:
    with owner() as cursor:
        owners(cursor, X, 2)
        cursor.execute("DELETE FROM user_role WHERE agency_id = %s", [X])
        assert refusal(cursor, NOW) == NO_HOLDER


def test_an_owner_role_with_no_holder_yet_is_allowed() -> None:
    with owner() as cursor:
        ids = owners(cursor, X, 0)
        checked(cursor)
        other = {**ids, "role_id": add_role(cursor, "Staff", agency=X)}
        assign(cursor, X, other, "both")
        cursor.execute("DELETE FROM user_role WHERE agency_id = %s", [X])  # not an Owner row
        assign(cursor, X, ids, "both")  # the first Owner assignment
        checked(cursor)


def test_the_holder_check_fails_closed_when_the_writer_cannot_see_the_agency() -> None:
    """FORCE back on for role and org_unit before the check: the owner, with no tenant token, then
    sees neither, as a skiw_app writer that changed its token before commit would."""
    with owner() as cursor:
        ids = owners(cursor, X, 2)
        checked(cursor)  # no pending role events, so ALTER TABLE role is allowed
        for table in ("role", "org_unit"):
            cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        cursor.execute(UNASSIGN, [ids["u0"]])
        assert refusal(cursor, NOW) == NO_HOLDER


def test_the_reverse_refuses_while_skiw_app_holds_a_write_grant() -> None:
    assert MIGRATION.REVERSE[0] == MIGRATION.LOCKS.GUARD  # the 0026 guard, the same statement
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)  # accounts.0030's grants, so the one below is what the guard sees
        cursor.execute("GRANT DELETE ON user_role TO skiw_app")
        assert refusal(cursor, MIGRATION.REVERSE[0])[0] == "55000"


def test_without_a_write_grant_the_reverse_drops_its_triggers_and_functions() -> None:
    with owner(agencies=False) as cursor:
        revoke_writes(cursor)
        for statement in MIGRATION.REVERSE:
            cursor.execute(statement)
        names = [name for name, _, _ in MIGRATION.TRIGGERS]
        left = cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname = ANY(%s)", [names])
        assert left.fetchone() == (0,)
        for function in MIGRATION.FUNCTIONS:
            row = cursor.execute("SELECT to_regprocedure(%s)", [function]).fetchone()
            assert row == (None,)
