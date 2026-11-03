"""`migrate` writes the two guard key tables from the host secret files (spec §4.1, §8.4 H4;
plan M4c-3). `TenancyConfig.ready()` connects it (then the agency seed, M4c-5) to `post_migrate`,
which every `migrate` run sends, even with nothing to apply; `migrate --plan` sends none. Django
`flush` and pytest-django `transaction=True` teardown send it too, so it would run there and refuse
as a non-migrator role; no test uses either today.

One transaction, run only as `skiw_migrator` (checked before the first `SET ROLE`, because after
it `current_user` is the owner). The migrator holds no grant on either table (M4c-2a), so every
statement, the compares included, runs as the table's owner through `tenancy.ddl.owner_role`:
- `guard.tenant_mac_key`: a missing version is inserted, the same bytes are left alone, an
  unlisted version gets `retired_at = now()`. Different bytes for a stored version stop `migrate`
  (plan line ~202). A retired version listed again stops it too, whatever its bytes (owner decision
  2026-11-03): no override; remove the line, and a key that is safe after all comes back only
  under a new version number, never by un-retiring the old one.
- `guard.lookup_decoy_key` holds exactly the file's versions: a changed one stops `migrate`, an
  unlisted one is deleted.
Key bytes go in as bound parameters on a server-binding cursor, so they are not in the statement
text (pg_stat_activity, the server log); they never come back out, and no message names them
(UNI-09): errors name the key and its versions only.
"""

from dataclasses import dataclass
from typing import Any, LiteralString

import psycopg
from django.conf import settings
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.migrations.recorder import MigrationRecorder

from tenancy.ddl import owner_role

MIGRATOR = "skiw_migrator"
TABLES_MIGRATION = ("tenancy", "0002_guard_key_tables_unlinted")


@dataclass(frozen=True)
class KeyTable:
    source: str  # the env variable (or <source>_FILE on hosts) that holds the lines
    setting: str  # its lazy reader in settings
    owner: str
    changed: LiteralString  # stored versions whose bytes differ from the file's
    refused: LiteralString | None  # listed versions that may not be written again
    insert: LiteralString
    unlisted: LiteralString  # retire or delete what the file no longer lists


TENANT_MAC = KeyTable(
    source="TENANT_TOKEN_KEY",
    setting="SKIW_TENANT_TOKEN_KEYS",
    owner="skiw_tenant_guard",
    changed="SELECT k.version FROM guard.tenant_mac_key k"
    " JOIN unnest(%s::integer[], %s::bytea[]) AS f(version, key) USING (version)"
    " WHERE k.key <> f.key ORDER BY 1",
    refused="SELECT version FROM guard.tenant_mac_key"
    " WHERE retired_at IS NOT NULL AND version = ANY(%s::integer[]) ORDER BY 1",
    insert="INSERT INTO guard.tenant_mac_key (version, key) SELECT version, key"
    " FROM unnest(%s::integer[], %s::bytea[]) AS f(version, key) ON CONFLICT (version) DO NOTHING",
    unlisted="UPDATE guard.tenant_mac_key SET retired_at = now()"
    " WHERE retired_at IS NULL AND version <> ALL(%s::integer[])",
)
LOOKUP_DECOY = KeyTable(
    source="LOOKUP_DECOY_KEY",
    setting="SKIW_LOOKUP_DECOY_KEYS",
    owner="skiw_auth_lookup",
    changed="SELECT k.version FROM guard.lookup_decoy_key k"
    " JOIN unnest(%s::integer[], %s::bytea[]) AS f(version, key) USING (version)"
    " WHERE k.key <> f.key ORDER BY 1",
    refused=None,  # an unlisted decoy version is deleted, so none is ever kept retired
    insert="INSERT INTO guard.lookup_decoy_key (version, key) SELECT version, key"
    " FROM unnest(%s::integer[], %s::bytea[]) AS f(version, key) ON CONFLICT (version) DO NOTHING",
    unlisted="DELETE FROM guard.lookup_decoy_key WHERE version <> ALL(%s::integer[])",
)
KEY_TABLES = (TENANT_MAC, LOOKUP_DECOY)


def _read(table: KeyTable) -> tuple[list[int], list[bytes]]:
    try:
        keys: list[tuple[int, bytes]] = getattr(settings, table.setting)()
    except RuntimeError as exc:  # config.env's errors name the variable and line, never a value
        raise CommandError(f"guard key writes: {exc}") from None
    return [version for version, _ in keys], [key for _, key in keys]


def _write(cursor: "psycopg.Cursor[Any]", table: KeyTable) -> None:
    versions, keys = _read(table)
    with owner_role(cursor, table.owner):
        # The retired check runs first, so a retired version is reported as retired even when its
        # bytes changed too.
        checks: list[tuple[LiteralString | None, tuple[object, ...], str]] = [
            (table.refused, (versions,), "retired; remove the line (a key that is safe after all"),
            (table.changed, (versions, keys), "changed; restore the stored line (a new key"),
        ]
        for query, params, problem in checks:
            bad = [] if query is None else [r[0] for r in cursor.execute(query, params).fetchall()]
            if bad:
                raise CommandError(
                    f"{table.source}: version(s) {', '.join(map(str, bad))} {problem} goes in"
                    " under a new, higher version). Nothing was written."
                )
        cursor.execute(table.insert, (versions, keys))
        cursor.execute(table.unlisted, (versions,))


def write_guard_keys(using: str = DEFAULT_DB_ALIAS) -> None:
    """Bring both key tables in line with the key files, all or nothing."""
    connection = connections[using]
    # A server-binding cursor on Django's own connection (opened by atomic), in its transaction.
    with transaction.atomic(using=using), psycopg.Cursor(connection.connection) as cursor:
        row = cursor.execute("SELECT session_user::text, current_user::text").fetchone()
        if row != (MIGRATOR, MIGRATOR):
            raise CommandError(f"guard key writes run only as {MIGRATOR}; nothing was written")
        if TABLES_MIGRATION not in MigrationRecorder(connection).applied_migrations():
            return  # migrated back before the key tables: nothing to write
        try:
            for table in KEY_TABLES:
                _write(cursor, table)
        except psycopg.Error as exc:  # its text can quote a row; keep only the code
            raise CommandError(
                f"guard key writes failed (SQLSTATE {exc.sqlstate}); nothing was written"
            ) from None
        if cursor.execute("SELECT current_user::text").fetchone() != (MIGRATOR,):
            raise CommandError("guard key writes: the owner role was not reset")
