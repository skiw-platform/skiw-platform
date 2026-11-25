# security_event_shape (slice spec Decisions 30, 32; §4 security_event row; plan row M4r-1c, split
# M4r-1c-ii): a BEFORE INSERT row trigger on security_event, for every writer. Runs as
# skiw_migrator, which owns the table and the function. A pre-tenant kind passes unchanged. A
# change kind is refused unless pg_trigger_depth() >= 2, i.e. the INSERT comes from inside another
# trigger (the M4r-1e audit triggers; until then only the test-only probe trigger), and its
# details_json must hold exactly the kind's Decision 30 keys with these values: operator matches
# the skiw.operator shape; every id a canonical lowercase uuid string; parent_id JSON null exactly
# when unit_kind is 'agency' (org_unit_root_is_agency); line and unit_kind closed codes; the
# (permission_code, scope) pair present in permission. Refusals raise a fixed message naming no
# data: 42501 for the depth rule, 23514 for the shape. The trigger fires before the RLS WITH CHECK
# and the CHECKs (PostgreSQL CREATE POLICY docs). SECURITY INVOKER, so a lookup of permission runs
# as the writer (skiw_app holds SELECT, accounts.0018); search_path is pinned and every function
# and table is schema-qualified. The body does not name its table, so the pg_proc scan of
# functions that write events finds only the writers. The schema check's security_event rule pins
# the trigger (tenancy.check). Each statement is one line (the linter reads sqlmigrate output line
# by line) with no `%`, as accounts.0009.
# Reverse: refused (55000, a fixed message naming no data) while any change-kind row exists, before
# the trigger is dropped (PR 186 R1 P1). This is the first reverse that removes an isolation of
# security_event (0024's reverse runs after it), and each migration commits on its own, so a guard
# any later would leave the rows kept but readable and writable by skiw_app without the tenant
# policies or the shape and depth rule. Under FORCE the migrator, which no policy names, sees no
# row, so the reverse lifts FORCE in its own transaction first (the tenancy.seed pattern) and puts
# it back after the check: a refusal rolls back the whole reverse, FORCE included, and with no
# change row 0024's reverse starts from the same ENABLE + FORCE state as before.

from django.db import migrations

UUID = "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'"
OPERATOR = "'^[a-z][a-z0-9-]{1,31}$'"
KEYS = {
    "role.created": ("operator", "role_id"),
    "role.renamed": ("operator", "role_id"),
    "role.deleted": ("operator", "role_id"),
    "permission.set": ("operator", "role_permission_id", "role_id", "permission_code", "scope"),
    "permission.unset": ("operator", "role_permission_id", "role_id", "permission_code", "scope"),
    "role.assigned": ("operator", "user_role_id", "user_id", "role_id", "org_unit_id", "line"),
    "role.unassigned": ("operator", "user_role_id", "user_id", "role_id", "org_unit_id", "line"),
    "org.added": ("operator", "org_unit_id", "parent_id", "unit_kind"),
    "org.moved": ("operator", "org_unit_id", "old_parent_id", "new_parent_id"),
    "org.renamed": ("operator", "org_unit_id"),
}


def _array(items: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{item}'" for item in items) + "]::pg_catalog.text[]"


WANT = " ".join(f"WHEN '{kind}' THEN {_array(keys)}" for kind, keys in KEYS.items())
SHAPE = "RAISE EXCEPTION 'change event refused: details do not match the kind'"
EXACT_KEYS = (
    "IF ARRAY(SELECT x FROM pg_catalog.jsonb_object_keys(d) AS x ORDER BY x COLLATE"
    ' pg_catalog."C") IS DISTINCT FROM ARRAY(SELECT x FROM pg_catalog.unnest(want) AS x'
    ' ORDER BY x COLLATE pg_catalog."C") THEN'
)
BODY = " ".join(
    [
        "DECLARE d pg_catalog.jsonb := NEW.details_json; want pg_catalog.text[];",
        "k pg_catalog.text; t pg_catalog.text; s pg_catalog.text;",
        "BEGIN",
        f"want := CASE NEW.kind::pg_catalog.text {WANT} END;",
        "IF want IS NULL THEN RETURN NEW; END IF;",
        "IF pg_catalog.pg_trigger_depth() < 2 THEN",
        "RAISE EXCEPTION 'change event refused: written only by a trigger'",
        "USING ERRCODE = 'insufficient_privilege'; END IF;",
        "IF d IS NULL OR pg_catalog.jsonb_typeof(d) <> 'object' THEN",
        f"{SHAPE} USING ERRCODE = 'check_violation'; END IF;",
        EXACT_KEYS,
        f"{SHAPE} USING ERRCODE = 'check_violation'; END IF;",
        "FOREACH k IN ARRAY want LOOP",
        "t := pg_catalog.jsonb_typeof(d -> k); s := d ->> k;",
        "IF NOT COALESCE(CASE",
        f"WHEN k = 'operator' THEN t = 'string' AND s ~ {OPERATOR}",
        "WHEN k = 'line' THEN t = 'string' AND s = ANY (ARRAY['insurance', 'investment', 'both'])",
        "WHEN k = 'unit_kind' THEN t = 'string' AND s = ANY (ARRAY['agency', 'unit', 'team'])",
        "WHEN k = 'permission_code' OR k = 'scope' THEN t = 'string'",
        "WHEN k = 'parent_id' AND t = 'null' THEN (d ->> 'unit_kind') = 'agency'",
        f"WHEN k = 'parent_id' THEN t = 'string' AND s ~ {UUID}",
        "AND (d ->> 'unit_kind') <> 'agency'",
        f"ELSE t = 'string' AND s ~ {UUID} END, false) THEN",
        f"{SHAPE} USING ERRCODE = 'check_violation'; END IF;",
        "END LOOP;",
        "IF (d ->> 'permission_code') IS NOT NULL AND NOT EXISTS (SELECT FROM public.permission p",
        "WHERE p.code = (d ->> 'permission_code') AND p.scope = (d ->> 'scope')) THEN",
        f"{SHAPE} USING ERRCODE = 'check_violation'; END IF;",
        "RETURN NEW;",
        "END",
    ]
)
FUNCTION = "public.security_event_shape()"
CREATE = (
    f"CREATE FUNCTION {FUNCTION} RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER"
    f" SET search_path = pg_catalog, pg_temp AS $fn${BODY}$fn$"
)
KINDS = tuple(KEYS)  # the ten change kinds (accounts.0022 KINDS; a test pins them)
TABLE = "public.security_event"
REFUSE_RETAINED = [
    f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY",
    f"DO $$ BEGIN IF EXISTS (SELECT FROM {TABLE} WHERE kind IN {KINDS}) THEN"
    " RAISE EXCEPTION 'reverse refused: security_event holds role or org change events'"
    " USING ERRCODE = 'object_not_in_prerequisite_state'; END IF; END $$",
    f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY",
]
TRIGGER = (
    "CREATE TRIGGER security_event_shape BEFORE INSERT ON public.security_event"
    f" FOR EACH ROW EXECUTE FUNCTION {FUNCTION}"
)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0024_security_event_rls"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[CREATE, f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC", TRIGGER],
            reverse_sql=[
                *REFUSE_RETAINED,
                "DROP TRIGGER security_event_shape ON public.security_event",
                f"DROP FUNCTION {FUNCTION}",
            ],
        ),
    ]
