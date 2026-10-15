"""`bootstrap-db prepare|apply` (spec §8.4 H4, H6; plan §3 M1e).

A fake runner records what would reach `docker compose exec db`; a temporary root and a recording
chown stand in for the host. Every password is generated at run time.
"""

import base64
import hmac
import re
import secrets as token
import subprocess
from pathlib import Path

import pytest

from skiw_host import bootstrap_db
from skiw_host.bootstrap_db import PASSWORDS, main, verifier
from skiw_host.secrets import OWNER

HOST = Path(__file__).resolve().parents[1]
CI_ENV = HOST / "env" / "ci.env"
STATEMENT = re.compile(r"ALTER ROLE \"(\w+)\" PASSWORD '(SCRAM-SHA-256\$4096:[^']+)';")


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "root"
        self.store = self.root / "etc/skiw/secrets"
        self.store.mkdir(parents=True)
        self.calls: list[tuple[list[str], bytes]] = []
        self.chowns: dict[str, int] = {}
        self.fail_call = -1  # index of the runner call that fails

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((argv, stdin))
        if len(self.calls) - 1 == self.fail_call:  # psql may quote the failing statement
            return subprocess.CompletedProcess(argv, 1, stdin, stdin)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def chown(self, path: str, uid: int, gid: int) -> None:
        self.chowns[Path(path).name.removeprefix(".").removesuffix(".tmp")] = uid

    def run(self, mode: str, env: Path = CI_ENV) -> int:
        argv = [mode, "--env-file", str(env), "--root", str(self.root)]
        argv += ["--compose-file", "/srv/skiw/compose.yml"]
        return main(argv, run=self.runner, chown=self.chown)

    def passwords(self) -> dict[str, str]:
        values = {name: token.token_urlsafe(24) for name in PASSWORDS}
        for name, value in values.items():
            (self.store / name).write_text(f"{value}\n")
        return values


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def matches(password: str, stored: str) -> bool:
    iterations, salt, _ = re.split(r"[:$]", stored.removeprefix("SCRAM-SHA-256$"), maxsplit=2)
    assert int(iterations) == bootstrap_db.SCRAM_ITERATIONS
    return hmac.compare_digest(verifier(password, base64.b64decode(salt)), stored)


def test_prepare_mints_only_missing_password_files(rig: Rig) -> None:
    (rig.store / "postgres_password").write_text("kept\n")
    assert rig.run("prepare") == 0
    minted = {name: (rig.store / name).read_text() for name in PASSWORDS}
    assert minted.pop("postgres_password") == "kept\n"
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}\n", value) for value in minted.values())
    assert {n: (rig.store / n).stat().st_mode & 0o777 for n in minted} == dict.fromkeys(
        minted, 0o400
    )
    assert {n: rig.chowns[n] for n in minted} == {n: OWNER[n] for n in minted}
    assert rig.run("prepare") == 0  # a second run replaces nothing
    assert {name: (rig.store / name).read_text() for name in minted} == minted


