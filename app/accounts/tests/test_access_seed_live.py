"""The starting-role seed on the live schema (plan row M4r-1f; slice spec Decision 5, Flow 5.5,
Decisions 28, 31, 32, 33; accounts.access.seed). The seed runs as the migrator through
tenancy.seed.insert_agency(steps=True), the test twin of the agency seed; `make migrate` ran it for
the deployment agency. Rows are read as the owner in a rolled-back transaction with FORCE lifted,
or as skiw_app through with_agency()."""

import json
import os
import uuid
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, cast

import psycopg
import pytest
from django.db import connection

from accounts.access import seed as roles_seed
from accounts.access.catalogue import PAIRS, Scope
from accounts.access.seed import SeedRole, seed_starting_roles
from tenancy import seed
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

SEEDED = ("role", "role_permission", "security_event")
OPERATOR = "SELECT current_setting('skiw.operator', true)"
type Cursor = psycopg.Cursor[Any]


def migrator() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["MIGRATION_DATABASE_URL"])


def forced() -> bool:
    with migrator() as conn:
        rows = conn.execute(
            "SELECT relname FROM pg_class WHERE relname = ANY(%s) AND relforcerowsecurity"
            " AND relnamespace = 'public'::regnamespace",
            [list(SEEDED)],
        ).fetchall()
    return len(rows) == len(SEEDED)


def snapshot(cursor: Cursor, agency: uuid.UUID) -> dict[str, Any]:
    """The agency's roles, ticks, assignments and change events, read under lifted FORCE that is
    put back before returning (inside the caller's transaction)."""
    for table in (*SEEDED, "user_role"):
        cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    read = {
        "roles": "SELECT id, name, is_system FROM role WHERE agency_id = %s ORDER BY name",
        "ticks": "SELECT role_id, permission_code, scope FROM role_permission WHERE agency_id = %s",
        "holders": "SELECT id FROM user_role WHERE agency_id = %s",
        "events": "SELECT kind, details_json FROM security_event WHERE agency_id = %s",
    }
    found = {name: cursor.execute(sql, [agency]).fetchall() for name, sql in read.items()}
    for table in (*SEEDED, "user_role"):
        cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    found["ticks"].sort()
    found["events"].sort(key=lambda event: json.dumps(event, sort_keys=True))
    return found


@contextmanager
def rolled_back() -> Iterator[Cursor]:
    with migrator() as conn, conn.transaction(force_rollback=True), conn.cursor() as cursor:
        yield cursor


class Recording:
    """Stands in for the seed's cursor (it calls only execute) and keeps the statement log."""

    def __init__(self, cursor: Cursor) -> None:
        self.cursor, self.log = cursor, list[str]()

    def execute(self, query: str, params: Sequence[object] = ()) -> Cursor:
        self.log.append(query)
        return self.cursor.execute(query, params)


def test_a_fresh_agency_gets_the_owner_role_with_31_ticks_and_32_seed_events() -> None:
    """Committed: role_system_complete passed (the seed runs it before FORCE goes back on) and
    nothing was left for COMMIT to refuse."""
    agency = uuid.uuid4()
    with migrator() as conn, conn.cursor() as cursor:
        seed.insert_agency(cursor, agency, "Seed test", steps=True)
        assert cursor.execute(OPERATOR).fetchone() == ("",)  # the caller's (unset) value is back
    assert forced()
    with rolled_back() as cursor:
        found = snapshot(cursor, agency)
    events = found["events"]
    [(role, name, is_system)] = found["roles"]
    assert (name, is_system) == ("Owner", True)
    assert {(r, code, scope) for r, code, scope in found["ticks"]} == {(role, *p) for p in PAIRS}
    assert found["holders"] == []  # no Owner assignment is seeded (Decision 28 allows none yet)
    assert Counter(kind for kind, _ in events) == {"role.created": 1, "permission.set": 31}
    assert {details["operator"] for _, details in events} == {"seed"}
    assert {details["role_id"] for _, details in events} == {str(role)}
    ticked = {(d["permission_code"], d["scope"]) for k, d in events if k == "permission.set"}
    assert ticked == PAIRS
    with with_agency(agency), connection.cursor() as app:  # skiw_app sees them through RLS
        app.execute("SELECT count(*) FROM role_permission WHERE role_id = %s", [role])
        assert app.fetchone() == (31,)


