"""Writes to the tenant root `agency` (plan M4c-5; spec §4.1 `agency`, PROJECT §9 second-agency
gate). `skiw_migrator` owns the table, and under FORCE the owner is bound by RLS with no policy
naming it, so every write lifts FORCE inside one transaction and puts it back before commit:

1. `SET LOCAL lock_timeout`, then `LOCK TABLE agency IN ACCESS EXCLUSIVE MODE`.
2. `NO FORCE ROW LEVEL SECURITY` (only the owner may), then the write.
3. `FORCE ROW LEVEL SECURITY`, checked in pg_class. A raise rolls the whole transaction back, and
   DDL is transactional, so FORCE is back on as well.

`insert_agency` is the test-only writer, with no one-agency check (the A/B fixtures need two
agencies). The migrate-time seed of the one deployment agency follows in M4c-5-2.
"""

import uuid
from typing import Any

import psycopg
from django.core.management.base import CommandError
from psycopg import pq

MIGRATOR = "skiw_migrator"


def _lift(cursor: "psycopg.Cursor[Any]") -> None:
    row = cursor.execute("SELECT session_user::text, current_user::text").fetchone()
    if row != (MIGRATOR, MIGRATOR):
        raise CommandError(f"agency writes run only as {MIGRATOR}; nothing was written")
    # After a statement: in autocommit the connection is idle again, and LOCK TABLE would fail.
    if cursor.connection.info.transaction_status != pq.TransactionStatus.INTRANS:
        raise RuntimeError("agency writes: run them inside a transaction")
    cursor.execute("SET LOCAL lock_timeout = '5s'")
    cursor.execute("LOCK TABLE agency IN ACCESS EXCLUSIVE MODE")
    cursor.execute("ALTER TABLE agency NO FORCE ROW LEVEL SECURITY")


def _restore(cursor: "psycopg.Cursor[Any]") -> None:
    cursor.execute("ALTER TABLE agency FORCE ROW LEVEL SECURITY")
    row = cursor.execute(
        "SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.agency'::regclass"
    ).fetchone()
    if row != (True,):
        raise RuntimeError("agency writes: FORCE ROW LEVEL SECURITY is not back on")


def stored_ids(cursor: "psycopg.Cursor[Any]") -> set[uuid.UUID]:
    """Every agency id; only meaningful between `_lift` and `_restore`."""
    return {agency for (agency,) in cursor.execute("SELECT id FROM agency").fetchall()}


def insert_agency(cursor: "psycopg.Cursor[Any]", agency_id: uuid.UUID, name: str) -> None:
    """Tests only: insert an agency with no one-agency check (the A/B fixtures). Runs in the
    caller's open transaction, which must roll back on a raise."""
    _lift(cursor)
    cursor.execute(
        "INSERT INTO agency (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
        (agency_id, name),
    )
    _restore(cursor)
