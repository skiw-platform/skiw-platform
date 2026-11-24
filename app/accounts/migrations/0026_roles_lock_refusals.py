# The roles lock and the refusal triggers (slice spec Decisions 27, 28, 32; §4 rows of role,
# role_permission, org_unit and user_role; plan row M4r-1d, split M4r-1d-i). Runs as skiw_migrator,
# which owns the four tables and both functions. Triggers fire for every writer, the owner included.
#
# roles_lock: a BEFORE INSERT OR UPDATE OR DELETE row trigger on each of the four tables takes the
# per-agency transaction-scoped advisory lock pg_advisory_xact_lock(ROLES_LOCK_CLASS,
# hashtext(agency_id::text)) of the row (on UPDATE, of OLD and NEW; re-entrant, so the same agency
# twice is one lock), so every write of one agency serialises. Right after the lock it refuses
# unless transaction_isolation is 'read committed' (Decision 27): a REPEATABLE READ or SERIALIZABLE
# writer fails at its first write, 25000, before any check runs on a fixed snapshot.
#
# roles_refuse (Decision 32 "Refusal triggers"): BEFORE UPDATE on role_permission and user_role and
# BEFORE DELETE on org_unit, every row; BEFORE UPDATE on role when any column but name changes (the
# WHEN compares the rows without name, so a later column is covered too); BEFORE TRUNCATE FOR EACH
# STATEMENT on all four. 42501, a fixed message naming no data. skiw_app holds no such grant
# (accounts.0018, 0021); these are the defence if one is ever added.
#
# Not here (M4r-1d-ii): the org_unit tree guard, the system-role guards, role_system_complete and
# user_role_owner_remains. SECURITY INVOKER, search_path pinned, every function schema-qualified,
# EXECUTE revoked from PUBLIC; neither body names security_event. The reverse first refuses while
# skiw_app holds any write privilege on the four tables (Decision 32 "Deployment sequence"). Each
# statement is one line (the linter reads sqlmigrate output line by line) with no `%`.

from django.db import migrations

ROLES_LOCK_CLASS = 0x524F4C45  # "ROLE": first key of the two-key advisory lock space
TABLES = ("role", "role_permission", "user_role", "org_unit")
LOCK = "public.roles_lock()"
REFUSE = "public.roles_refuse()"
SHAPE = "RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, pg_temp"
TAKE = f"PERFORM pg_catalog.pg_advisory_xact_lock({ROLES_LOCK_CLASS}, pg_catalog.hashtext"
LOCK_BODY = " ".join(
    [
        "BEGIN",
        f"IF TG_OP <> 'INSERT' THEN {TAKE}(OLD.agency_id::pg_catalog.text)); END IF;",
        f"IF TG_OP <> 'DELETE' THEN {TAKE}(NEW.agency_id::pg_catalog.text)); END IF;",
        "IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN",
        "RAISE EXCEPTION 'roles change refused: the transaction must be read committed'",
        "USING ERRCODE = 'invalid_transaction_state'; END IF;",
        "IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;",
        "RETURN NEW;",
        "END",
    ]
)
REFUSE_BODY = (
    "BEGIN RAISE EXCEPTION 'roles change refused: this statement is not allowed on this table'"
    " USING ERRCODE = 'insufficient_privilege'; END"
)
WITHOUT_NAME = "pg_catalog.to_jsonb({row}) OPERATOR(pg_catalog.-) 'name'::pg_catalog.text"
NOT_ONLY_NAME = (
    f"({WITHOUT_NAME.format(row='OLD')}) IS DISTINCT FROM ({WITHOUT_NAME.format(row='NEW')})"
)


# (name, event, table, FOR EACH, function, WHEN condition or "")
TRIGGERS = [
    *((f"{t}_roles_lock", "INSERT OR UPDATE OR DELETE", t, "ROW", LOCK, "") for t in TABLES),
    ("role_permission_refuse_update", "UPDATE", "role_permission", "ROW", REFUSE, ""),
    ("user_role_refuse_update", "UPDATE", "user_role", "ROW", REFUSE, ""),
    ("org_unit_refuse_delete", "DELETE", "org_unit", "ROW", REFUSE, ""),
    ("role_refuse_update", "UPDATE", "role", "ROW", REFUSE, NOT_ONLY_NAME),
    *((f"{t}_refuse_truncate", "TRUNCATE", t, "STATEMENT", REFUSE, "") for t in TABLES),
]
CREATE_TRIGGERS = [
    f"CREATE TRIGGER {name} BEFORE {event} ON public.{table} FOR EACH {each}"
    + (f" WHEN ({condition})" if condition else "")
    + f" EXECUTE FUNCTION {function}"
    for name, event, table, each, function, condition in TRIGGERS
]
WRITES = " OR ".join(
    [
        "pg_catalog.has_table_privilege('skiw_app', t, 'INSERT,UPDATE,DELETE,TRUNCATE')",
        "pg_catalog.has_any_column_privilege('skiw_app', t, 'INSERT,UPDATE')",
    ]
)
ARRAY = "ARRAY[" + ", ".join(f"'public.{t}'" for t in TABLES) + "]"
GUARD = (
    f"DO $guard$ BEGIN IF EXISTS (SELECT FROM pg_catalog.unnest({ARRAY}) AS t WHERE {WRITES})"
    " THEN RAISE EXCEPTION 'reverse refused: skiw_app holds a write privilege on a roles table'"
    " USING ERRCODE = 'object_not_in_prerequisite_state'; END IF; END $guard$"
)
REVERSE = [
    GUARD,
    *(f"DROP TRIGGER {name} ON public.{table}" for name, _, table, *_ in reversed(TRIGGERS)),
    f"DROP FUNCTION {REFUSE}",
    f"DROP FUNCTION {LOCK}",
]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0025_security_event_shape"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                f"CREATE FUNCTION {LOCK} {SHAPE} AS $fn$ {LOCK_BODY} $fn$",
                f"CREATE FUNCTION {REFUSE} {SHAPE} AS $fn$ {REFUSE_BODY} $fn$",
                f"REVOKE EXECUTE ON FUNCTION {LOCK} FROM PUBLIC",
                f"REVOKE EXECUTE ON FUNCTION {REFUSE} FROM PUBLIC",
                *CREATE_TRIGGERS,
            ],
            reverse_sql=[*REVERSE],
        ),
    ]
