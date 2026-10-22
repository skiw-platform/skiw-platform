"""`predeploy`: the pre-migration dump (spec §8.4 H3 step 4, H6; plan §3 M1g; runbook restore.md).

skiw-deploy runs it as `docker compose --profile ops run --rm -T backup predeploy` (uid 10003, ops
network) when the new image has unapplied migrations. `pg_dump -Fc` as skiw_backup, without the data
of the guard key tables (when they exist); the same stream goes to `pg_restore --list`, which must
read it whole, and to `age` for the owner's dump recipients (G5). Writes
/srv/skiw/backups/predeploy/<UTC time>.dump.age (0400) and <name>.sha256, then prints exactly
`predeploy <name> <sha256>`. On any failure it removes what it wrote, prints one value-free line on
stderr and exits 1. The password reaches pg_dump only through a 0600 libpq password file in the
container's /tmp (tmpfs), never argv, environment or output. Stdlib only.
"""

import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

OUT = Path("/srv/skiw/backups/predeploy")
SECRET = Path("/run/secrets/skiw_backup_password")
EXCLUDE = ("guard.tenant_mac_key", "guard.approval_mac_key", "guard.lookup_decoy_key")
RECIPIENT = re.compile(r"age1[0-9a-z]{58}")
DB_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")
ONE_LINE = re.compile(r"[\x21-\x7e]+")
PRIVATE = stat.S_IRUSR | stat.S_IWUSR  # 0600: the libpq password file
DUMP_MODE = stat.S_IRUSR  # 0400: the dump and its checksum, read by the owner's puller (M6)
CHUNK = 1 << 16
PATH = "/usr/local/bin:/usr/lib/postgresql/17/bin:/usr/bin:/bin"
Popen = Callable[..., Any]


class Stop(Exception):
    """A failure; the message is value-free."""


def settings(environ: Mapping[str, str]) -> tuple[list[str], str]:
    recipients = environ.get("SKIW_DUMP_RECIPIENTS", "").split()
    db = environ.get("SKIW_POSTGRES_DB", "")
    if not recipients or not all(RECIPIENT.fullmatch(r) for r in recipients):
        raise Stop("SKIW_DUMP_RECIPIENTS is empty or not age1... public recipients (G5)")
    if not DB_NAME.fullmatch(db):
        raise Stop("SKIW_POSTGRES_DB is empty or not a plain name")
    return recipients, db


def stream(dump: Any, readers: Sequence[IO[bytes]]) -> None:
    """Copy pg_dump's stdout to each reader; a reader that stops early fails the copy."""
    while chunk := dump.stdout.read(CHUNK):
        for reader in readers:
            reader.write(chunk)
    for reader in readers:
        reader.close()


def write_dump(
    popen: Popen, scratch: Path, db: str, recipients: list[str], password: str, tmp: Path
) -> None:
    passfile = scratch / "pgpass"
    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, PRIVATE)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(f"db:5432:{db}:skiw_backup:{escaped}\n")
    env = {"PATH": PATH, "PGPASSFILE": str(passfile), "PGCONNECT_TIMEOUT": "10"}
    excluded = [f"--exclude-table-data={table}" for table in EXCLUDE]  # no error when absent
    dump_argv = ["pg_dump", "-Fc", "--no-password", "-h", "db", "-U", "skiw_backup", "-d", db]
    age_argv = ["age", *(x for r in recipients for x in ("-r", r)), "-o", str(tmp)]
    quiet = subprocess.DEVNULL  # tool output may quote data: never shown
    listing = scratch / "list"
    started = []
    try:
        with listing.open("wb") as out:
            dump = popen([*dump_argv, *excluded], stdout=subprocess.PIPE, stderr=quiet, env=env)
            started.append(dump)
            check = popen(
                ["pg_restore", "--list"], stdin=subprocess.PIPE, stdout=out, stderr=quiet, env=env
            )
            started.append(check)
            age = popen(age_argv, stdin=subprocess.PIPE, stdout=quiet, stderr=quiet, env=env)
            started.append(age)
            stream(dump, [check.stdin, age.stdin])
            codes = {"pg_dump": dump.wait(), "pg_restore --list": check.wait(), "age": age.wait()}
    except BrokenPipeError:
        raise Stop("a reader of the dump stream stopped early") from None
    finally:
        for process in started:
            if process.poll() is None:
                process.kill()
                process.wait()
    if failed := [name for name, code in codes.items() if code != 0]:
        raise Stop(f"{', '.join(failed)} failed")
    if listing.stat().st_size == 0:
        raise Stop("pg_restore --list read no table of contents")


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    popen: Popen = subprocess.Popen,
    out: Path = OUT,
    secret: Path = SECRET,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    if list(sys.argv[1:] if argv is None else argv) != ["predeploy"]:
        print("predeploy: usage: predeploy", file=sys.stderr)
        return 2
    name = f"{now():%Y%m%dT%H%M%SZ}.dump.age"
    target, tmp = out / name, out / f".{name}.tmp"
    written: list[Path] = []
    try:
        recipients, db = settings(os.environ if environ is None else environ)
        password = secret.read_text("ascii").removesuffix("\n")
        if not ONE_LINE.fullmatch(password):
            raise Stop(f"{secret} is empty or not one printable line")
        if target.exists() or target.is_symlink():
            raise Stop(f"{target} exists")
        written.append(tmp)
        with tempfile.TemporaryDirectory() as scratch:  # 0700, in the tmpfs /tmp
            write_dump(popen, Path(scratch), db, recipients, password, tmp)
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        os.chmod(tmp, DUMP_MODE)
        os.link(tmp, target)  # never replaces a file
        written.append(target)
        check = out / f"{name}.sha256"
        fd = os.open(check, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, DUMP_MODE)
        written.append(check)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(f"{digest}  {name}\n")
        tmp.unlink()
    except (Stop, OSError, UnicodeDecodeError) as exc:
        for path in written:
            path.unlink(missing_ok=True)
        detail = str(exc) if isinstance(exc, Stop) else type(exc).__name__
        print(f"predeploy: failed, nothing kept: {detail}", file=sys.stderr)
        return 1
    print(f"predeploy {name} {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
