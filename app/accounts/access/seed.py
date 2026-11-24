"""The starting-role seed (slice spec Decision 5, Flow 5.5; Decisions 28, 31, 32, 33).

Every agency starts with one role, Owner: the system role (`is_system`) holding every catalogue
pair. No other role is seeded; the owner creates the rest. `seed_starting_roles` runs in the agency
seed transaction after every `migrate` (tenancy.seed, which calls it through its agency steps), as
skiw_migrator, the owner of the tables:

1. Skip when accounts.0028 (the audit triggers) is not applied: migrated back, nothing to seed.
2. Lift FORCE on `role` only and read whether the agency has a system role. The owner is bound by
   FORCE and no policy names it, so a read under FORCE sees no rows. If one exists, FORCE goes back
   on and nothing else happens: no write, no event, and no ALTER TABLE of `role_permission` or
   `security_event` (whose ACCESS EXCLUSIVE lock would stop logins), so an admin's edits stay.
3. Otherwise lift FORCE on `role_permission` and `security_event` too (Decision 33: the audit
   triggers insert there as the migrator), set `skiw.operator` to the reserved code `seed`
   (transaction-local; Decision 31), and insert SEED_DEFAULTS. Every trigger stays on, so each row
   writes its own audit event (Decision 32): 1 `role.created` and 31 `permission.set`.
4. The deferred `role_system_complete` is run before FORCE goes back on (SET CONSTRAINTS ...
   IMMEDIATE): under FORCE the owner would see no ticks, and Postgres refuses ALTER TABLE on a
   table with pending trigger events. Then FORCE back on, checked in pg_class, and the caller's
   operator setting is put back. A raise rolls everything back, FORCE included (DDL is
   transactional).

No Owner assignment (`user_role`) is seeded: an Owner role with no holder is allowed until its
first assignment (Decision 28).
"""

from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID, uuid4

import psycopg

from accounts.access.catalogue import PAIRS, Scope

OPERATOR: Final = "seed"  # reserved: never an operator command's code (Decision 31)
NEEDS: Final = ("accounts", "0028_role_audit_triggers")
READ: Final = ("role",)
WRITTEN: Final = ("role_permission", "security_event")


@dataclass(frozen=True)
class SeedRole:
    name: str
    is_system: bool
    pairs: frozenset[tuple[str, Scope]]


SEED_DEFAULTS: Final[tuple[SeedRole, ...]] = (SeedRole("Owner", True, PAIRS),)


def _forced(cursor: "psycopg.Cursor[Any]", tables: tuple[str, ...]) -> bool:
    row = cursor.execute(
        "SELECT bool_and(relforcerowsecurity) FROM pg_class"
        " WHERE relnamespace = 'public'::regnamespace AND relname = ANY(%s)",
        [list(tables)],
    ).fetchone()
    return row == (True,)


def _force(cursor: "psycopg.Cursor[Any]", tables: tuple[str, ...], on: bool) -> None:
    for table in tables:  # names from this module's constants only
        cursor.execute(f"ALTER TABLE {table} {'' if on else 'NO '}FORCE ROW LEVEL SECURITY")
    if on and not _forced(cursor, tables):
        raise RuntimeError("starting-role seed: FORCE ROW LEVEL SECURITY is not back on")


def seed_starting_roles(cursor: "psycopg.Cursor[Any]", agency_id: UUID) -> bool:
    """Seed SEED_DEFAULTS into an agency with no system role (True); otherwise change nothing
    (False). Runs in the caller's open transaction, which must roll back on a raise."""
    applied = cursor.execute(
        "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s", NEEDS
    ).fetchone()
    if applied is None:
        return False
    if not _forced(cursor, READ + WRITTEN):
        raise RuntimeError("starting-role seed: FORCE must be on before the seed lifts it")
    _force(cursor, READ, on=False)
    found = cursor.execute(
        "SELECT 1 FROM role WHERE agency_id = %s AND is_system", [agency_id]
    ).fetchone()
    if found is not None:
        _force(cursor, READ, on=True)
        return False
    _force(cursor, WRITTEN, on=False)
    (caller,) = cursor.execute(
        "SELECT coalesce(current_setting('skiw.operator', true), '')"
    ).fetchone() or ("",)
    cursor.execute("SELECT set_config('skiw.operator', %s, true)", [OPERATOR])
    for role in SEED_DEFAULTS:
        role_id = uuid4()
        cursor.execute(
            "INSERT INTO role (id, agency_id, name, is_system) VALUES (%s, %s, %s, %s)",
            [role_id, agency_id, role.name, role.is_system],
        )
        codes, scopes = zip(*sorted(role.pairs), strict=True)
        cursor.execute(
            "INSERT INTO role_permission (id, agency_id, role_id, permission_code, scope)"
            " SELECT gen_random_uuid(), %s, %s, code, scope"
            " FROM unnest(%s::text[], %s::text[]) AS pair (code, scope)",
            [agency_id, role_id, list(codes), list(scopes)],
        )
    cursor.execute("SELECT set_config('skiw.operator', %s, true)", [caller])
    # The deferred check runs now, while the owner can still read the rows; Postgres also refuses
    # ALTER TABLE on a table with pending trigger events (55006). Deferred again for the caller.
    cursor.execute("SET CONSTRAINTS role_system_complete IMMEDIATE")
    cursor.execute("SET CONSTRAINTS role_system_complete DEFERRED")
    _force(cursor, READ + WRITTEN, on=True)
    return True
