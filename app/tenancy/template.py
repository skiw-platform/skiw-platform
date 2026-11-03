"""The tenant-table template (spec §4, §4.2; plan M4c-6a). A tenant table's migration creates the
table from a `TenantModel` (which carries `unique (agency_id, id)`), then appends
`tenant_table(...)`: the FK to `agency`, the composite FKs to tenant parents, ENABLE + FORCE, the
restrictive policy, one permissive policy per granted command and the matching `skiw_app` grant.

Each step is one `RunSQL` with its exact reverse. Each statement is one line with no `%` (the
migration linter reads sqlmigrate output line by line). Names are checked, not quoted, so a table
or column name cannot carry SQL.
"""

import re
from collections.abc import Collection, Sequence

from django.db import migrations

APP_ROLE = "skiw_app"
PREDICATE = "agency_id = (SELECT guard.current_agency())"
# Spec §4.2: SELECT and DELETE filter with USING, INSERT checks with WITH CHECK, UPDATE does both.
COMMANDS = {
    "SELECT": ("sel", f"USING ({PREDICATE})"),
    "INSERT": ("ins", f"WITH CHECK ({PREDICATE})"),
    "UPDATE": ("upd", f"USING ({PREDICATE}) WITH CHECK ({PREDICATE})"),
    "DELETE": ("del", f"USING ({PREDICATE})"),
}
ROOT = "agency"
NAME = re.compile(r"[a-z_][a-z0-9_]*")
MAX_NAME = 63  # Postgres NAMEDATALEN - 1


def _name(value: str, what: str) -> str:
    if not NAME.fullmatch(value) or len(value) > MAX_NAME:
        raise ValueError(f"tenant_table: {what} {value!r} is not a plain lowercase name")
    return value


# Forward statements and their exact reverse. Tuples: RunSQL takes a covariant sequence.
Step = tuple[tuple[str, ...], tuple[str, ...]]


def tenant_table(
    table: str,
    *,
    commands: Collection[str],
    composite_fks: Sequence[tuple[str, str]] = (),
) -> list[migrations.RunSQL]:
    """The §4.2 operations for `table`, one `RunSQL` per step of `tenant_table_sql`."""
    return [
        migrations.RunSQL(sql=forward, reverse_sql=reverse)
        for forward, reverse in tenant_table_sql(
            table, commands=commands, composite_fks=composite_fks
        )
    ]


def tenant_table_sql(
    table: str,
    *,
    commands: Collection[str],
    composite_fks: Sequence[tuple[str, str]] = (),
) -> list[Step]:
    """The §4.2 statements for `table`, as (forward, reverse) steps. `commands` is the closed
    set `skiw_app` gets, each with its permissive policy (an append-only table leaves out UPDATE
    and DELETE, TEN-03).
    `composite_fks` holds `(column, parent)` pairs: `(agency_id, column)` references
    `parent(agency_id, id)`, so a row cannot point at another agency's parent."""
    _name(table, "table")
    if table == ROOT:
        raise ValueError("tenant_table: `agency` is the tenant root, not a tenant table")
    unknown = set(commands) - set(COMMANDS)
    if not commands or unknown:
        raise ValueError(f"tenant_table: commands must be a non-empty subset of {list(COMMANDS)}")
    granted = [command for command in COMMANDS if command in commands]

    def constraint(suffix: str) -> str:
        return _name(f"{table}_{suffix}", "constraint")

    operations: list[Step] = [
        _step(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint('agency_fk')}"
            f" FOREIGN KEY (agency_id) REFERENCES {ROOT}(id)",
            reverse=f"ALTER TABLE {table} DROP CONSTRAINT {constraint('agency_fk')}",
        )
    ]
    columns = [column for column, _ in composite_fks]
    if len(set(columns)) != len(columns):
        raise ValueError("tenant_table: one composite FK per column")
    for column, parent in composite_fks:
        _name(column, "column")
        _name(parent, "parent")
        if column == "agency_id" or parent == ROOT:
            raise ValueError("tenant_table: the FK to `agency` is added already")
        name = constraint(f"{column}_fk")
        operations.append(
            _step(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY (agency_id, {column})"
                f" REFERENCES {parent}(agency_id, id)",
                reverse=f"ALTER TABLE {table} DROP CONSTRAINT {name}",
            )
        )
    tenant = constraint("tenant")
    operations.append(
        (
            (
                f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
                f"CREATE POLICY {tenant} ON {table} AS RESTRICTIVE FOR ALL TO {APP_ROLE}"
                f" USING ({PREDICATE}) WITH CHECK ({PREDICATE})",
            ),
            (
                f"DROP POLICY {tenant} ON {table}",
                f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
                f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
            ),
        )
    )
    for command in granted:
        suffix, clauses = COMMANDS[command]
        name = constraint(suffix)
        operations.append(
            _step(
                f"CREATE POLICY {name} ON {table} FOR {command} TO {APP_ROLE} {clauses}",
                reverse=f"DROP POLICY {name} ON {table}",
            )
        )
    privileges = ", ".join(granted)
    operations.append(
        _step(
            f"GRANT {privileges} ON {table} TO {APP_ROLE}",
            reverse=f"REVOKE {privileges} ON {table} FROM {APP_ROLE}",
        )
    )
    return operations


def _step(sql: str, *, reverse: str) -> Step:
    return ((sql,), (reverse,))
