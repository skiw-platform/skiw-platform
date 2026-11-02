# Fixture for `semgrep --test semgrep/` (rules in tenancy-boundaries.yml).
# ruleid: tenancy-async-pool
from psycopg_pool import AsyncConnectionPool


def key_sql(cursor, version):
    # ruleid: tenancy-guard-key-sql
    cursor.execute("SELECT key FROM guard.lookup_decoy_key WHERE version = %s", [version])
    # ruleid: tenancy-guard-key-sql
    cursor.execute("insert into guard.tenant_mac_key (version, key) values (%s, %s)", [1, b""])
    # ruleid: tenancy-guard-key-sql
    cursor.execute("""
        SELECT key
          FROM guard.approval_mac_key
    """)
    # ruleid: tenancy-guard-key-sql
    cursor.execute('-- read\nselect * from "guard"."tenant_mac_key"')
    # ruleid: tenancy-guard-key-sql
    cursor.execute("WITH k AS (SELECT 1) DELETE FROM guard.lookup_decoy_key")


def token(cursor, value):
    # ruleid: tenancy-token-setting
    cursor.execute("SELECT set_config('app.tenant_token', %s, true)", [value])
    # ruleid: tenancy-token-setting
    cursor.execute("\nSET LOCAL app.tenant_token = 'x'")
    # ruleid: tenancy-token-setting
    cursor.execute("WITH t AS (SELECT 1) SELECT set_config('app.tenant_token', %s, true)", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, false)", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT 1, set_config('app.agency_id', %s, 'f')", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, 'false')", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, 0)", [value])
    # PR 85 review R1 P2: forms the first regex let through.
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', guard.mint_token(%s), false)", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, 'off')", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, 'no')", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, '0')", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', %s, %s)", [value, False])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('app.agency_id', f(%s, true), false)", [value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('a', %s, false), set_config('b', %s, true)", [value, value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SELECT set_config('a', %s, true), set_config('b', %s, 'off')", [value, value])
    # ruleid: tenancy-no-session-setting
    cursor.execute("SET app.agency_id = 'b'")
    # ruleid: tenancy-no-session-setting
    cursor.execute("select 1; set session app.tenant_token = 'x'")
    # ruleid: tenancy-async-pool
    return AsyncConnectionPool("")


def allowed(cursor):
    # ok: tenancy-guard-key-sql
    names = {"guard.tenant_mac_key", "guard.lookup_decoy_key", "guard.approval_mac_key"}
    # ok: tenancy-guard-key-sql
    query = "SELECT has_table_privilege('skiw_app', %s, 'SELECT')"
    # ok: tenancy-token-setting
    read = "SELECT current_setting('app.tenant_token', true)"
    # ok: tenancy-no-session-setting
    local = "SELECT set_config('app.other', %s, true)"
    # ok: tenancy-no-session-setting
    nested = "SELECT set_config('app.other', guard.mint_token(%s, true), true)"
    # ok: tenancy-no-session-setting
    two = "SELECT set_config('a', %s, TRUE), set_config('b', f(%s), true) AS x"
    # ok: tenancy-no-session-setting
    cursor.execute("SET LOCAL lock_timeout = '5s'")
    return names, query, read, local, nested, two