def test_make_migrate_seeded_the_deployment_agency() -> None:
    agency = uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])
    with with_agency(agency), connection.cursor() as app:
        app.execute(
            "SELECT count(*) FROM role_permission WHERE role_id ="
            " (SELECT id FROM role WHERE is_system)"
        )
        assert app.fetchone() == (31,)


def test_a_second_run_changes_nothing_writes_no_event_and_alters_only_role() -> None:
    """Only the read lifts FORCE, on `role`: no ALTER TABLE of role_permission or security_event,
    whose ACCESS EXCLUSIVE lock would stop logins (Flow 5.5)."""
    agency = uuid.uuid4()
    with migrator() as conn, conn.transaction(force_rollback=True), conn.cursor() as cursor:
        seed.insert_agency(cursor, agency, "Seed twice", steps=True)
        before = snapshot(cursor, agency)
        second = Recording(cursor)
        assert seed_starting_roles(cast(Cursor, second), agency) is False
        assert snapshot(cursor, agency) == before
    assert len(before["events"]) == 32
    altered = [statement for statement in second.log if "ALTER" in statement.upper()]
    assert altered == [
        "ALTER TABLE role NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE role FORCE ROW LEVEL SECURITY",
    ]
    assert not [s for s in second.log if s.upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def test_an_agency_whose_roles_were_edited_is_left_untouched() -> None:
    agency = uuid.uuid4()
    with rolled_back() as cursor:
        cursor.execute("SELECT set_config('skiw.operator', 'test-operator', true)")
        seed.insert_agency(cursor, agency, "Edited", steps=True)
        assert cursor.execute(OPERATOR).fetchone() == ("test-operator",)
        for table in SEEDED:
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        cursor.execute("UPDATE role SET name = 'Founder' WHERE agency_id = %s", [agency])
        cursor.execute(
            "WITH r AS (INSERT INTO role (id, agency_id, name) VALUES (gen_random_uuid(), %s,"
            " 'Adviser') RETURNING id) INSERT INTO role_permission (id, agency_id, role_id,"
            " permission_code, scope) SELECT gen_random_uuid(), %s, id, 'client.view', 'own'"
            " FROM r",
            [agency, agency],
        )
        for table in SEEDED:
            cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        before = snapshot(cursor, agency)
        assert seed_starting_roles(cursor, agency) is False
        assert snapshot(cursor, agency) == before
    assert [name for _, name, _ in before["roles"]] == ["Adviser", "Founder"]
    assert len(before["events"]) == 32 + 3  # rename, create, tick


@pytest.mark.parametrize("broken", ["pair-missing", "unknown-pair"])
def test_a_failed_seed_leaves_force_on_and_writes_nothing(
    broken: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pair-missing fails role_system_complete (run by the seed before FORCE goes back on);
    unknown-pair fails the FK at once. Both after FORCE was lifted."""
    unknown: frozenset[tuple[str, Scope]] = frozenset({("client.fly", "own")})
    pairs = {
        "pair-missing": PAIRS - {("staff.manage", "agency")},
        "unknown-pair": PAIRS | unknown,
    }[broken]
    monkeypatch.setattr(roles_seed, "SEED_DEFAULTS", (SeedRole("Owner", True, pairs),))
    agency = uuid.uuid4()
    with pytest.raises(psycopg.Error) as caught, migrator() as conn:
        with conn.cursor() as cursor:
            seed.insert_agency(cursor, agency, "Broken", steps=True)
        conn.commit()
    assert caught.value.sqlstate == {"pair-missing": "23514", "unknown-pair": "23503"}[broken]
    assert forced()
    with rolled_back() as cursor:
        assert snapshot(cursor, agency) == {"roles": [], "ticks": [], "holders": [], "events": []}


def test_the_seed_refuses_a_caller_that_lifted_force() -> None:
    """Else its own FORCE-back-on would hide a caller (or a mutant) that left FORCE off."""
    with rolled_back() as cursor:
        cursor.execute("ALTER TABLE security_event NO FORCE ROW LEVEL SECURITY")
        with pytest.raises(RuntimeError, match="FORCE must be on"):
            seed.insert_agency(cursor, uuid.uuid4(), "Lifted", steps=True)


def test_the_seed_skips_a_database_migrated_back_before_the_audit_triggers() -> None:
    agency = uuid.uuid4()
    with rolled_back() as cursor:
        cursor.execute(
            "DELETE FROM django_migrations WHERE app = %s AND name = %s", roles_seed.NEEDS
        )
        seed.insert_agency(cursor, agency, "Migrated back", steps=True)
        assert snapshot(cursor, agency)["roles"] == []
