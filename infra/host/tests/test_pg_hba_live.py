"""Each DB role connects only from its network or the socket (spec §8.4 H6; TEN-02, TEN-10).

The `host_live` tests start `db` from compose.yml with env/ci.env under a throwaway project, with
pg_hba.conf rendered by bootstrap-db and every secret generated per run in a temp dir, then run
`bootstrap-db apply` (twice) and connect from a psql probe container on the `app` and the `ops`
network. Without a Docker daemon they skip locally and fail in CI.
"""

import json
import os
import secrets
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from skiw_host import bootstrap_db

HOST = Path(__file__).resolve().parents[1]
ENV_FILE = HOST / "env" / "ci.env"
DB_NAME = "skiw"  # SKIW_POSTGRES_DB in env/ci.env
ROLES = "select rolname, rolsuper, rolbypassrls, rolcanlogin, rolconnlimit, rolconfig from pg_roles"
CLOSED = {"postgres", "skiw_migrator", "skiw_app", "skiw_readonly", "skiw_backup"}
CLOSED |= {"skiw_tenant_guard", "skiw_auth_lookup"}
live = pytest.mark.host_live


@dataclass
class Db:
    command: list[str]
    compose_args: list[str]
    passwords: dict[str, str]

    def compose(self, *args: str, password: str = "") -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PGPASSWORD": password}  # psql reads it in the container; not argv
        return subprocess.run(
            [*self.command, *args], env=env, capture_output=True, text=True, timeout=300
        )

    def probe(self, network: str, role: str) -> subprocess.CompletedProcess[str]:
        psql = ["-h", "db", "-U", role, "-d", DB_NAME, "-tAc", "select current_user"]
        return self.compose("run", "--rm", f"probe-{network}", *psql, password=self.passwords[role])

    def socket(self, role: str, sql: str) -> subprocess.CompletedProcess[str]:
        psql = ["psql", "-X", "-U", role, "-d", DB_NAME, "-tAc", sql]
        return self.compose(
            "exec", "-T", "-e", "PGPASSWORD", "db", *psql, password=self.passwords[role]
        )

    def apply(self, root: Path) -> None:
        argv = ["apply", "--env-file", str(ENV_FILE), "--compose-file", str(HOST / "compose.yml")]
        argv += [f"--root={root}", *(f"--compose-arg={a}" for a in self.compose_args)]
        assert bootstrap_db.main(argv) == 0


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory, docker_cli: str) -> Iterator[Db]:
    tmp = tmp_path_factory.mktemp("hba")
    base = [docker_cli, "compose", "-f", str(HOST / "compose.yml"), "--env-file", str(ENV_FILE)]
    store = tmp / "root/etc/skiw/secrets"
    store.mkdir(parents=True)
    files = {}
    for name in bootstrap_db.PASSWORDS:  # generated per run; never committed, never printed
        files[name] = str(store / name)
        Path(files[name]).write_text(f"{secrets.token_urlsafe(24)}\n")
        Path(files[name]).chmod(0o644)  # read by the db container's uid 999
    hba = tmp / "pg_hba.conf"
    hba.write_text(bootstrap_db.render_hba(ENV_FILE))
    image = json.loads(
        subprocess.run(
            [*base, "config", "--format", "json"], capture_output=True, text=True, check=True
        ).stdout
    )["services"]["db"]["image"]
    probe = {
        "image": image,
        "profiles": ["probe"],
        "entrypoint": ["psql", "-X"],
        "environment": ["PGPASSWORD"],
        "logging": {"driver": "local"},
    }
    override = tmp / "override.json"
    override.write_text(
        json.dumps(
            {
                "secrets": {n: {"file": f} for n, f in files.items()},
                "configs": {"pg_hba": {"file": str(hba)}},
                "services": {
                    "db": {"logging": {"driver": "local"}},  # journald is a host setting
                    "probe-app": {**probe, "networks": ["app"]},
                    "probe-ops": {**probe, "networks": ["ops"]},
                },
            }
        )
    )
    extra = ["-f", str(override), "-p", f"skiw-hba-{secrets.token_hex(4)}"]
    roles = {
        n.removesuffix("_password"): Path(f).read_text().strip()
        for n, f in files.items()
        if n.endswith("_password")
    }
    stack = Db([*base[:4], *extra, *base[4:]], extra, roles)
    try:
        started = stack.compose("up", "-d", "--wait", "db")
        assert started.returncode == 0, started.stderr[-3000:]
        stack.apply(tmp / "root")
        before = stack.socket("postgres", ROLES)
        stack.apply(tmp / "root")  # idempotent: the same role set and attributes
        assert before.returncode == 0 and stack.socket("postgres", ROLES).stdout == before.stdout
        yield stack
    finally:
        stack.compose("down", "-v", "--remove-orphans")


@live
def test_bootstrap_db_leaves_exactly_the_closed_role_set(db: Db) -> None:
    listed = db.socket("postgres", "select rolname from pg_roles where rolname !~ '^pg_'")
    assert set(listed.stdout.split()) == CLOSED


@live
@pytest.mark.parametrize(
    ("network", "role"),
    [("app", "skiw_app"), ("app", "skiw_migrator"), ("ops", "skiw_backup")],
)
def test_role_connects_from_its_network(db: Db, network: str, role: str) -> None:
    result = db.probe(network, role)
    assert (result.returncode, result.stdout.strip()) == (0, role), result.stderr


@live
@pytest.mark.parametrize(
    ("network", "role"),
    [
        ("app", "skiw_backup"),  # TEN-02: the BYPASSRLS role never from the app network
        ("ops", "skiw_app"),
        ("ops", "skiw_migrator"),
        ("app", "skiw_readonly"),  # socket only
        ("ops", "skiw_readonly"),
        ("app", "postgres"),
        ("ops", "postgres"),
    ],
)
def test_role_is_refused_from_any_other_network(db: Db, network: str, role: str) -> None:
    result = db.probe(network, role)
    assert result.returncode != 0
    assert "pg_hba.conf rejects connection" in result.stderr  # a rule refused it, not a password


@live
def test_readonly_and_postgres_connect_over_the_socket_only(db: Db) -> None:
    for role in ("skiw_readonly", "postgres"):
        result = db.socket(role, "select current_user")
        assert (result.returncode, result.stdout.strip()) == (0, role), result.stderr
    for role in ("skiw_app", "skiw_migrator", "skiw_backup"):
        assert "pg_hba.conf rejects connection" in db.socket(role, "select 1").stderr


@live
def test_pg_hba_is_the_rendered_file_mounted_read_only(db: Db) -> None:
    shown = db.socket("postgres", "show hba_file")
    assert shown.stdout.strip() == "/etc/skiw/pg_hba.conf"
    written = db.compose("exec", "-T", "db", "sh", "-c", "echo >> /etc/skiw/pg_hba.conf")
    assert written.returncode != 0