def test_apply_runs_roles_sql_then_sets_every_password_on_stdin_only(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    values = rig.passwords()
    assert rig.run("apply") == 0
    (roles_argv, roles_sql), (argv, stdin) = rig.calls
    out = capsys.readouterr()
    for value in values.values():  # UNI-09: no value in argv, on stdin in clear, or in output
        assert value not in " ".join(argv) and value.encode() not in stdin
        assert value not in out.out + out.err
    assert roles_argv == argv
    assert argv[:2] == [argv[0], "compose"] and argv[-6:-1] == ["exec", "-T", "db", "sh", "-c"]
    assert "-U postgres" in argv[-1] and "/run/secrets/postgres_password" in argv[-1]
    assert roles_sql == (HOST / "db" / "roles.sql").read_bytes()
    statements = dict(STATEMENT.findall(stdin.decode()))
    assert statements.keys() == {name.removesuffix("_password") for name in PASSWORDS}
    assert all(matches(values[f"{role}_password"], v) for role, v in statements.items())


def test_the_psql_wrapper_keeps_the_superuser_password_out_of_env_argv_and_output(
    tmp_path: Path,
) -> None:
    """Runs the real wrapper with a probe in place of psql and reads what the child sees (H4)."""
    password = "a:b\\c" + token.token_urlsafe(24)  # a colon and a backslash must be escaped
    secret = tmp_path / "postgres_password"
    secret.write_text(f"{password}\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    probe = bin_dir / "psql"
    probe.write_text(
        "#!/bin/sh\n"
        f'env > "{tmp_path}/env"; echo "$@" > "{tmp_path}/argv"; cat > "{tmp_path}/stdin"\n'
        f'cp "$PGPASSFILE" "{tmp_path}/passfile"; stat -f %Lp "$PGPASSFILE" > "{tmp_path}/mode" '
        f'2>/dev/null || stat -c %a "$PGPASSFILE" > "{tmp_path}/mode"; echo "$PGPASSFILE" '
        f'> "{tmp_path}/path"; exit 7\n'
    )
    probe.chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "POSTGRES_DB": "skiw", "TMPDIR": str(tmp_path)}
    result = subprocess.run(
        ["/bin/sh", "-c", bootstrap_db.psql_script(str(secret))],
        input=b"SELECT 1;\n",
        env=env,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7  # psql's own status comes through
    for name in ("env", "argv", "stdin"):
        assert password not in (tmp_path / name).read_text()
    assert password.encode() not in result.stdout + result.stderr
    assert (tmp_path / "passfile").read_text() == "*:*:*:postgres:" + (
        password.replace("\\", "\\\\").replace(":", "\\:") + "\n"
    )
    assert (tmp_path / "mode").read_text().strip() == "600"
    assert not Path((tmp_path / "path").read_text().strip()).exists()  # removed on exit


def test_apply_again_sends_the_same_roles_and_only_new_salts(rig: Rig) -> None:
    rig.passwords()
    assert rig.run("apply") == 0 and rig.run("apply") == 0
    first, second = rig.calls[:2], rig.calls[2:]
    assert [argv for argv, _ in first] == [argv for argv, _ in second]
    assert first[0][1] == second[0][1]
    assert STATEMENT.sub("", first[1][1].decode()) == STATEMENT.sub("", second[1][1].decode())


@pytest.mark.parametrize("content", [None, "", "\n", "two\nlines\n", "with space\n", "é\n"])
def test_apply_refuses_a_missing_or_malformed_password_before_touching_the_db(
    rig: Rig, capsys: pytest.CaptureFixture[str], content: str | None
) -> None:
    rig.passwords()
    target = rig.store / "skiw_backup_password"
    target.unlink()
    if content is not None:
        target.write_text(content, encoding="utf-8")
    assert rig.run("apply") == 2
    assert rig.calls == []
    assert "skiw_backup_password" in capsys.readouterr().err


def test_a_failed_step_stops_and_withholds_the_password_statements(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.passwords()
    rig.fail_call = 0
    assert rig.run("apply") == 1 and len(rig.calls) == 1  # roles.sql failed: no password step
    assert "roles.sql failed (exit 1)" in capsys.readouterr().err  # no secret in it: shown
    rig.calls.clear()
    rig.fail_call = 1
    assert rig.run("apply") == 1
    err = capsys.readouterr().err
    assert "psql exit 1" in err and "SCRAM-SHA-256" not in err and "ALTER ROLE" not in err


def test_roles_sql_holds_no_password_and_the_closed_role_set() -> None:
    sql = (HOST / "db" / "roles.sql").read_text()
    statements = [line for line in sql.splitlines() if not line.startswith("--")]
    assert "password" not in "\n".join(statements).lower()
    created = set(re.findall(r"'(skiw_\w+)'", sql))
    assert created == {
        "skiw_migrator",
        "skiw_app",
        "skiw_readonly",
        "skiw_backup",
        "skiw_tenant_guard",
        "skiw_auth_lookup",
    }
    assert {f"{role}_password" for role in created} >= set(PASSWORDS) - {"postgres_password"}
