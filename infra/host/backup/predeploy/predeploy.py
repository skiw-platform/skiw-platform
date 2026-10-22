"""`predeploy`: the pre-migration dump (spec §8.4 H3 step 4, H6; plan §3 M1g; runbook restore.md).

skiw-deploy runs it as `docker compose --profile ops run --rm -T backup predeploy` (uid 10003, ops
network) when the new image has unapplied migrations. `pg_dump -Fc` as skiw_backup, without the data
of the guard key tables (when they exist). Every byte of the archive goes to `age` for the owner's
dump recipients (G5); the same bytes also go to a validator, `pg_restore -f /dev/null`, for as long
as it reads them.

What is checked, and what is not: the archive starts with the custom-format magic `PGDMP`; pg_dump
exits 0 (it wrote the whole archive); age exits 0 (it encrypted every byte it was given, and it was
given every byte); the validator exits 0. The validator reads the header and table of contents and
then, in archive order, every data block it turns into a script, decompressing each one; the script
goes to /dev/null. It never loads the data into a database, so a dump it accepts is readable, not
proven restorable. pg_restore may stop reading before the end of the stream; that is not a failure,
and its exit code, never its pipe, is the verdict.

Bounds: Python holds one 64 KiB copy chunk and one 1 MiB hash block; pg_restore holds one data
block; no copy of the archive goes to disk except the encrypted output itself.

Writes /srv/skiw/backups/predeploy/<UTC time>.dump.age (0400) and <name>.sha256 (0400), syncs both
files and the directory to disk, and only then prints exactly `predeploy <name> <sha256>`. On any
failure it removes what it wrote, prints one value-free line on stderr and exits 1. The password
reaches pg_dump only through a 0600 libpq password file in the container's /tmp (tmpfs), never argv,
environment or output. Stdlib only.
"""

import contextlib
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
from typing import IO, Protocol

OUT = Path("/srv/skiw/backups/predeploy")
SECRET = Path("/run/secrets/skiw_backup_password")
EXCLUDE = ("guard.tenant_mac_key", "guard.approval_mac_key", "guard.lookup_decoy_key")
RECIPIENT = re.compile(r"age1[0-9a-z]{58}")
DB_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")
ONE_LINE = re.compile(r"[\x21-\x7e]+")
PRIVATE = stat.S_IRUSR | stat.S_IWUSR  # 0600: the libpq password file
DUMP_MODE = stat.S_IRUSR  # 0400: the dump and its checksum, read by the owner's puller (M6)
MAGIC = b"PGDMP"  # the first bytes of every pg_dump custom-format archive
CHUNK = 1 << 16  # pipe copy
HASH_BLOCK = 1 << 20  # checksum read
PATH = "/usr/local/bin:/usr/lib/postgresql/17/bin:/usr/bin:/bin"
VALIDATE = ["pg_restore", "-f", "/dev/null"]


class Child(Protocol):
    """The part of subprocess.Popen this module uses."""

    @property
    def stdin(self) -> IO[bytes] | None: ...
    @property
    def stdout(self) -> IO[bytes] | None: ...
    def wait(self) -> int: ...
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...


# Popen's keyword arguments (stdin, stdout, stderr, env) are untyped `...`: the call sites below
# are the only ones and pass fixed values; the return type is checked.
Spawn = Callable[..., Child]


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


def pipe(child: Child, which: str) -> IO[bytes]:
    end = child.stdout if which == "stdout" else child.stdin
    if end is None:
        raise Stop(f"no {which} pipe")
    return end


