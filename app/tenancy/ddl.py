"""Ownership helper for `guard` objects (owner Q1 (a); plan M4c-2a).

`skiw_migrator` is a member of the two NOLOGIN owner roles with INHERIT FALSE, SET TRUE
(`infra/host/db/roles.sql`), so it acts as an owner only through an explicit `SET ROLE`. A `guard`
object is created, replaced and dropped as its owner, never created as the migrator and handed
over, so nothing relies on inherited ownership. Use it only in atomic migrations (the default):
`SET LOCAL ROLE` has no effect outside a transaction block, so the statement after it raises unless
`current_user` is the owner (plan M4c-2b, PR 84 review P3). In a non-atomic run the GRANT before it
has already committed; a re-run in an atomic migration revokes it (docs/DECISIONS.md "M4c-2b").
"""

from collections.abc import Sequence

from django.db import migrations

# The closed list of guard object owners (spec D4, §4.1). Nothing else may own a guard object.
GUARD_OWNERS = frozenset({"skiw_tenant_guard", "skiw_auth_lookup"})


def as_owner(role: str, statements: Sequence[str], reverse: Sequence[str]) -> migrations.RunSQL:
    """One `RunSQL` that runs `statements` (forward) or `reverse` as `role`, one statement per
    item. The role holds CREATE on `guard` only while it runs; the migrator keeps the schema."""
    if role not in GUARD_OWNERS:
        raise ValueError(f"as_owner: {role!r} is not a guard owner role")

    def wrapped(body: Sequence[str]) -> tuple[str, ...]:
        return (
            f"GRANT CREATE ON SCHEMA guard TO {role}",
            f"SET LOCAL ROLE {role}",
            # One line (the linter reads sqlmigrate output line by line) and no `%`, so no
            # %-formatting step can change it.
            f"DO $$BEGIN IF current_user <> '{role}' THEN RAISE EXCEPTION"
            f" 'as_owner: current_user is not {role}; use an atomic migration'; END IF; END$$",
            *body,
            "RESET ROLE",
            f"REVOKE CREATE ON SCHEMA guard FROM {role}",
        )

    return migrations.RunSQL(sql=wrapped(statements), reverse_sql=wrapped(reverse))
