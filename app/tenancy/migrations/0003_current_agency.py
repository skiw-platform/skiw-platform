# guard.current_agency(), the tenant-token verifier (spec §4.2 "Tenant binding" item 3, v1.21;
# TEN-06, TEN-12; plan M4c-4a), and skiw_app's USAGE on `guard`, its first object there.
# Created as its NOLOGIN owner through `as_owner`; the encoding matches tenancy.token. Any failed
# step returns NULL: no RAISE, no logging, no dynamic SQL. The xid is compared as text, so an
# out-of-range number in the token cannot fail a cast. The last MAC character is limited to the
# canonical ones, so each MAC has exactly one spelling. The plan named tenancy/0002; 0002 had
# merged (PR 82), so the function lands in a new migration (docs/DECISIONS.md "M4c-4a").
# Each statement is one line (the linter reads sqlmigrate output line by line) with no `%`.
from django.db import migrations

from tenancy.ddl import as_owner

FUNCTION = "guard.current_agency()"
UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
MAC = "[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]"
TOKEN = rf"^v([1-9][0-9]{{0,5}})\.({UUID})\.(0|[1-9][0-9]{{0,19}})\.({MAC})$"


def field(value: str) -> str:
    """One MAC input field: its length as 4 big-endian bytes, then the bytes."""
    return f"pg_catalog.int4send(pg_catalog.octet_length({value})) || {value}"


MAC_INPUT = " || ".join(
    field(value)
    for value in (
        "pg_catalog.convert_to('skiw-tenant-v1', 'UTF8')",
        "pg_catalog.convert_to(pg_catalog.current_database()::text, 'UTF8')",
        "pg_catalog.uuid_send(agency)",
        "pg_catalog.xid8send(xact)",
    )
)
BODY = " ".join(
    [
        "DECLARE parts text[]; agency uuid; xact pg_catalog.xid8; secret bytea; given bytea;",
        "expected bytea; nonce bytea;",
        "BEGIN",
        f"parts := pg_catalog.regexp_match(pg_catalog.current_setting('app.tenant_token', true),"
        f" '{TOKEN}');",
        "IF parts IS NULL THEN RETURN NULL; END IF;",
        "xact := pg_catalog.pg_current_xact_id_if_assigned();",
        "IF xact IS NULL OR parts[3] <> xact::text THEN RETURN NULL; END IF;",
        "SELECT k.key INTO secret FROM guard.tenant_mac_key k",
        "WHERE k.version = parts[1]::integer AND k.retired_at IS NULL;",
        "IF secret IS NULL THEN RETURN NULL; END IF;",
        "agency := parts[2]::uuid;",
        "given := pg_catalog.decode(pg_catalog.translate(parts[4], '-_', '+/') || '=', 'base64');",
        f"expected := guard.hmac({MAC_INPUT}, secret, 'sha256');",
        "nonce := guard.gen_random_bytes(32);",
        "IF guard.hmac(given, nonce, 'sha256') <> guard.hmac(expected, nonce, 'sha256')",
        "THEN RETURN NULL; END IF;",
        "RETURN agency;",
        "END",
    ]
)
CREATE = (
    f"CREATE FUNCTION {FUNCTION} RETURNS uuid LANGUAGE plpgsql STABLE SECURITY DEFINER"
    f" SET search_path = pg_catalog, pg_temp AS $fn${BODY}$fn$"
)


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0002_guard_key_tables_unlinted")]

    operations = [
        as_owner(
            "skiw_tenant_guard",
            [
                CREATE,
                f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC",
                f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO skiw_app",
            ],
            [f"DROP FUNCTION {FUNCTION}"],
        ),
        migrations.RunSQL(
            sql=["GRANT USAGE ON SCHEMA guard TO skiw_app"],
            reverse_sql=["REVOKE USAGE ON SCHEMA guard FROM skiw_app"],
        ),
    ]