def fan_out(source: IO[bytes], age: IO[bytes], check: IO[bytes]) -> None:
    """Copy the whole archive to age, and to the validator for as long as it reads.

    age must take every byte: a broken age pipe fails the dump. The validator may stop early,
    after success or failure alike; it is then left out and judged by its exit code.
    """
    head, validator = b"", check
    reading = True
    while chunk := source.read(CHUNK):
        head += chunk[: len(MAGIC) - len(head)]
        try:
            age.write(chunk)
        except BrokenPipeError:
            raise Stop("age stopped reading the dump") from None
        if reading:
            try:
                validator.write(chunk)
            except BrokenPipeError:
                reading = False
    try:
        age.close()
    except BrokenPipeError:
        raise Stop("age stopped reading the dump") from None
    with contextlib.suppress(BrokenPipeError):  # the pipe closes even when the flush fails
        validator.close()
    if head != MAGIC:
        raise Stop("the dump is not a pg_dump custom-format archive")


def write_dump(
    spawn: Spawn, scratch: Path, db: str, recipients: list[str], password: str, tmp: Path
) -> None:
    passfile = scratch / "pgpass"
    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, PRIVATE)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(f"db:5432:{db}:skiw_backup:{escaped}\n")
    dump_env = {"PATH": PATH, "PGPASSFILE": str(passfile), "PGCONNECT_TIMEOUT": "10"}
    excluded = [f"--exclude-table-data={table}" for table in EXCLUDE]  # no error when absent
    dump_argv = ["pg_dump", "-Fc", "--no-password", "-h", "db", "-U", "skiw_backup", "-d", db]
    age_argv = ["age", *(x for r in recipients for x in ("-r", r)), "-o", str(tmp)]
    quiet, piped, env = subprocess.DEVNULL, subprocess.PIPE, {"PATH": PATH}
    started: list[Child] = []  # tool output may quote data: never shown
    try:
        dump = spawn([*dump_argv, *excluded], stdout=piped, stderr=quiet, env=dump_env)
        started.append(dump)
        check = spawn(VALIDATE, stdin=piped, stdout=quiet, stderr=quiet, env=env)
        started.append(check)
        age = spawn(age_argv, stdin=piped, stdout=quiet, stderr=quiet, env=env)
        started.append(age)
        fan_out(pipe(dump, "stdout"), pipe(age, "stdin"), pipe(check, "stdin"))
        codes = {"pg_dump": dump.wait(), "pg_restore": check.wait(), "age": age.wait()}
    finally:
        for process in started:
            if process.poll() is None:
                process.kill()
                process.wait()
    if failed := [name for name, code in codes.items() if code != 0]:
        raise Stop(f"{', '.join(failed)} failed")


def seal(tmp: Path) -> str:
    """Hash the encrypted dump in bounded reads, make it 0400 and sync it to disk."""
    digest = hashlib.sha256()
    fd = os.open(tmp, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        while block := os.read(fd, HASH_BLOCK):
            digest.update(block)
        os.fchmod(fd, DUMP_MODE)
        os.fsync(fd)  # age closes its output without a sync
    finally:
        os.close(fd)
    return digest.hexdigest()


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    spawn: Spawn = subprocess.Popen,
    out: Path = OUT,
    secret: Path = SECRET,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    if list(sys.argv[1:] if argv is None else argv) != ["predeploy"]:
        print("predeploy: usage: predeploy", file=sys.stderr)
        return 2
    name = f"{now():%Y%m%dT%H%M%SZ}.dump.age"
    target, tmp, check = out / name, out / f".{name}.tmp", out / f"{name}.sha256"
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
            write_dump(spawn, Path(scratch), db, recipients, password, tmp)
        digest = seal(tmp)
        os.link(tmp, target)  # never replaces a file
        written.append(target)
        fd = os.open(check, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, DUMP_MODE)
        written.append(check)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(f"{digest}  {name}\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.unlink()
        sync_directory(out)  # the two new names and the removed temporary name
    except (Stop, OSError, UnicodeDecodeError) as exc:
        for path in written:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        detail = str(exc) if isinstance(exc, Stop) else type(exc).__name__
        print(f"predeploy: failed, nothing kept: {detail}", file=sys.stderr)
        return 1
    print(f"predeploy {name} {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
