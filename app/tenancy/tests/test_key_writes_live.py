"""The migrate-time guard key writes (spec §4.1, §8.4 H4, TEN-02 (hard), UNI-09; plan M4c-3).
Each test runs `manage.py migrate` in a subprocess with generated keys, on key tables this module
empties first and restores after. Rows are read as the owner, through digests only."""

import base64
import hashlib
import os
import secrets
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql

from tenancy.ddl import GUARD_OWNERS, owner_role

pytestmark = pytest.mark.live

MANAGE = Path(__file__).resolve().parents[2] / "manage.py"
MAC, DECOY = "tenant_mac_key", "lookup_decoy_key"
OWNER = dict(zip((MAC, DECOY), ("skiw_tenant_guard", "skiw_auth_lookup"), strict=True))
SOURCE = dict(zip((MAC, DECOY), ("TENANT_TOKEN_KEY", "LOOKUP_DECOY_KEY"), strict=True))
STATE: dict[str, LiteralString] = {
    MAC: "SELECT version, encode(sha256(key), 'hex'), created_at, retired_at IS NOT NULL"
    " FROM guard.tenant_mac_key ORDER BY 1",
    DECOY: "SELECT version, encode(sha256(key), 'hex') FROM guard.lookup_decoy_key ORDER BY 1",
}
Keys = dict[int, bytes]


def new_key() -> bytes:
    return secrets.token_bytes(32)


def lines(keys: Keys) -> str:
    return "".join(f"v{n}:{base64.b64encode(k).decode()}\n" for n, k in sorted(keys.items()))


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["MIGRATION_DATABASE_URL"])


def state(table: str) -> list[tuple[Any, ...]]:
    with connect() as conn, conn.cursor() as cursor, owner_role(cursor, OWNER[table]):
        return cursor.execute(STATE[table]).fetchall()


def states() -> dict[str, list[tuple[Any, ...]]]:
    return {table: state(table) for table in (MAC, DECOY)}


def digest(keys: Keys) -> list[tuple[int, str]]:
    return [(n, hashlib.sha256(k).hexdigest()) for n, k in sorted(keys.items())]


def migrate(
    mac: Keys | None,
    decoy: Keys | None,
    *args: str,
    url: str = "MIGRATION_DATABASE_URL",
    **env: str,
) -> subprocess.CompletedProcess[str]:
    run_env = {k: v for k, v in os.environ.items() if not k.endswith("_KEY_FILE")}
    run_env.update(DATABASE_URL=os.environ[url])
    for table, keys in ((MAC, mac), (DECOY, decoy)):
        run_env.pop(SOURCE[table], None)
        if keys is not None:
            run_env[SOURCE[table]] = lines(keys)
    run_env.update(env)
    command = [sys.executable, str(MANAGE), "migrate", *args]
    return subprocess.run(command, env=run_env, capture_output=True, text=True, check=False)


def assert_no_key_text(result: subprocess.CompletedProcess[str], *sets: Keys) -> None:
    output = result.stdout + result.stderr
    for keys in sets:
        for key in keys.values():
            for text in (base64.b64encode(key).decode(), key.hex(), repr(key)[2:-1]):
                assert text not in output


@pytest.fixture(autouse=True)
def empty_key_tables() -> Iterator[None]:
    """Empty both tables (as their owners), then put the rows `make migrate` wrote back."""
    saved: dict[str, list[tuple[Any, ...]]] = {}
    columns = {MAC: "version, key, created_at, retired_at", DECOY: "version, key"}

    def query(text: str, table: str) -> sql.Composed:
        return sql.SQL(text).format(sql.SQL(columns[table]), sql.Identifier("guard", table))

    with connect() as conn, conn.cursor() as cursor:
        for table in (MAC, DECOY):
            with owner_role(cursor, OWNER[table]):
                saved[table] = cursor.execute(query("SELECT {} FROM {}", table)).fetchall()
                cursor.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier("guard", table)))
    yield
    with connect() as conn, conn.cursor() as cursor:
        for table in (MAC, DECOY):
            with owner_role(cursor, OWNER[table]):
                cursor.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier("guard", table)))
                marks = sql.SQL(", ").join([sql.Placeholder()] * len(columns[table].split(",")))
                insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier("guard", table), sql.SQL(columns[table]), marks
                )
                for row in saved[table]:
                    cursor.execute(insert, row)


def test_keys_are_written_and_a_second_run_changes_nothing() -> None:
    mac, decoy = {1: new_key(), 2: new_key()}, {1: new_key()}
    first = migrate(mac, decoy)
    assert first.returncode == 0, first.stderr
    written = states()
    assert [row[:2] for row in written[MAC]] == digest(mac)
    assert [row[3] for row in written[MAC]] == [False, False]
    assert written[DECOY] == digest(decoy)
    second = migrate(mac, decoy)
    assert second.returncode == 0, second.stderr
    assert states() == written  # created_at included: nothing was rewritten
    assert_no_key_text(first, mac, decoy)
    assert_no_key_text(second, mac, decoy)


