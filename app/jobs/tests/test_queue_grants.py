"""Grant audit, spec §4.1 "Procrastinate queue grants" (i), read from pg_catalog. Re-run in every
migration PR and every Procrastinate upgrade PR."""

from collections import defaultdict

import psycopg
import pytest

from .conftest import separate

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

APP_ROLE = "skiw_app"
TABLES = {
    "procrastinate_jobs": {"SELECT", "INSERT", "UPDATE"},
    "procrastinate_events": {"INSERT"},
    "procrastinate_periodic_defers": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "procrastinate_workers": {"SELECT", "INSERT", "UPDATE", "DELETE"},
}
SEQUENCES = {
    "procrastinate_jobs_id_seq": {"USAGE"},
    "procrastinate_events_id_seq": {"USAGE"},
    "procrastinate_periodic_defers_id_seq": {"USAGE"},
    "procrastinate_workers_id_seq": {"USAGE"},  # identity sequence of procrastinate_workers.id
}
GRANTED_FUNCTIONS = {
    "procrastinate_defer_jobs_v1",
    "procrastinate_defer_periodic_job_v2",
    "procrastinate_fetch_job_v2",
    "procrastinate_finish_job_v1",
    "procrastinate_retry_job_v2",
    "procrastinate_register_worker_v1",
    "procrastinate_unregister_worker_v1",
    "procrastinate_update_heartbeat_v1",
    "procrastinate_prune_stalled_workers_v1",
}
NOT_GRANTED_FUNCTIONS = {
    "procrastinate_cancel_job_v1",
    "procrastinate_retry_job_v1",
    # Trigger functions: EXECUTE is checked when a trigger is created, not when it fires.
    "procrastinate_notify_queue_job_inserted_v1",
    "procrastinate_notify_queue_abort_job_v1",
    "procrastinate_trigger_function_status_events_insert_v1",
    "procrastinate_trigger_function_status_events_update_v1",
    "procrastinate_trigger_function_scheduled_events_v1",
    "procrastinate_trigger_abort_requested_events_procedure_v1",
    "procrastinate_unlink_periodic_defers_v1",
}
# Spec §4.1 types need no grant; the composite one is the only type with a pg_class row.
COMPOSITE_TYPES = {"procrastinate_job_to_defer_v1"}
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
# django_session: D6 "Revocation is a row delete" (accounts.0001; flush and cycle_key delete).
DELETE_ALLOW_LIST = {"procrastinate_periodic_defers", "procrastinate_workers", "django_session"}
# accounts.0002 (plan M3c): the global pre-tenant tables of spec §4.1; no DELETE, no TRUNCATE.
AUTH_TABLES = {
    "auth_throttle": {"SELECT", "INSERT", "UPDATE"},
    "security_event": {"SELECT", "INSERT"},  # append-only (TEN-03)
}
# Every non-owner ACL entry on the auth tables, a closed list (grantee "-" would be PUBLIC).
# accounts.0003 (plan M4c-2b): skiw_auth_lookup, owner of the guard.auth_lookup_* definer
# functions (M3e, M3g), may only INSERT events.
LOOKUP_ROLE = "skiw_auth_lookup"
AUTH_TABLE_GRANTS = {
    **{(table, APP_ROLE): privileges for table, privileges in AUTH_TABLES.items()},
    ("security_event", LOOKUP_ROLE): {"INSERT"},
}
# Every relation the migrations create is in spec §4.1's closed global list until M4 adds
# tenant-owned tables (and the schema check); the probe tables are made by test fixtures only.
# tenancy.0002 (plan M4c-2a): the guard key tables, owned by the NOLOGIN roles. M4c-6a replaces
# this set with the schema-qualified spec list.
GUARD_KEY_TABLES = {"tenant_mac_key", "lookup_decoy_key"}
GLOBAL_TABLES = {*TABLES, *AUTH_TABLES, *GUARD_KEY_TABLES, "django_session", "django_migrations"}
# tenancy.0004 (plan M4c-5): the tenant root, the one named non-global table until M4c-6b's schema
# check classifies every table.
ROOT_TABLES = {"agency"}
TEST_ONLY_TABLES = {"jobs_probe", "files_probe"}
# Spec §4.2 TEN-03 row: append-only evidence tables, each checked as it lands.
TEN03_EVIDENCE_TABLES = [
    "audit_event",
    "security_event",
    "pipeline_stage_event",
    "ai_usage_ledger",
    "setting_change",
    "auth_stepup",
    "outbox_approval",
    "outbox_send",
]
USER_RELATIONS = """
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT starts_with(n.nspname, 'pg_') AND n.nspname <> 'information_schema'
"""


