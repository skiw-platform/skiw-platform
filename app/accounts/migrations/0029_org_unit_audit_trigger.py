# The audit trigger of org_unit (slice spec Decisions 30, 31, 32; §4 org_unit row; plan row M4r-1e,
# split M4r-1e-ii), in the shape of accounts.0028: runs as skiw_migrator, which owns the table and
# the function; AFTER INSERT OR UPDATE FOR EACH ROW (any column, not UPDATE OF, so a change of an
# immutable column also reaches it), so the change and its events commit or roll back together.
# On every row it fires for, the function first runs 0028's OPERATOR_CHECK, unchanged and inline.
# INSERT -> org.added. UPDATE: refused (42501, 0026's fixed refusal message, naming no data) if id,
# agency_id, kind or created_at changed; then one event per changed updatable field: parent_id IS
# DISTINCT FROM -> org.moved (old parent from OLD), name IS DISTINCT FROM -> org.renamed, both ->
# both, neither -> none. Each event is INSERT INTO public.security_event as in 0028, with the
# Decision 30 keys (0025's KEYS) from OLD/NEW and the operator. SECURITY INVOKER, search_path
# pinned, every object schema-qualified, EXECUTE revoked from PUBLIC; no write grant. The reverse
# first refuses while skiw_app holds any write privilege on the four roles tables (0026's guard).
# Each statement is one line with no `%`.

import importlib

from django.db import migrations

LOCKS = importlib.import_module("accounts.migrations.0026_roles_lock_refusals")
AUDIT = importlib.import_module("accounts.migrations.0028_role_audit_triggers")
FUNCTION = "public.org_unit_audit()"
IMMUTABLE = ("id", "agency_id", "kind", "created_at")
# kind: the Decision 30 keys after operator, each key=value from OLD/NEW
EVENTS = {
    "org.added": ("org_unit_id=NEW.id", "parent_id=NEW.parent_id", "unit_kind=NEW.kind"),
    "org.moved": (
        "org_unit_id=NEW.id",
        "old_parent_id=OLD.parent_id",
        "new_parent_id=NEW.parent_id",
    ),
    "org.renamed": ("org_unit_id=NEW.id",),
}


def row(prefix: str) -> str:
    return "(" + ", ".join(f"{prefix}.{column}" for column in IMMUTABLE) + ")"


def event(kind: str) -> str:
    values = ", ".join(
        f"'{key}', {value}" for key, _, value in (k.partition("=") for k in EVENTS[kind])
    )
    return " ".join(
        [
            "INSERT INTO public.security_event (id, at, kind, agency_id, details_json) VALUES",
            "(pg_catalog.gen_random_uuid(), pg_catalog.statement_timestamp(),",
            f"'{kind}', NEW.agency_id, pg_catalog.jsonb_build_object('operator', op, {values}));",
        ]
    )


BODY = " ".join(
    [
        "DECLARE op pg_catalog.text := pg_catalog.current_setting('skiw.operator', true);",
        "BEGIN",
        AUDIT.OPERATOR_CHECK,
        f"IF TG_OP = 'INSERT' THEN {event('org.added')} RETURN NULL; END IF;",
        f"IF {row('OLD')} IS DISTINCT FROM {row('NEW')} THEN",
        LOCKS.REFUSE_BODY.removeprefix("BEGIN ").removesuffix(" END"),  # 42501, no data named
        "END IF;",
        f"IF OLD.parent_id IS DISTINCT FROM NEW.parent_id THEN {event('org.moved')} END IF;",
        f"IF OLD.name IS DISTINCT FROM NEW.name THEN {event('org.renamed')} END IF;",
        "RETURN NULL;",
        "END",
    ]
)
TRIGGER = (
    "CREATE TRIGGER org_unit_audit AFTER INSERT OR UPDATE ON public.org_unit"
    f" FOR EACH ROW EXECUTE FUNCTION {FUNCTION}"
)
REVERSE = [
    LOCKS.GUARD,
    "DROP TRIGGER org_unit_audit ON public.org_unit",
    f"DROP FUNCTION {FUNCTION}",
]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0028_role_audit_triggers"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                f"CREATE FUNCTION {FUNCTION} {LOCKS.SHAPE} AS $fn$ {BODY} $fn$",
                f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC",
                TRIGGER,
            ],
            reverse_sql=[*REVERSE],
        ),
    ]
