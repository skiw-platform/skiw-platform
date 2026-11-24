# The org_unit tree guard, the system-role guards and the two deferred checks (slice spec Decisions
# 2, 27, 28; §4 rows of role, role_permission, org_unit and user_role; plan row M4r-1d, split
# M4r-1d-ii). Runs as skiw_migrator, which owns the four tables and every function here. The roles
# lock and its READ COMMITTED refusal, and the refusal triggers, are accounts.0026.
#
# org_unit_tree_guard: BEFORE INSERT OR UPDATE OF parent_id, every row. Its name sorts after
# org_unit_roles_lock, and BEFORE row triggers of one event fire in name order, so it runs with the
# roles lock held and at READ COMMITTED; each query in it takes a fresh snapshot (a VOLATILE
# function). A root (parent_id NULL) is left to the CHECKs and the one-root index. Otherwise it
# walks the ancestors of NEW.parent_id and the descendants of NEW.id, each with CYCLE and at most
# ORG_MAX_DEPTH levels, and refuses (23514) a cycle (NEW.id among the ancestors, or a flagged
# repeat) or a path from the root longer than ORG_MAX_DEPTH units (the root is level 1).
#
# role_system_guard: BEFORE DELETE on role WHEN OLD.is_system, and BEFORE DELETE on role_permission
# of a row of the agency's system role (42501). Its triggers sort after the lock triggers too. A
# change of is_system, a second system role and an UPDATE of a tick are already refused (0026, the
# role_one_system_per_agency index).
#
# role_system_complete (AFTER INSERT on role WHEN NEW.is_system) and user_role_owner_remains (AFTER
# UPDATE OR DELETE on user_role): constraint triggers, DEFERRABLE INITIALLY DEFERRED, so they run at
# commit. Each first takes the roles lock of the row's agency (Decision 28: "already held"):
# re-entrant, so a no-op behind the row's own lock trigger, whose lock a savepoint rollback can
# release only together with the row change and this queued check. No isolation check: the row's
# lock trigger already refused a writer not at READ COMMITTED, and the level cannot change after
# the first query. role_system_complete refuses (23514) unless the role holds every permission
# row. user_role_owner_remains refuses (23514) when the removed row was of the system role and no
# assignment to it is left, and also when the row's unit cannot be seen (units are never deleted,
# so the writer's RLS context changed before commit): it fails closed rather than miss the system
# role.
#
# SECURITY INVOKER, search_path pinned, every object schema-qualified, EXECUTE revoked from PUBLIC;
# no body names security_event. The reverse first refuses while skiw_app holds any write privilege
# on the four tables (0026's guard). Each statement is one line with no `%`.

import importlib

from django.db import migrations

LOCKS = importlib.import_module("accounts.migrations.0026_roles_lock_refusals")
ORG_MAX_DEPTH = 32  # slice spec §8: a technical bound, the same cap as scoped()'s subtree CTE
TREE_GUARD = "public.org_unit_tree_guard()"
SYSTEM_GUARD = "public.role_system_guard()"
COMPLETE = "public.role_system_complete()"
OWNER_REMAINS = "public.user_role_owner_remains()"
FUNCTIONS = (TREE_GUARD, SYSTEM_GUARD, COMPLETE, OWNER_REMAINS)


def refuse(message: str, code: str) -> str:
    return f"RAISE EXCEPTION 'roles change refused: {message}' USING ERRCODE = '{code}';"


def walk(name: str, seed: str, step: str) -> str:
    """A bounded recursive walk over the agency's units, from `seed` along `step`."""
    return " ".join(
        [
            f"WITH RECURSIVE {name}(id, parent_id, n) AS ({seed} UNION ALL",
            "SELECT u.id, u.parent_id,",
            f"{name}.n OPERATOR(pg_catalog.+) 1",
            f"FROM {name} JOIN public.org_unit u ON u.agency_id = NEW.agency_id AND {step}",
            f"WHERE {name}.n OPERATOR(pg_catalog.<) {ORG_MAX_DEPTH})",
            "CYCLE id SET is_cycle USING path",
        ]
    )


