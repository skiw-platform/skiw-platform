# The write grants of the four roles tables (slice spec Decisions 3, 32, 33; §4 rows of role,
# role_permission, org_unit and user_role; plan row M4r-1g, split M4r-1g-i). Runs as skiw_migrator.
#
# PRECONDITION is the first statement (Decision 32 "Deployment sequence"): a DO block that raises
# (55000, a fixed message naming no data) unless every Decision 32 trigger below exists on its
# table with tgenabled = 'O', and security_event has RLS enabled and forced and exactly its three
# Decision 33 policies, as deparsed. DECISION_32 is a frozen copy of the trigger names accounts.0025
# to 0029 create (a test pins it to them); a migration that is applied never changes.
#
# Then Decision 3, nothing more: role INSERT, UPDATE (name) as a column grant, DELETE;
# role_permission INSERT, DELETE; org_unit INSERT, UPDATE (table level: §4 gives no column list,
# and org_unit_audit refuses a change of id, agency_id, kind or created_at); user_role INSERT,
# DELETE. SELECT on the four and on permission stays as accounts.0018 and 0021 granted it; no
# TRUNCATE. Each granted command gets its permissive tenant_table() policy, without which FORCE RLS
# would refuse it. The reverse revokes the writes and drops those policies; Django runs it before
# the reverses of 0029 to 0026, whose guard refuses while any write privilege is held.
# Each statement is one line with no `%`.

from django.db import migrations

from tenancy.template import APP_ROLE, COMMANDS

DECISION_32 = {
    "role": (
        "role_roles_lock",
        "role_refuse_update",
        "role_refuse_truncate",
        "role_system_guard",
        "role_system_complete",
        "role_audit",
    ),
    "role_permission": (
        "role_permission_roles_lock",
        "role_permission_refuse_update",
        "role_permission_refuse_truncate",
        "role_permission_system_guard",
        "role_permission_audit",
    ),
    "user_role": (
        "user_role_roles_lock",
        "user_role_refuse_update",
        "user_role_refuse_truncate",
        "user_role_owner_remains",
        "user_role_audit",
    ),
    "org_unit": (
        "org_unit_roles_lock",
        "org_unit_refuse_delete",
        "org_unit_refuse_truncate",
        "org_unit_tree_guard",
        "org_unit_audit",
    ),
    "security_event": ("security_event_shape",),
}
# Decision 33's predicate as pg_get_expr deparses it (tenancy.check.EVENT_DEPARSED; a test pins it)
P = "((agency_id IS NULL) OR (agency_id = ( SELECT guard.current_agency() AS current_agency)))"
# (name, permissive, polcmd, USING, WITH CHECK; '' for none)
POLICIES = (
    ("security_event_tenant", "false", "*", P, P),
    ("security_event_sel", "true", "r", P, ""),
    ("security_event_ins", "true", "a", "", P),
)
WRITES = {
    "role": ("INSERT", "UPDATE", "DELETE"),
    "role_permission": ("INSERT", "DELETE"),
    "org_unit": ("INSERT", "UPDATE"),
    "user_role": ("INSERT", "DELETE"),
}
COLUMN_UPDATE = {"role": "name"}  # Decision 3: "UPDATE (`name` only, column grant)"

EVENT = "pg_catalog.to_regclass('public.security_event')"
EXPECTED = ", ".join(
    f"('public.{table}', '{name}')" for table, names in DECISION_32.items() for name in names
)
TRIGGER_MISSING = (
    f"EXISTS (SELECT FROM (VALUES {EXPECTED})"  # noqa: S608 (constant)
    " AS e(rel, name) WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_trigger t"
    " WHERE t.tgrelid = pg_catalog.to_regclass(e.rel) AND t.tgname = e.name"
    " AND t.tgenabled = 'O' AND NOT t.tgisinternal))"
)
RLS_OFF = (
    f"NOT EXISTS (SELECT FROM pg_catalog.pg_class c WHERE c.oid = {EVENT}"
    " AND c.relrowsecurity AND c.relforcerowsecurity)"
)
SHAPES = ", ".join(f"('{n}', {k}, '{c}', '{u}', '{w}')" for n, k, c, u, w in POLICIES)
POLICY_SHAPE = (
    "(p.polname::pg_catalog.text, p.polpermissive, p.polcmd::pg_catalog.text,"
    " COALESCE(pg_catalog.pg_get_expr(p.polqual, p.polrelid), ''),"
    " COALESCE(pg_catalog.pg_get_expr(p.polwithcheck, p.polrelid), ''))"
)
POLICIES_CHANGED = (
    f"(SELECT pg_catalog.count(*) FROM pg_catalog.pg_policy p"  # noqa: S608 (constant)
    f" WHERE p.polrelid = {EVENT}) <> 3 OR (SELECT pg_catalog.count(*)"
    f" FROM pg_catalog.pg_policy p WHERE p.polrelid = {EVENT}"
    f" AND p.polroles = ARRAY['{APP_ROLE}'::pg_catalog.regrole::pg_catalog.oid]"
    f" AND {POLICY_SHAPE} IN (VALUES {SHAPES})) <> 3"
)
PRECONDITION = (
    f"DO $pre$ BEGIN IF {TRIGGER_MISSING} OR {RLS_OFF} OR {POLICIES_CHANGED} THEN"
    " RAISE EXCEPTION 'grant refused: a roles trigger or the security_event isolation is missing"
    " or not enabled' USING ERRCODE = 'object_not_in_prerequisite_state'; END IF; END $pre$"
)


def privileges(table: str) -> str:
    column = COLUMN_UPDATE.get(table)
    return ", ".join(f"{c} ({column})" if c == "UPDATE" and column else c for c in WRITES[table])


def policy(table: str, command: str) -> tuple[str, str]:
    suffix, clauses = COMMANDS[command]
    return (
        f"CREATE POLICY {table}_{suffix} ON public.{table} FOR {command} TO {APP_ROLE} {clauses}",
        f"DROP POLICY {table}_{suffix} ON public.{table}",
    )


POLICY_SQL = [policy(table, command) for table, commands in WRITES.items() for command in commands]
FORWARD = [
    PRECONDITION,
    *(create for create, _ in POLICY_SQL),
    *(f"GRANT {privileges(t)} ON public.{t} TO {APP_ROLE}" for t in WRITES),
]
REVERSE = [
    *(f"REVOKE {privileges(t)} ON public.{t} FROM {APP_ROLE}" for t in reversed(WRITES)),
    *(drop for _, drop in reversed(POLICY_SQL)),
]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0029_org_unit_audit_trigger"),
    ]

    operations = [
        migrations.RunSQL(sql=[*FORWARD], reverse_sql=[*REVERSE]),
    ]
