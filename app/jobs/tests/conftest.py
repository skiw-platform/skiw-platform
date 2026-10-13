import os
import uuid
from collections.abc import Iterator
from typing import Any, LiteralString

import psycopg
import pytest
from django.db import connection, transaction
from pytest_django import DjangoDbBlocker

from jobs.enqueue import enqueue_in_tx
from jobs.registry import JobTask


@pytest.fixture(scope="session")
def django_db_setup() -> None:
    """Use the database `make migrate` already prepared as skiw_migrator. skiw_app has
    NOCREATEDB and no TRUNCATE, so pytest-django must neither create a test database nor
    flush one; tests commit for real and tell their rows apart by fresh uuids."""


@pytest.fixture(scope="session")
def probe_table() -> Iterator[None]:
    """Test-only table the probe ids point at; no tenant data. skiw_app may only SELECT and
    INSERT, like a migration-created table would grant."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS jobs_probe (id uuid PRIMARY KEY)")
        conn.execute("GRANT SELECT, INSERT ON jobs_probe TO skiw_app")
        yield
        conn.execute("DROP TABLE jobs_probe")


@pytest.fixture
def unapplied_jobs_migration() -> Iterator[None]:
    """Make the migration record say jobs.0001 was never applied, then put the row back.
    The grants stay in place; only the record changes, through the owner role."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
        row = conn.execute(
            "DELETE FROM django_migrations WHERE app = 'jobs' RETURNING app, name, applied"
        ).fetchone()
        assert row is not None
        try:
            yield
        finally:
            conn.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)", row
            )


@pytest.fixture
def live_db(
    django_db_setup: None, django_db_blocker: DjangoDbBlocker, probe_table: None
) -> Iterator[None]:
    """The real Django connection (skiw_app), in autocommit, outside any test transaction."""
    with django_db_blocker.unblock():
        yield


def separate(sql: LiteralString, *params: object) -> list[tuple[Any, ...]]:
    """Run `sql` on a new skiw_app connection, i.e. outside the Django connection's transaction."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()


def insert_probe_and_enqueue(task: JobTask, probe_id: uuid.UUID) -> int:
    """The EVT-01 shape: a data row and its job written in one transaction."""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("INSERT INTO jobs_probe (id) VALUES (%s)", [probe_id])
        return enqueue_in_tx(task, probe_id=probe_id)