def test_queue_objects_are_exactly_the_audited_ones() -> None:
    relations = separate(
        "SELECT c.relname, c.relkind::text" + USER_RELATIONS + " AND c.relkind <> 'i'"
        " AND starts_with(c.relname, 'procrastinate_')"
    )
    assert sorted(relations) == sorted(
        [(name, "r") for name in TABLES]
        + [(name, "S") for name in SEQUENCES]
        + [(name, "c") for name in COMPOSITE_TYPES]
    )
    functions = separate(
        "SELECT p.proname FROM pg_proc p WHERE starts_with(p.proname, 'procrastinate_')"
    )
    assert sorted(name for (name,) in functions) == sorted(
        GRANTED_FUNCTIONS | NOT_GRANTED_FUNCTIONS
    )


def test_every_table_is_in_the_closed_global_list_or_the_root() -> None:
    rows = separate("SELECT c.relname" + USER_RELATIONS + " AND c.relkind IN ('r', 'p')")
    assert {name for (name,) in rows} - TEST_ONLY_TABLES == GLOBAL_TABLES | ROOT_TABLES


def test_acl_entries_on_the_auth_tables_are_exactly_the_plan_list() -> None:
    # Every grantee but the owner (M3c-1 filtered on skiw_app, so another grantee went unseen).
    owners = separate(
        "SELECT DISTINCT c.relowner::regrole::text FROM pg_class c WHERE c.relname = ANY(%s)",
        list(AUTH_TABLES),
    )
    assert owners == [("skiw_migrator",)]
    rows = separate(
        "SELECT c.relname, a.grantee::regrole::text, a.privilege_type"
        " FROM pg_class c, aclexplode(c.relacl) a"
        " WHERE c.relname = ANY(%s) AND a.grantee <> c.relowner",
        list(AUTH_TABLES),
    )
    granted: dict[tuple[str, str], set[str]] = defaultdict(set)
    for relname, grantee, privilege in rows:
        granted[relname, grantee].add(privilege)
    assert granted == AUTH_TABLE_GRANTS


def test_app_role_acl_entries_on_queue_relations_are_exactly_the_spec_list() -> None:
    rows = separate(
        "SELECT c.relname, a.privilege_type FROM pg_class c, aclexplode(c.relacl) a"
        " WHERE starts_with(c.relname, 'procrastinate_') AND a.grantee = %s::regrole",
        APP_ROLE,
    )
    granted: dict[str, set[str]] = defaultdict(set)
    for relname, privilege in rows:
        granted[relname].add(privilege)
    assert granted == TABLES | SEQUENCES


@pytest.mark.parametrize("table", [*TABLES, *AUTH_TABLES])
def test_app_role_effective_table_privileges(table: str) -> None:
    held = {
        privilege
        for privilege in TABLE_PRIVILEGES
        if separate("SELECT has_table_privilege(%s, %s, %s)", APP_ROLE, table, privilege)[0][0]
    }
    assert held == (TABLES | AUTH_TABLES)[table]


