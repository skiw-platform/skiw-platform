"""The test-only probe trigger (slice spec Decision 32, §7 "Other code writes or forges change
events"; plan row M4r-1c): `public.security_event_probe` is an empty table whose BEFORE INSERT
trigger writes the inserted row into security_event and skips its own row, so the event INSERT
runs at trigger depth 2 as the inserting role (SECURITY INVOKER: skiw_app's RLS applies). It
stands in for the M4r-1e audit triggers. Made by skiw_migrator, INSERT granted to skiw_app; never in
a migration. app/conftest.py installs it for a live run and removes it afterwards; the schema-check
tests list it as a test-only table."""

import os
import uuid
from typing import Any

import psycopg
from psycopg import sql

TABLE = "public.security_event_probe"
FUNCTION = "public.security_event_probe_plant()"
INSERT = (
    f"INSERT INTO {TABLE} (id, kind, agency, email_hmac, ip_hmac, details)"  # noqa: S608
    " VALUES (%s, %s, %s, %s, %s, %s)"
)
BODY = (
    "BEGIN INSERT INTO public.security_event"
    " (id, at, kind, agency_id, email_hmac, ip_hmac, details_json) VALUES (NEW.id,"
    " pg_catalog.statement_timestamp(), NEW.kind, NEW.agency, NEW.email_hmac, NEW.ip_hmac,"
    " NEW.details); RETURN NULL; END"
)
INSTALL = (
    f"CREATE TABLE IF NOT EXISTS {TABLE} (id uuid NOT NULL, kind text NOT NULL, agency uuid,"
    " email_hmac bytea, ip_hmac bytea, details jsonb)",
    f"CREATE OR REPLACE FUNCTION {FUNCTION} RETURNS trigger LANGUAGE plpgsql"
    f" SET search_path = pg_catalog, pg_temp AS $fn${BODY}$fn$",
    f"CREATE OR REPLACE TRIGGER plant BEFORE INSERT ON {TABLE} FOR EACH ROW"
    f" EXECUTE FUNCTION {FUNCTION}",
    f"REVOKE ALL ON {TABLE} FROM PUBLIC",
    f"GRANT INSERT ON {TABLE} TO skiw_app",
)
REMOVE = (f"DROP TABLE IF EXISTS {TABLE}", f"DROP FUNCTION IF EXISTS {FUNCTION}")


def _run(statements: tuple[str, ...]) -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        for statement in statements:
            conn.execute(sql.SQL(statement))  # constants above


def install() -> None:
    _run(INSTALL)


def remove() -> None:
    _run(REMOVE)


def details(kind: str) -> dict[str, Any]:
    """A well-shaped Decision 30 key set for `kind` (fresh ids; the pair is in the catalogue)."""
    ids = [str(uuid.uuid4()) for _ in range(5)]
    role, unit = {"role_id": ids[0]}, {"org_unit_id": ids[1]}
    tick = {"role_permission_id": ids[2], **role, "permission_code": "client.view", "scope": "own"}
    assignment = {"user_role_id": ids[2], "user_id": ids[3], **role, **unit}
    shapes: dict[str, dict[str, Any]] = {
        "role.created": role,
        "role.renamed": role,
        "role.deleted": role,
        "permission.set": tick,
        "permission.unset": tick,
        "role.assigned": {**assignment, "line": "both"},
        "role.unassigned": {**assignment, "line": "insurance"},
        "org.added": {**unit, "parent_id": ids[4], "unit_kind": "team"},
        "org.moved": {**unit, "old_parent_id": ids[3], "new_parent_id": ids[4]},
        "org.renamed": unit,
    }
    return {"operator": "ops-1", **shapes[kind]}
