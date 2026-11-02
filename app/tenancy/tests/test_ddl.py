"""`tenancy.ddl.as_owner` and the lint-skipped migration name (plan M4c-2a). No database."""

import re
from pathlib import Path

import pytest
from django.db.migrations.loader import MigrationLoader

from tenancy.ddl import GUARD_OWNERS, as_owner

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
            body,
            "RESET ROLE",
            f"REVOKE CREATE ON SCHEMA guard FROM {role}",
        )


def test_the_lint_skipped_migration_name_is_unique() -> None:
    # lintmigrations --ignore-name matches the name in every app (Makefile `migrate`).
    loader = MigrationLoader(None, ignore_no_migrations=True)
    assert [key for key in loader.disk_migrations if key[1] == UNLINTED] == [("tenancy", UNLINTED)]


def test_make_migrate_skips_only_that_migration() -> None:
    assert re.findall(r"--ignore-name(?:-contains)?\s+(\S+)", MAKEFILE.read_text()) == [UNLINTED]
