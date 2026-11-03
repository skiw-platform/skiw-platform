"""The deployment agency seed (plan M4c-5, owner Q2 (a); spec §4.1 `agency`, PROJECT §9
second-agency gate). After every `migrate`, in its own transaction after the guard key writes
(TenancyConfig.ready), as `skiw_migrator`, which owns `agency`:

1. `SET LOCAL lock_timeout`, then `LOCK TABLE agency IN ACCESS EXCLUSIVE MODE`.
2. `NO FORCE ROW LEVEL SECURITY`. Under FORCE the owner is bound by RLS and no policy names the
   migrator, so it would read zero rows: the read must come after this step.
3. Read every id. An empty table gets the configured agency; a table that holds the configured id
   is left alone; anything else raises, so a changed SKIW_DEPLOYMENT_AGENCY_ID can never add a
   second agency. The seed never updates or deletes.
4. `FORCE ROW LEVEL SECURITY`, checked in pg_class, then commit. A raise rolls the whole
   transaction back, and DDL is transactional, so FORCE is back on as well.

Outside tests the seed is the only writer of `agency`, and it inserts only into an empty table, so
a host holds at most one row. `insert_agency` is the test-only twin with no one-agency check (the
A/B fixtures need two agencies).
"""

import uuid
from typing import Any

import psycopg
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.migrations.recorder import MigrationRecorder
from psycopg import pq

MIGRATOR = "skiw_migrator"
TABLE_MIGRATION = ("tenancy", "0004_agency")


class SecondAgencyRefused(RuntimeError):
    pass


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


def seed_deployment_agency(cursor: "psycopg.Cursor[Any]", agency_id: uuid.UUID, name: str) -> bool:
    """Insert the configured agency into an empty table (True), or find it there (False); any
    other content raises. Runs in the caller's open transaction, which must roll back on a raise."""
    _lift(cursor)
    ids = stored_ids(cursor)
    if ids and agency_id not in ids:
        raise SecondAgencyRefused(
            f"agency seed: SKIW_DEPLOYMENT_AGENCY_ID {agency_id} is not the agency this database"
            " holds; a second agency is gated (PROJECT §9). Nothing was written."
        )
    if not ids:
        cursor.execute("INSERT INTO agency (id, name) VALUES (%s, %s)", (agency_id, name))
    _restore(cursor)
    return not ids


def insert_agency(cursor: "psycopg.Cursor[Any]", agency_id: uuid.UUID, name: str) -> None:
    """Tests only: insert an agency with no one-agency check (the A/B fixtures). Runs in the
    caller's open transaction, which must roll back on a raise."""
    _lift(cursor)
    cursor.execute(
        "INSERT INTO agency (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
        (agency_id, name),
    )
    _restore(cursor)


def seed_after_migrate(using: str = DEFAULT_DB_ALIAS) -> None:
    connection = connections[using]
    with transaction.atomic(using=using), psycopg.Cursor(connection.connection) as cursor:
        if TABLE_MIGRATION not in MigrationRecorder(connection).applied_migrations():
            return  # migrated back before the table: nothing to seed
        try:
            agency_id, name = settings.SKIW_DEPLOYMENT_AGENCY()
        except ImproperlyConfigured as exc:
            raise CommandError(f"agency seed: {exc}") from None
        try:
            seed_deployment_agency(cursor, agency_id, name)
        except SecondAgencyRefused as exc:
            raise CommandError(str(exc)) from None
        except psycopg.Error as exc:
            raise CommandError(
                f"agency seed failed (SQLSTATE {exc.sqlstate}); nothing was written"
            ) from None