@pytest.mark.parametrize("table", AUTH_TABLES)
def test_lookup_role_effective_table_privileges(table: str) -> None:
    held = {
        privilege
        for privilege in TABLE_PRIVILEGES
        if separate("SELECT has_table_privilege(%s, %s, %s)", LOOKUP_ROLE, table, privilege)[0][0]
    }
    assert held == AUTH_TABLE_GRANTS.get((table, LOOKUP_ROLE), set())


@pytest.mark.parametrize("sequence", SEQUENCES)
def test_app_role_effective_sequence_privileges(sequence: str) -> None:
    held = {
        privilege
        for privilege in ("USAGE", "SELECT", "UPDATE")
        if separate("SELECT has_sequence_privilege(%s, %s, %s)", APP_ROLE, sequence, privilege)[0][
            0
        ]
    }
    assert held == SEQUENCES[sequence]


def test_app_role_executes_only_the_listed_functions() -> None:
    rows = separate(
        "SELECT p.proname FROM pg_proc p WHERE starts_with(p.proname, 'procrastinate_')"
        " AND has_function_privilege(%s, p.oid, 'EXECUTE')",
        APP_ROLE,
    )
    assert {name for (name,) in rows} == GRANTED_FUNCTIONS


def test_no_queue_function_is_security_definer_or_public() -> None:
    rows = separate(
        "SELECT p.proname FROM pg_proc p WHERE starts_with(p.proname, 'procrastinate_') AND ("
        " p.prosecdef OR EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl,"
        " acldefault('f', p.proowner))) a WHERE a.grantee = 0))"
    )
    assert rows == []


def test_only_owners_hold_truncate_anywhere() -> None:
    rows = separate(
        "SELECT c.relname, a.grantee::regrole::text"
        " FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace,"
        " aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a"
        " WHERE NOT starts_with(n.nspname, 'pg_') AND n.nspname <> 'information_schema'"
        " AND c.relkind IN ('r', 'p') AND a.privilege_type = 'TRUNCATE'"
        " AND a.grantee <> c.relowner"
    )
    assert rows == []


def test_app_role_deletes_only_from_the_allow_list() -> None:
    rows = separate(
        "SELECT c.relname" + USER_RELATIONS + " AND c.relkind IN ('r', 'p')"
        " AND has_table_privilege(%s, c.oid, 'DELETE')",
        APP_ROLE,
    )
    assert {name for (name,) in rows} == DELETE_ALLOW_LIST


@pytest.mark.parametrize("role", [APP_ROLE, LOOKUP_ROLE])
def test_evidence_tables_that_exist_are_append_only_for_the_writers(role: str) -> None:
    assert separate("SELECT to_regclass('security_event') IS NOT NULL") == [(True,)]
    rows = separate(
        "SELECT t FROM unnest(%s::text[]) t WHERE to_regclass(t) IS NOT NULL AND ("
        " has_table_privilege(%s, t, 'UPDATE') OR has_table_privilege(%s, t, 'DELETE')"
        " OR has_table_privilege(%s, t, 'TRUNCATE'))",
        TEN03_EVIDENCE_TABLES,
        role,
        role,
        role,
    )
    assert rows == []


def test_app_role_cannot_create_in_the_queue_schema() -> None:
    rows = separate(
        "SELECT has_schema_privilege(%s, c.relnamespace, 'CREATE') FROM pg_class c"
        " WHERE c.oid = 'procrastinate_jobs'::regclass",
        APP_ROLE,
    )
    assert rows == [(False,)]


def test_no_column_level_grants() -> None:
    rows = separate(
        "SELECT c.relname, a.attname FROM pg_attribute a"
        " JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE NOT starts_with(n.nspname, 'pg_') AND n.nspname <> 'information_schema'"
        " AND a.attacl IS NOT NULL"
    )
    assert rows == []


@pytest.mark.parametrize(
    "sql", ["DELETE FROM procrastinate_jobs", *(f"TRUNCATE {table}" for table in TABLES)]
)
def test_app_role_cannot_delete_jobs_or_truncate_queue_tables(sql: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as raised:
        separate(sql)
    assert raised.value.sqlstate == "42501"
