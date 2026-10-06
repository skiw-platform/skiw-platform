import os
from typing import LiteralString

import psycopg
import pytest
from django.db import connection
from pytest_django import DjangoDbBlocker

pytestmark = pytest.mark.live

APP_ROLE = "skiw_app"
MIGRATOR_ROLE = "skiw_migrator"


def one(conninfo: str, sql: LiteralString, *params: str) -> tuple[object, ...]:
    with psycopg.connect(conninfo) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    assert row is not None
    return row


def test_django_app_connection_runs_as_the_runtime_role(django_db_blocker: DjangoDbBlocker) -> None:
    with django_db_blocker.unblock(), connection.cursor() as cursor:
        cursor.execute("select current_user")
        assert cursor.fetchone() == (APP_ROLE,)


def test_migration_url_runs_as_the_migration_role() -> None:
    assert one(os.environ["MIGRATION_DATABASE_URL"], "select current_user") == (MIGRATOR_ROLE,)


def test_runtime_and_migration_urls_are_different() -> None:
    assert os.environ["DATABASE_URL"] != os.environ["MIGRATION_DATABASE_URL"]


def test_app_role_is_not_superuser_and_cannot_bypass_rls() -> None:
    row = one(
        os.environ["MIGRATION_DATABASE_URL"],
        "select rolsuper, rolbypassrls, rolcreatedb, rolcreaterole from pg_roles "
        "where rolname = %s",
        APP_ROLE,
    )
    assert row == (False, False, False, False)


def test_database_and_schema_belong_to_the_migrator() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"]
    assert one(
        url, "select datdba::regrole::text from pg_database where datname = current_database()"
    ) == (MIGRATOR_ROLE,)
    assert one(
        url, "select nspowner::regrole::text from pg_namespace where nspname = %s", "public"
    ) == (MIGRATOR_ROLE,)


def test_migrator_can_create_objects_in_the_schema() -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("create table skiw_migrator_probe (id int)")
        conn.rollback()


def test_app_role_cannot_create_objects_in_the_schema() -> None:
    with (
        psycopg.connect(os.environ["DATABASE_URL"]) as conn,
        conn.cursor() as cur,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        cur.execute("create table skiw_app_must_not_create (id int)")
