"""`bootstrap-db prepare|apply` (spec §8.4 H4, H6; runbook docs/runbooks/host-rebuild.md).

`prepare` (before `docker compose up db`) mints each missing DB password file, never replacing
one (the per-role pg_hba.conf is M1e-2). `apply` (db running) runs db/roles.sql,
then sets every DB role's password from its file, through the unix socket as `postgres` with
`docker compose exec db`. Passwords reach psql only on stdin, as SCRAM verifiers computed here;
no value is ever in argv, output or a message (UNI-09).
"""

import argparse
import base64
import hashlib
import hmac
import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from skiw_host.bootstrap_secrets import Chown, Host, Refused, write
from skiw_host.secrets import INVENTORY, OWNER, Kind

DB = Path(__file__).resolve().parents[1] / "db"
PASSWORDS = tuple(secret.name for secret in INVENTORY if secret.kind is Kind.DB_PASSWORD)
PASSWORD_BYTES = 32
SCRAM_ITERATIONS = 4096  # PostgreSQL's default scram_iterations
SALT_BYTES = 16
ONE_LINE = re.compile(r"[\x21-\x7e]+")  # printable ASCII: SASLprep leaves it unchanged
# Inside `db`: the superuser over the socket, its password read there from its own secret file.
PSQL = (
    'PGPASSWORD="$(cat /run/secrets/postgres_password)" exec psql -X -q -v ON_ERROR_STOP=1 '
    '-U postgres -d "$POSTGRES_DB" -v db="$POSTGRES_DB"'
)
Runner = Callable[[list[str], bytes], subprocess.CompletedProcess[bytes]]


class Failed(Exception):
    pass


def run_command(argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, input=stdin, capture_output=True, check=False)  # noqa: S603 - argv built here, no shell


def prepare(host: Host) -> list[str]:
    if not host.secrets.is_dir():
        raise Refused(f"{host.secrets} does not exist: run bootstrap-secrets init first")
    minted = []
    for name in PASSWORDS:
        if not (host.secrets / name).exists():
            value = secrets.token_urlsafe(PASSWORD_BYTES)
            write(host, host.secrets / name, f"{value}\n", OWNER[name])
            minted.append(name)
    return minted


def passwords(host: Host) -> dict[str, str]:
    """Role → password, every file checked before the database is touched (fail closed)."""
    found = {}
    for name in PASSWORDS:
        try:
            value = (host.secrets / name).read_text(encoding="ascii").removesuffix("\n")
        except (OSError, UnicodeDecodeError):
            raise Refused(f"{host.secrets / name} is missing or unreadable") from None
        if not ONE_LINE.fullmatch(value):
            raise Refused(f"{host.secrets / name} is empty or not one printable ASCII line")
        found[name.removesuffix("_password")] = value
    return found


def verifier(password: str, salt: bytes) -> str:
    """The SCRAM-SHA-256 verifier PostgreSQL stores (RFC 5802, RFC 7677)."""
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("ascii"), salt, SCRAM_ITERATIONS)
    stored = hashlib.sha256(hmac.digest(salted, b"Client Key", "sha256")).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")
    parts = [base64.b64encode(x).decode("ascii") for x in (salt, stored, server)]
    return f"SCRAM-SHA-256${SCRAM_ITERATIONS}:{parts[0]}${parts[1]}:{parts[2]}"


def apply(compose: list[str], run: Runner, host: Host) -> int:
    found = passwords(host)
    psql = [*compose, "exec", "-T", "db", "sh", "-c", PSQL]
    roles = run(psql, (DB / "roles.sql").read_bytes())
    if roles.returncode != 0:
        detail = roles.stderr.decode("utf-8", "replace")[-2000:]
        raise Failed(f"roles.sql failed (exit {roles.returncode}):\n{detail}")
    statements = "".join(
        f"ALTER ROLE \"{role}\" PASSWORD '{verifier(value, os.urandom(SALT_BYTES))}';\n"
        for role, value in found.items()
    )
    done = run(psql, f"BEGIN;\n{statements}COMMIT;\n".encode("ascii"))
    if done.returncode != 0:  # psql's output may quote a statement: withheld (UNI-09)
        raise Failed(f"setting the passwords failed (psql exit {done.returncode})")
    return len(found)


def main(
    argv: Sequence[str] | None = None, run: Runner = run_command, chown: Chown = os.chown
) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap-db", description=__doc__)
    parser.add_argument("mode", choices=["prepare", "apply"])
    parser.add_argument("--env-file", type=Path, help="apply: host env/<env>.env")
    parser.add_argument("--compose-file", type=Path, help="apply: the host's compose.yml")
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    parser.add_argument("--compose-arg", action="append", default=[], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    host = Host(args.root, chown)
    try:
        if args.mode == "prepare":
            minted = prepare(host)
            done = f"minted {', '.join(minted) or 'no password file'}"
        else:
            if args.compose_file is None or args.env_file is None:
                raise Refused("apply needs --compose-file and --env-file")
            docker = shutil.which("docker") or "docker"
            compose = [docker, "compose", "-f", str(args.compose_file), *args.compose_arg]
            count = apply([*compose, "--env-file", str(args.env_file)], run, host)
            done = f"role set applied; {count} role passwords set from their files"
    except Refused as exc:
        print(f"bootstrap-db: refused, nothing changed: {exc}", file=sys.stderr)
        return 2
    except Failed as exc:
        print(f"bootstrap-db: failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"bootstrap-db: failed: {exc.strerror} {exc.filename}", file=sys.stderr)
        return 1
    print(f"bootstrap-db: {args.mode}: {done}", file=sys.stderr)
    return 0
