"""`roles.sql` against a throwaway PostgreSQL (spec §8.4 H6, TEN-02; plan §3 M1e).

The `host_live` tests run only under `make host-test-live`. One container from the digest-pinned
db image: no network, no published port, data on tmpfs, removed afterwards. They prove drift
handling: a membership the file does not allow stops the run and changes nothing.
"""

import os
import re
import secrets
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

COMPOSE = Path(__file__).resolve().parents[1] / "compose.yml"
ROLES_SQL = Path(__file__).resolve().parents[1] / "db" / "roles.sql"
IMAGE = re.search(r"image: (postgres:\S+)", COMPOSE.read_text())
pytestmark = pytest.mark.host_live


def docker() -> str:
    path = shutil.which("docker")
    if path and subprocess.run([path, "info"], capture_output=True, check=False).returncode == 0:
        return path
    if os.environ.get("CI") == "true":
        pytest.fail("no Docker daemon in CI: the role tests must run, not skip")
    pytest.skip("no Docker daemon locally; CI runs the role tests")


class Db:
    def __init__(self, cli: str, name: str) -> None:
        self.cli, self.name = cli, name

    def psql(self, sql: str, *args: str) -> subprocess.CompletedProcess[str]:
        argv = ["exec", "-i", self.name, "psql", "-X", "-q", "-U", "postgres", "-d", "skiw", *args]
        return subprocess.run(
            [self.cli, *argv], input=sql, capture_output=True, text=True, check=False
        )

    def roles(self) -> subprocess.CompletedProcess[str]:
        return self.psql(ROLES_SQL.read_text(), "-v", "db=skiw")

    def value(self, sql: str) -> str:
        result = self.psql(sql, "-At")
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()


@pytest.fixture
def db() -> Iterator[Db]:
    assert IMAGE, "the db image is not pinned in compose.yml"
    cli, name = docker(), f"skiw-roles-{secrets.token_hex(4)}"
    run = [cli, "run", "-d", "--rm", "--name", name, "--network", "none", "--tmpfs"]
    run += ["/var/lib/postgresql/data", "-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(16)}"]
    run += ["-e", "POSTGRES_DB=skiw", IMAGE.group(1)]
    subprocess.run(run, check=True, capture_output=True)
    try:
        for _ in range(60):
            ready = subprocess.run(
                [cli, "exec", name, "pg_isready", "-U", "postgres", "-d", "skiw"]
            )
            probe = subprocess.run(
                [cli, "exec", name, "psql", "-U", "postgres", "-d", "skiw", "-Atc", "select 1"],
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0 and probe.returncode == 0:
                break
            time.sleep(1)
        yield Db(cli, name)
    finally:
        subprocess.run([cli, "rm", "-f", name], capture_output=True, check=False)


MEMBERS = (
    "select string_agg(member::regrole || ' in ' || roleid::regrole, ',' order by 1) "
    "from pg_auth_members where member::regrole::text like 'skiw\\_%'"
)


def test_a_clean_run_and_a_second_run_pass_with_only_the_backup_membership(db: Db) -> None:
    assert db.roles().returncode == 0
    assert db.roles().returncode == 0
    assert db.value(MEMBERS) == "skiw_backup in pg_read_all_data"


@pytest.mark.parametrize(
    ("member", "granted"),
    [
        ("skiw_app", "pg_read_all_data"),
        ("skiw_backup", "pg_monitor"),
        ("skiw_auth_lookup", "skiw_app"),
    ],
)
def test_an_unexpected_membership_stops_the_run_and_changes_nothing(
    db: Db, member: str, granted: str
) -> None:
    assert db.roles().returncode == 0
    assert db.psql(f"GRANT {granted} TO {member};").returncode == 0
    before = db.value(MEMBERS)
    assert db.psql("ALTER ROLE skiw_app CONNECTION LIMIT 7;").returncode == 0
    result = db.roles()
    assert result.returncode != 0
    assert "unexpected role membership" in result.stderr and member in result.stderr
    assert db.value(MEMBERS) == before  # nothing dropped: a person decides
    assert db.value("select rolconnlimit from pg_roles where rolname = 'skiw_app'") == "7"
    assert db.psql(f"REVOKE {granted} FROM {member};").returncode == 0
    assert db.roles().returncode == 0
    assert db.value(MEMBERS) == "skiw_backup in pg_read_all_data"
