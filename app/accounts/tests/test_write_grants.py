"""accounts.0030 without a database (plan row M4r-1g, split M4r-1g-i; slice spec Decisions 3, 32,
33): the precondition is the first statement and names exactly the triggers accounts.0025 to 0029
create, with the schema check's security_event predicate; the grants are Decision 3; and no earlier
accounts migration grants a roles table more than SELECT, so no prefix of the deployment sequence
has a write grant (the live prefix walk is test_write_grants_live)."""

import importlib
import re
from types import ModuleType

from django.db import migrations
from django.db.migrations.loader import MigrationLoader

from tenancy.check import EVENT_DEPARSED

MIGRATION = importlib.import_module("accounts.migrations.0030_roles_write_grants")
CREATE_TRIGGER = re.compile(r"CREATE (?:CONSTRAINT )?TRIGGER (\w+) .*? ON (?:public\.)?(\w+) ")
GRANT = re.compile(r"\b(GRANT|REVOKE) (.+?) ON (?:public\.)?(\w+) (?:TO|FROM) (\w+)")
ROLES_TABLES = ("permission", "role", "role_permission", "org_unit", "user_role")
DECISION_3_WRITES = {
    ("role", "INSERT"),
    ("role", "UPDATE (name)"),
    ("role", "DELETE"),
    ("role_permission", "INSERT"),
    ("role_permission", "DELETE"),
    ("org_unit", "INSERT"),
    ("org_unit", "UPDATE"),
    ("user_role", "INSERT"),
    ("user_role", "DELETE"),
}


def statements(migration: ModuleType | migrations.Migration) -> list[str]:
    found: list[str] = []
    for operation in migration.operations:
        if isinstance(operation, migrations.RunSQL):
            sql = operation.sql
            found += [sql] if isinstance(sql, str) else [str(s) for s in sql]
    return found


def grants(sql: list[str], verb: str) -> set[tuple[str, str]]:
    return {
        (table, privilege.strip())
        for statement in sql
        for found, privileges, table, role in GRANT.findall(statement)
        if found == verb and role == "skiw_app"
        for privilege in privileges.split(",")
    }


def test_the_precondition_names_exactly_the_triggers_0025_to_0029_create() -> None:
    created = {
        (table, name)
        for number in range(25, 30)
        for (app, migration_name), migration in LOADER.disk_migrations.items()
        if app == "accounts" and migration_name.startswith(f"00{number}_")
        for statement in statements(migration)
        for name, table in CREATE_TRIGGER.findall(statement)
    }
    frozen = {(table, name) for table, names in MIGRATION.DECISION_32.items() for name in names}
    assert frozen == created and len(frozen) == 22
    assert MIGRATION.P == EVENT_DEPARSED


def test_the_precondition_comes_first_and_the_grants_are_exactly_decision_3() -> None:
    (operation,) = MIGRATION.Migration.operations
    assert operation.sql == MIGRATION.FORWARD and operation.reverse_sql == MIGRATION.REVERSE
    assert MIGRATION.FORWARD[0] == MIGRATION.PRECONDITION
    assert MIGRATION.PRECONDITION.startswith("DO $pre$") and "GRANT" not in MIGRATION.PRECONDITION
    assert grants(MIGRATION.FORWARD, "GRANT") == DECISION_3_WRITES
    assert grants(MIGRATION.REVERSE, "REVOKE") == DECISION_3_WRITES
    assert not grants(MIGRATION.FORWARD, "REVOKE") and not grants(MIGRATION.REVERSE, "GRANT")


LOADER = MigrationLoader(None, ignore_no_migrations=True)


def test_no_earlier_accounts_migration_grants_a_roles_table_more_than_select() -> None:
    found = sorted(
        (name[:4], table, privilege)
        for (app, name), migration in LOADER.disk_migrations.items()
        if app == "accounts" and name < "0030"
        for table, privilege in grants(statements(migration), "GRANT")
        if table in ROLES_TABLES
    )
    assert found == [
        ("0018", "permission", "SELECT"),
        ("0018", "role", "SELECT"),
        ("0018", "role_permission", "SELECT"),
        ("0021", "org_unit", "SELECT"),
        ("0021", "user_role", "SELECT"),
    ]
