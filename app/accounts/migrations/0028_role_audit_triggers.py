# The audit triggers of role, role_permission and user_role (slice spec Decisions 30, 31, 32; §4
# rows of the three tables; plan row M4r-1e, split M4r-1e-i). Runs as skiw_migrator, which owns the
# tables and the functions. AFTER row triggers fire for every writer, the owner included, at the end
# of the change's own statement, so the change and its event commit or roll back together (also
# when a deferred check refuses at commit). Each function first checks the operator: OPERATOR_CHECK
# raises (22023, a fixed message naming no data) unless current_setting('skiw.operator', true)
# matches the Decision 31 shape, so NULL (never set) and '' (an earlier transaction-local value has
# ended in this session) are refused, on every row it fires for, also a name-unchanged UPDATE. Then
# one event per row: role INSERT -> role.created, UPDATE with a changed name -> role.renamed (else
# none), DELETE -> role.deleted; role_permission INSERT/DELETE -> permission.set/unset; user_role
# INSERT/DELETE -> role.assigned/unassigned (from NEW, from OLD). The event is INSERT INTO
# public.security_event with gen_random_uuid(), statement_timestamp(), the kind, the row's
# agency_id and the Decision 30 keys from the row and the operator (security_event_shape checks
# them, at trigger depth 2). The check is repeated inline in each function, not a helper: these are
# SECURITY INVOKER, so a nested helper would need EXECUTE for skiw_app (DECISIONS M4r-1d-ii,
# choice 1); M4r-1e-ii's org_unit_audit reuses OPERATOR_CHECK. SECURITY INVOKER (security_event's
# RLS applies to the writer), search_path pinned, every object schema-qualified, EXECUTE revoked
# from PUBLIC; no write grant. The reverse first refuses while skiw_app holds any write privilege on
# the four roles tables (0026's guard). Each statement is one line with no `%`.

import importlib

from django.db import migrations

LOCKS = importlib.import_module("accounts.migrations.0026_roles_lock_refusals")
OPERATOR_CHECK = " ".join(
    [
        "IF NOT COALESCE(op OPERATOR(pg_catalog.~) '^[a-z][a-z0-9-]{1,31}$', false) THEN",
        "RAISE EXCEPTION 'roles change refused: skiw.operator is missing or malformed'",
        "USING ERRCODE = 'invalid_parameter_value'; END IF;",
    ]
)
# table: (kinds for INSERT, UPDATE, DELETE (None: no such trigger event), the Decision 30 keys
# after operator, the row field whose change an UPDATE records)
AUDITS = {
    "role": (("role.created", "role.renamed", "role.deleted"), ("role_id=id",), "name"),
    "role_permission": (
        ("permission.set", None, "permission.unset"),
        ("role_permission_id=id", "role_id", "permission_code", "scope"),
        None,
    ),
    "user_role": (
        ("role.assigned", None, "role.unassigned"),
        ("user_role_id=id", "user_id", "role_id", "org_unit_id", "line"),
        None,
    ),
}


def body(table: str) -> str:
    (on_insert, on_update, on_delete), keys, field = AUDITS[table]
    pairs = (key.partition("=") for key in keys)
    values = ", ".join(f"'{key}', r.{column or key}" for key, _, column in pairs)
    unchanged = f"OLD.{field} IS NOT DISTINCT FROM NEW.{field}"
    return " ".join(
        [
            "DECLARE op pg_catalog.text := pg_catalog.current_setting('skiw.operator', true);",
            f"r public.{table};",
            "BEGIN",
            OPERATOR_CHECK,
            *([f"IF TG_OP = 'UPDATE' AND {unchanged} THEN RETURN NULL; END IF;"] if field else []),
            "IF TG_OP = 'DELETE' THEN r := OLD; ELSE r := NEW; END IF;",
            "INSERT INTO public.security_event (id, at, kind, agency_id, details_json) VALUES",
            "(pg_catalog.gen_random_uuid(), pg_catalog.statement_timestamp(),",
            f"CASE TG_OP WHEN 'INSERT' THEN '{on_insert}'",
            *([f"WHEN 'UPDATE' THEN '{on_update}'"] if on_update else []),
            f"ELSE '{on_delete}' END, r.agency_id,",
            f"pg_catalog.jsonb_build_object('operator', op, {values}));",
            "RETURN NULL;",
            "END",
        ]
    )


def events(table: str) -> str:
    kinds = AUDITS[table][0]
    return " OR ".join(
        op for op, kind in zip(("INSERT", "UPDATE", "DELETE"), kinds, strict=True) if kind
    )


FUNCTIONS = {table: f"public.{table}_audit()" for table in AUDITS}
TRIGGERS = [
    (
        f"{table}_audit",
        table,
        f"CREATE TRIGGER {table}_audit AFTER {events(table)} ON public.{table}"
        f" FOR EACH ROW EXECUTE FUNCTION {FUNCTIONS[table]}",
    )
    for table in AUDITS
]
REVERSE = [
    LOCKS.GUARD,
    *(f"DROP TRIGGER {name} ON public.{table}" for name, table, _ in reversed(TRIGGERS)),
    *(f"DROP FUNCTION {FUNCTIONS[table]}" for table in reversed(AUDITS)),
]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0027_tree_system_role_guards"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                *(
                    f"CREATE FUNCTION {f} {LOCKS.SHAPE} AS $fn$ {body(t)} $fn$"
                    for t, f in FUNCTIONS.items()
                ),
                *(f"REVOKE EXECUTE ON FUNCTION {f} FROM PUBLIC" for f in FUNCTIONS.values()),
                *(statement for _, _, statement in TRIGGERS),
            ],
            reverse_sql=[*REVERSE],
        ),
    ]
