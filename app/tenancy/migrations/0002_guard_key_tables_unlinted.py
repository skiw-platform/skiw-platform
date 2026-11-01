# The two key tables (spec §4.1 `guard.tenant_mac_key`, `guard.lookup_decoy_key`; plan M4c-2a).
# Each is created and dropped as its NOLOGIN owner through `as_owner`, and nobody holds any grant
# on it, the migrator included (TEN-02): only the owner, or the migrator after an explicit SET ROLE
# to it, can read the keys. `migrate` writes them (M4c-3).
# `make migrate` skips this one migration in lintmigrations (--ignore-name): the linter flags the
# reverse `DROP TABLE` and has no per-statement ignore (docs/DECISIONS.md "M4c-2a"). Keep it to
# these two tables; test_guard_schema_live.py runs its forward and reverse instead.
from django.db import migrations

from tenancy.ddl import as_owner

VERSION = "version integer PRIMARY KEY CHECK (version BETWEEN 1 AND 999999)"
KEY = "key bytea NOT NULL CHECK (octet_length(key) >= 32)"


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0001_guard")]

    operations = [
        as_owner(
            "skiw_tenant_guard",
            [
                f"CREATE TABLE guard.tenant_mac_key ({VERSION}, {KEY},"
                " created_at timestamptz NOT NULL DEFAULT now(), retired_at timestamptz)"
            ],
            ["DROP TABLE guard.tenant_mac_key"],
        ),
        as_owner(
            "skiw_auth_lookup",
            [f"CREATE TABLE guard.lookup_decoy_key ({VERSION}, {KEY})"],
            ["DROP TABLE guard.lookup_decoy_key"],
        ),
    ]