UP = walk(
    "up",
    "SELECT u.id, u.parent_id, 1 FROM public.org_unit u"
    " WHERE u.agency_id = NEW.agency_id AND u.id = NEW.parent_id",
    "u.id = up.parent_id",
)
DOWN = walk("down", "SELECT NEW.id, NEW.parent_id, 1", "u.parent_id = down.id")
TREE_BODY = " ".join(
    [
        "DECLARE above pg_catalog.int4; below pg_catalog.int4; looped pg_catalog.bool;",
        "BEGIN",
        "IF NEW.parent_id IS NULL THEN RETURN NEW; END IF;",
        UP,
        "SELECT pg_catalog.max(n), pg_catalog.bool_or(is_cycle OR id = NEW.id)",
        "INTO above, looped FROM up;",
        f"IF looped THEN {refuse('the org unit tree would have a cycle', 'check_violation')}",
        "END IF;",
        DOWN,
        "SELECT pg_catalog.max(n), pg_catalog.bool_or(is_cycle) INTO below, looped FROM down;",
        f"IF looped THEN {refuse('the org unit tree would have a cycle', 'check_violation')}",
        "END IF;",
        f"IF above OPERATOR(pg_catalog.+) below OPERATOR(pg_catalog.>) {ORG_MAX_DEPTH} THEN",
        refuse(f"the org unit tree would be deeper than {ORG_MAX_DEPTH} levels", "check_violation"),
        "END IF;",
        "RETURN NEW;",
        "END",
    ]
)
SYSTEM_ROLE = (
    "SELECT FROM public.role r WHERE r.agency_id = OLD.agency_id AND r.id = OLD.role_id"
    " AND r.is_system"
)
SYSTEM_BODY = " ".join(
    [
        "BEGIN",
        # Nested: PL/pgSQL parses an expression when it first runs, and role has no role_id.
        "IF TG_TABLE_NAME = 'role_permission' THEN",
        f"IF NOT EXISTS ({SYSTEM_ROLE}) THEN RETURN OLD; END IF;",
        "END IF;",
        refuse("the system role is protected", "insufficient_privilege"),
        "END",
    ]
)
EVERY_PAIR = (
    "SELECT FROM public.permission p WHERE NOT EXISTS (SELECT FROM public.role_permission rp"
    " WHERE rp.agency_id = NEW.agency_id AND rp.role_id = NEW.id"
    " AND rp.permission_code = p.code AND rp.scope = p.scope)"
)
COMPLETE_BODY = " ".join(
    [
        "BEGIN",
        f"{LOCKS.TAKE}(NEW.agency_id::pg_catalog.text));",
        f"IF EXISTS ({EVERY_PAIR}) THEN",
        refuse("the system role must hold every permission", "check_violation"),
        "END IF;",
        "RETURN NULL;",
        "END",
    ]
)
UNIT_SEEN = (
    "SELECT FROM public.org_unit o WHERE o.agency_id = OLD.agency_id AND o.id = OLD.org_unit_id"
)
HOLDER = (
    "SELECT FROM public.user_role h WHERE h.agency_id = OLD.agency_id AND h.role_id = OLD.role_id"
)
REMAINS_BODY = " ".join(
    [
        "BEGIN",
        f"{LOCKS.TAKE}(OLD.agency_id::pg_catalog.text));",
        f"IF NOT EXISTS ({UNIT_SEEN}) OR (EXISTS ({SYSTEM_ROLE}) AND NOT EXISTS ({HOLDER})) THEN",
        refuse("the system role must keep a holder", "check_violation"),
        "END IF;",
        "RETURN NULL;",
        "END",
    ]
)
BODIES = {
    TREE_GUARD: TREE_BODY,
    SYSTEM_GUARD: SYSTEM_BODY,
    COMPLETE: COMPLETE_BODY,
    OWNER_REMAINS: REMAINS_BODY,
}
DEFERRED = "DEFERRABLE INITIALLY DEFERRED"
# (name, table, statement)
TRIGGERS = [
    (
        "org_unit_tree_guard",
        "org_unit",
        "CREATE TRIGGER org_unit_tree_guard BEFORE INSERT OR UPDATE OF parent_id ON public.org_unit"
        f" FOR EACH ROW EXECUTE FUNCTION {TREE_GUARD}",
    ),
    (
        "role_system_guard",
        "role",
        "CREATE TRIGGER role_system_guard BEFORE DELETE ON public.role FOR EACH ROW"
        f" WHEN (OLD.is_system) EXECUTE FUNCTION {SYSTEM_GUARD}",
    ),
    (
        "role_permission_system_guard",
        "role_permission",
        "CREATE TRIGGER role_permission_system_guard BEFORE DELETE ON public.role_permission"
        f" FOR EACH ROW EXECUTE FUNCTION {SYSTEM_GUARD}",
    ),
    (
        "role_system_complete",
        "role",
        f"CREATE CONSTRAINT TRIGGER role_system_complete AFTER INSERT ON public.role {DEFERRED}"
        f" FOR EACH ROW WHEN (NEW.is_system) EXECUTE FUNCTION {COMPLETE}",
    ),
    (
        "user_role_owner_remains",
        "user_role",
        "CREATE CONSTRAINT TRIGGER user_role_owner_remains AFTER UPDATE OR DELETE"
        f" ON public.user_role {DEFERRED} FOR EACH ROW EXECUTE FUNCTION {OWNER_REMAINS}",
    ),
]
REVERSE = [
    LOCKS.GUARD,
    *(f"DROP TRIGGER {name} ON public.{table}" for name, table, _ in reversed(TRIGGERS)),
    *(f"DROP FUNCTION {function}" for function in reversed(FUNCTIONS)),
]


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0026_roles_lock_refusals"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                *(f"CREATE FUNCTION {f} {LOCKS.SHAPE} AS $fn$ {BODIES[f]} $fn$" for f in FUNCTIONS),
                *(f"REVOKE EXECUTE ON FUNCTION {f} FROM PUBLIC" for f in FUNCTIONS),
                *(statement for _, _, statement in TRIGGERS),
            ],
            reverse_sql=[*REVERSE],
        ),
    ]