@pytest.mark.parametrize("changed", [MAC, DECOY])
def test_a_changed_key_stops_migrate_and_writes_nothing(changed: str) -> None:
    keys = {MAC: {1: new_key()}, DECOY: {1: new_key()}}
    assert migrate(keys[MAC], keys[DECOY]).returncode == 0
    before = states()
    # The changed table's v1 gets new bytes; the other gains a v2, which must not land either.
    other = DECOY if changed == MAC else MAC
    after = {changed: {1: new_key()}, other: {**keys[other], 2: new_key()}}
    result = migrate(after[MAC], after[DECOY])
    assert result.returncode != 0
    assert f"{SOURCE[changed]}: version(s) 1 changed; restore the stored line" in result.stderr
    assert states() == before
    assert_no_key_text(result, keys[MAC], keys[DECOY], after[MAC], after[DECOY])


def test_an_unlisted_version_is_retired_or_deleted() -> None:
    mac, decoy = {1: new_key(), 2: new_key()}, {1: new_key(), 2: new_key()}
    assert migrate(mac, decoy).returncode == 0
    result = migrate({2: mac[2]}, {2: decoy[2]})
    assert result.returncode == 0, result.stderr
    rows = state(MAC)
    assert [row[:2] for row in rows] == digest(mac)
    assert [row[3] for row in rows] == [True, False]
    assert state(DECOY) == digest({2: decoy[2]})


@pytest.mark.parametrize("same_bytes", [True, False])
def test_a_retired_version_listed_again_stops_migrate(same_bytes: bool) -> None:
    """Owner decision 2026-11-03: no override and no un-retire, whatever the listed bytes."""
    mac, decoy = {1: new_key(), 2: new_key()}, {1: new_key()}
    assert migrate(mac, decoy).returncode == 0
    assert migrate({2: mac[2]}, decoy).returncode == 0  # v1 retired
    before = states()
    again = {1: mac[1] if same_bytes else new_key(), 2: mac[2], 3: new_key()}
    result = migrate(again, decoy)
    assert result.returncode != 0
    assert "TENANT_TOKEN_KEY: version(s) 1 retired; remove the line" in result.stderr
    assert states() == before  # v1 still retired, v3 not inserted
    assert_no_key_text(result, mac, decoy, again)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "TENANT_TOKEN_KEY_FILE: the secret file cannot be read"),
        ("", "TENANT_TOKEN_KEY_FILE: holds no key version"),
        ("v1:not-base64!\n", "TENANT_TOKEN_KEY_FILE: line 1 is not v<n>:<base64>"),
        (f"v1:{base64.b64encode(bytes(31)).decode()}\n", "line 1 is too short"),
    ],
)
def test_a_missing_or_malformed_key_file_fails(
    tmp_path: Path, content: str | None, message: str
) -> None:
    path = tmp_path / "tenant_token_key"
    if content is not None:
        path.write_text(content)
    result = migrate(None, {1: new_key()}, TENANT_TOKEN_KEY_FILE=str(path))
    assert result.returncode != 0
    assert message in result.stderr
    assert states() == {MAC: [], DECOY: []}


@pytest.mark.parametrize(
    ("decoy", "args", "url", "message"),
    [
        (
            None,
            (),
            "MIGRATION_DATABASE_URL",
            "LOOKUP_DECOY_KEY (or LOOKUP_DECOY_KEY_FILE on hosts)",
        ),
        ({1: new_key()}, ("--plan",), "MIGRATION_DATABASE_URL", None),
        ({1: new_key()}, (), "DATABASE_URL", "guard key writes run only as skiw_migrator"),
    ],
)
def test_no_key_plan_and_runtime_role_write_nothing(
    decoy: Keys | None, args: tuple[str, ...], url: str, message: str | None
) -> None:
    result = migrate({1: new_key()}, decoy, *args, url=url)
    assert (result.returncode == 0) is (message is None), result.stderr
    assert message is None or message in result.stderr
    assert states() == {MAC: [], DECOY: []}


@pytest.mark.parametrize("table", [MAC, DECOY])
def test_no_standing_grant_carries_the_writes(table: str) -> None:
    assert migrate({1: new_key()}, {1: new_key()}).returncode == 0
    with connect() as conn:
        query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("guard", table))
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied"):
            conn.execute(query)


@pytest.mark.parametrize("role", sorted(GUARD_OWNERS))
def test_owner_role_switches_and_resets_inside_a_transaction(role: str) -> None:
    with connect() as conn, conn.cursor() as cursor:
        with owner_role(cursor, role):
            assert cursor.execute("SELECT current_user::text").fetchall() == [(role,)]
        assert cursor.execute("SELECT session_user::text, current_user::text").fetchall() == [
            ("skiw_migrator", "skiw_migrator")
        ]
        conn.rollback()


@pytest.mark.parametrize("table", [MAC, DECOY])
def test_owner_role_resets_when_the_block_raises_and_is_caught(table: str) -> None:
    query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("guard", table))
    with connect() as conn, conn.cursor() as cursor:
        with pytest.raises(LookupError), owner_role(cursor, OWNER[table]):
            raise LookupError
        assert cursor.execute("SELECT current_user::text").fetchall() == [("skiw_migrator",)]
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied"):
            cursor.execute(query)


@pytest.mark.parametrize("role", sorted(GUARD_OWNERS))
def test_owner_role_outside_a_transaction_raises_before_the_block(role: str) -> None:
    ran = False
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn,
        conn.cursor() as cursor,
        pytest.raises(RuntimeError, match=f"current_user is not {role}"),
        owner_role(cursor, role),
    ):
        ran = True
    assert not ran
