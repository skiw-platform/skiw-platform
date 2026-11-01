"""`roles.sql` against a throwaway PostgreSQL (spec §8.4 H6, TEN-02; plan §3 M1e).

The `host_live` tests run only under `make host-test-live`. One container from the digest-pinned
db image: no network, no published port, data on tmpfs, removed afterwards. They prove that a
second run changes no value (plan M4c-1 A7), that a run resets INHERIT and SET on the migrator's
own grant, and drift handling: a membership the file does not allow stops the run and changes
nothing.
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
    "select string_agg(m, ',' order by m) from (select member::regrole || ' in ' "
    "|| roleid::regrole as m from pg_auth_members) s where m like 'skiw\\_%'"
)
ALLOWED = (
    "skiw_backup in pg_read_all_data,skiw_migrator in skiw_auth_lookup,"
    "skiw_migrator in skiw_tenant_guard"
)
# Every value roles.sql sets or checks, compared by value (a re-run rewrites the role rows).
CATALOG = """select concat_ws('|', 'role', rolname, rolcanlogin, rolsuper, rolinherit, rolbypassrls,
  rolcreatedb, rolcreaterole, rolreplication, rolconnlimit, rolconfig) from pg_roles
union all select concat_ws('|', 'member', member::regrole, roleid::regrole, grantor::regrole,
  admin_option, inherit_option, set_option) from pg_auth_members
union all select concat_ws('|', 'setting', setrole::regrole, setdatabase, setconfig)
  from pg_db_role_setting
union all select concat_ws('|', 'db', datname, datdba::regrole, datacl) from pg_database
union all select concat_ws('|', 'schema', nspname, nspowner::regrole, nspacl) from pg_namespace
  where nspname = 'public'
order by 1"""


def test_a_clean_run_and_a_second_run_pass_and_the_second_changes_nothing(db: Db) -> None:
    assert db.roles().returncode == 0
    before = db.value(CATALOG)
    assert db.roles().returncode == 0
    assert db.value(CATALOG) == before  # A7: the GRANTs with the same options are no-ops
    assert db.value(MEMBERS) == ALLOWED
    options = (
        "select string_agg(concat_ws('|', roleid::regrole, admin_option, inherit_option, "
        "set_option), ',' order by roleid::regrole::text) from pg_auth_members "
        "where member = 'skiw_migrator'::regrole"
    )
    assert db.value(options) == "skiw_auth_lookup|f|f|t,skiw_tenant_guard|f|f|t"


def test_a_run_resets_inherit_and_set_on_its_own_grant(db: Db) -> None:
    # PostgreSQL 17 updates the options of an existing grant from the same grantor in place, so a
    # re-run repairs this drift silently instead of stopping (ADMIN OPTION is not reset: below).
    assert db.roles().returncode == 0
    grant = "GRANT skiw_auth_lookup TO skiw_migrator WITH INHERIT TRUE, SET FALSE;"
    assert db.psql(grant).returncode == 0
    assert db.roles().returncode == 0
    options = (
        "select concat_ws('|', admin_option, inherit_option, set_option) from pg_auth_members "
    )
    options += "where member = 'skiw_migrator'::regrole and roleid = 'skiw_auth_lookup'::regrole"
    assert db.value(options) == "f|f|t"


@pytest.mark.parametrize(
    ("grant", "revoke", "named"),
    [
        (
            "GRANT pg_read_all_data TO skiw_app;",
            "REVOKE pg_read_all_data FROM skiw_app;",
            "skiw_app in pg_read_all_data",
        ),
        (
            "GRANT pg_monitor TO skiw_backup;",
            "REVOKE pg_monitor FROM skiw_backup;",
            "skiw_backup in pg_monitor",
        ),
        (
            "GRANT skiw_app TO skiw_auth_lookup;",
            "REVOKE skiw_app FROM skiw_auth_lookup;",
            "skiw_auth_lookup in skiw_app",
        ),
        (  # a guard role granted to a role outside the six
            "GRANT skiw_auth_lookup TO pg_monitor;",
            "REVOKE skiw_auth_lookup FROM pg_monitor;",
            "pg_monitor in skiw_auth_lookup",
        ),
        (  # a third guard membership
            "GRANT skiw_tenant_guard TO skiw_readonly WITH INHERIT FALSE, SET TRUE;",
            "REVOKE skiw_tenant_guard FROM skiw_readonly;",
            "skiw_readonly in skiw_tenant_guard",
        ),
        (  # the migrator could hand the bypass role on
            "GRANT skiw_auth_lookup TO skiw_migrator WITH ADMIN OPTION;",
            "REVOKE ADMIN OPTION FOR skiw_auth_lookup FROM skiw_migrator;",
            "skiw_migrator in skiw_auth_lookup",
        ),
        (  # a second grant of the migrator's pair, from another grantor
            "GRANT skiw_auth_lookup TO skiw_readonly WITH ADMIN OPTION, INHERIT FALSE, SET FALSE;"
            "GRANT skiw_auth_lookup TO skiw_migrator WITH INHERIT FALSE, SET TRUE"
            " GRANTED BY skiw_readonly;",
            "REVOKE skiw_auth_lookup FROM skiw_readonly CASCADE;",
            "skiw_readonly in skiw_auth_lookup",
        ),
    ],
)
def test_an_unexpected_membership_stops_the_run_and_changes_nothing(
    db: Db, grant: str, revoke: str, named: str
) -> None:
    assert db.roles().returncode == 0
    assert db.psql(grant).returncode == 0
    before = db.value(CATALOG)
    assert db.psql("ALTER ROLE skiw_app CONNECTION LIMIT 7;").returncode == 0
    result = db.roles()
    assert result.returncode != 0
    assert "unexpected role membership" in result.stderr and named in result.stderr
    assert db.value("select rolconnlimit from pg_roles where rolname = 'skiw_app'") == "7"
    assert db.psql("ALTER ROLE skiw_app CONNECTION LIMIT -1;").returncode == 0
    assert db.value(CATALOG) == before  # nothing dropped or reset: a person decides
    assert db.psql(revoke).returncode == 0
    assert db.roles().returncode == 0
    assert db.value(MEMBERS) == ALLOWED
