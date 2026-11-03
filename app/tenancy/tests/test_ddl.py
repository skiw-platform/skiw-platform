"""`tenancy.ddl.as_owner` and the lint-skipped migration name (plan M4c-2a). No database."""

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import psycopg
import pytest
from django.db.migrations.loader import MigrationLoader
from psycopg import pq

from tenancy.ddl import GUARD_OWNERS, as_owner, owner_role

UNLINTED = "0002_guard_key_tables_unlinted"
MAKEFILE = Path(__file__).resolve().parents[3] / "Makefile"


def test_the_owner_set_is_exactly_the_two_nologin_roles() -> None:
    assert frozenset({"skiw_tenant_guard", "skiw_auth_lookup"}) == GUARD_OWNERS


@pytest.mark.parametrize(
    "role",
    [
        "skiw_migrator",
        "skiw_app",
        "skiw_readonly",
        "skiw_backup",
        "postgres",
        "pg_read_all_data",
        "skiw_tenant_guard; DROP SCHEMA guard",
        "SKIW_TENANT_GUARD",
        "",
    ],
)
def test_any_other_role_is_refused(role: str) -> None:
    with pytest.raises(ValueError, match="not a guard owner role"):
        as_owner(role, ["SELECT 1"], ["SELECT 2"])
    # owner_role (plan M4c-3) refuses before it touches the cursor, so no database is needed.
    with (
        pytest.raises(ValueError, match="not a guard owner role"),
        owner_role(cast("psycopg.Cursor[Any]", None), role),
    ):
        pass


class FakeCursor:
    """Records statements; `current_user` reads back as the role, the status is set per test."""

    def __init__(self, role: str, status: pq.TransactionStatus) -> None:
        self.role, self.sent = role, list[str]()
        self.connection = SimpleNamespace(info=SimpleNamespace(transaction_status=status))

    def execute(self, query: object) -> "FakeCursor":
        self.sent.append(query if isinstance(query, str) else "SET LOCAL ROLE")
        return self

    def fetchone(self) -> tuple[str]:
        return (self.role,)


@pytest.mark.parametrize(
    ("status", "reset"),
    [(pq.TransactionStatus.INTRANS, True), (pq.TransactionStatus.INERROR, False)],
)
def test_owner_role_resets_on_an_exception_unless_the_transaction_is_in_error(
    status: pq.TransactionStatus, reset: bool
) -> None:
    fake = FakeCursor("skiw_tenant_guard", status)
    with pytest.raises(LookupError), owner_role(cast("psycopg.Cursor[Any]", fake), fake.role):
        raise LookupError
    assert fake.sent == ["SET LOCAL ROLE", "SELECT current_user::text", *["RESET ROLE"] * reset]


@pytest.mark.parametrize("role", sorted(GUARD_OWNERS))
def test_forward_and_reverse_run_as_the_owner_and_hand_create_back(role: str) -> None:
    op = as_owner(role, ["CREATE TABLE guard.a (x int)"], ["DROP TABLE guard.a"])
    for body, statements in (
        ("CREATE TABLE guard.a (x int)", op.sql),
        ("DROP TABLE guard.a", op.reverse_sql),
    ):
        assert statements == (
            f"GRANT CREATE ON SCHEMA guard TO {role}",
            f"SET LOCAL ROLE {role}",
            f"DO $$BEGIN IF current_user <> '{role}' THEN RAISE EXCEPTION"
            f" 'as_owner: current_user is not {role}; use an atomic migration'; END IF; END$$",
            body,
            "RESET ROLE",
            f"REVOKE CREATE ON SCHEMA guard FROM {role}",
        )


def test_no_statement_holds_a_percent_sign_or_a_line_break() -> None:
    # The linter reads sqlmigrate output line by line; `%` would meet any params formatting.
    op = as_owner("skiw_auth_lookup", ["SELECT 1"], ["SELECT 2"])
    statements = [*op.sql, *(op.reverse_sql or ())]
    assert len(statements) == 12
    assert [s for s in statements if not isinstance(s, str) or "%" in s or "\n" in s] == []


def test_the_lint_skipped_migration_name_is_unique() -> None:
    # lintmigrations --ignore-name matches the name in every app (Makefile `migrate`).
    loader = MigrationLoader(None, ignore_no_migrations=True)
    assert [key for key in loader.disk_migrations if key[1] == UNLINTED] == [("tenancy", UNLINTED)]


def test_make_migrate_skips_only_that_migration() -> None:
    assert re.findall(r"--ignore-name(?:-contains)?\s+(\S+)", MAKEFILE.read_text()) == [UNLINTED]
