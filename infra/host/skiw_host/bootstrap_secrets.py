"""`bootstrap-secrets init|restore` (spec §8.4 H4; runbook docs/runbooks/host-rebuild.md).

Both modes check everything in memory first, then write the escrow bundle, then install the key
files (and, for restore, the `.restored` marker); any failure up to that commit point removes every
file the run wrote, so no key is installed without its escrow and a failed run leaves an empty
store. Messages name keys and paths, never values (UNI-09).
"""

import argparse
import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import re
import stat
import sys
import syslog
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from skiw_host import escrow
from skiw_host.secrets import APP_KEYS, OWNER

KEY_BYTES = 32  # app/config/env.py MIN_KEY_BYTES
KEY_LINE = re.compile(r"v([1-9][0-9]{0,5}):([A-Za-z0-9+/]+={0,2})")  # app/config/env.py KEY_LINE
FORMAT = "skiw-escrow-1"
MARKER = ".restored"
DIR_MODE = stat.S_IRWXU  # 0700: only root enters the secret and escrow directories
LOG_DIR_MODE = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP  # 0750
LOG_MODE = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP  # 0640
OTHERS_WRITE = stat.S_IWGRP | stat.S_IWOTH
Chown = Callable[[str, int, int], None]
Journal = Callable[[str], None]


class Refused(Exception):
    pass


class Host:
    def __init__(self, root: Path, chown: Chown) -> None:
        self.root = root
        self.secrets = root / "etc/skiw/secrets"
        self.escrow = root / "srv/skiw/escrow"
        self.deploy_log = root / "var/log/skiw/deploy.log"  # [A] path shared with skiw-deploy (M1g)
        self.chown = chown


def to_journal(message: str, ident: str = "bootstrap-secrets") -> None:
    syslog.openlog(ident)
    syslog.syslog(syslog.LOG_NOTICE, message)


def sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_chain(host: Host, directory: Path) -> None:
    """Make the directory entries durable: the directory itself and every ancestor up to the root,
    because `mkdir -p` may have just created them."""
    for path in (directory, *directory.parents):
        sync_dir(path)
        if path == host.root:
            break


def mint(version: int) -> str:
    return f"v{version}:{base64.b64encode(os.urandom(KEY_BYTES)).decode('ascii')}"


def version(line: str) -> int:
    return int(line[1 : line.index(":")])


def sha256(line: str) -> str:
    return hashlib.sha256(line.encode("ascii")).hexdigest()


def refuse_if_used(host: Host) -> None:
    if (host.secrets / MARKER).exists():
        raise Refused(f"{host.secrets / MARKER} exists: this host was already restored")
    if host.secrets.exists() and any(host.secrets.iterdir()):
        raise Refused(f"{host.secrets} is not empty: init and restore need an empty store")


def bundle(keys: dict[str, list[str]], created: datetime) -> bytes:
    entries = {
        name: [{"line": x, "sha256": sha256(x)} for x in lines] for name, lines in keys.items()
    }
    return json.dumps({"format": FORMAT, "created": created.isoformat(), "keys": entries}).encode()


def parse(raw: bytes, may_lack: set[str]) -> dict[str, list[str]]:
    """The decrypted bundle: every app key present (or allowed to lack), each version verified."""
    try:
        doc: object = json.loads(raw)
    except ValueError:
        raise Refused("stdin is not a decrypted escrow bundle") from None
    keys = doc.get("keys") if isinstance(doc, dict) and doc.get("format") == FORMAT else None
    if not isinstance(keys, dict):
        raise Refused("stdin is not a decrypted escrow bundle")
    if extra := set(keys) - set(APP_KEYS):
        raise Refused(f"the bundle holds {len(extra)} entries outside the app-key inventory")
    if missing := set(APP_KEYS) - set(keys) - may_lack:
        raise Refused(f"the bundle lacks {', '.join(sorted(missing))}")
    return {name: versions(name, entries) for name, entries in keys.items()}


def versions(name: str, entries: object) -> list[str]:
    """The verified lines of one key, oldest first; entry numbers, never lines, in messages."""
    if not isinstance(entries, list) or not entries:
        raise Refused(f"{name}: the bundle holds no version")
    lines: dict[int, str] = {}
    for number, entry in enumerate(entries, start=1):
        line, digest = (
            (entry.get("line"), entry.get("sha256")) if isinstance(entry, dict) else (0, 0)
        )
        match = KEY_LINE.fullmatch(line) if isinstance(line, str) else None
        if match is None or not isinstance(digest, str) or int(match[1]) in lines:
            raise Refused(f"{name}: version entry {number} is malformed or repeated")
        if not hmac.compare_digest(sha256(match[0]).encode(), digest.encode()):
            raise Refused(f"{name}: version entry {number} does not match its SHA-256")
        try:
            size = len(base64.b64decode(match[2], validate=True))
        except binascii.Error:
            size = 0
        if size < KEY_BYTES:
            raise Refused(f"{name}: version entry {number} is not {KEY_BYTES} bytes of base64")
        lines[int(match[1])] = match[0]
    return [lines[number] for number in sorted(lines)]


def write(host: Host, path: Path, text: str, uid: int) -> Path:
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o400)
        host.chown(str(tmp), uid, 0)
        os.link(tmp, path)  # unlike rename, never replaces an existing file
    finally:
        tmp.unlink(missing_ok=True)
    return path


def install(host: Host, keys: dict[str, list[str]], to: list[str], age: Path, mark: bool) -> Path:
    created = datetime.now(UTC)
    for directory in (host.secrets, host.escrow):
        directory.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
        os.chmod(directory, DIR_MODE)
        host.chown(str(directory), 0, 0)
    path = host.escrow / f"{created:%Y%m%dT%H%M%SZ}.bundle.age"
    escrow.encrypt(path, bundle(keys, created), to, age)
    written = [path]
    try:
        sync_chain(host, host.escrow)  # the bundle's name is on disk before any key is installed
        for name, lines in keys.items():
            text = "".join(f"{line}\n" for line in lines)
            written.append(write(host, host.secrets / name, text, OWNER[name]))
        if mark:  # last file before the commit point: a failed marker rolls the restore back
            written.append(write(host, host.secrets / MARKER, f"{created.isoformat()}\n", 0))
        sync_chain(host, host.secrets)
    except BaseException:
        for done in written:
            done.unlink(missing_ok=True)
        raise
    return path


def say(text: str) -> None:
    """One line to stderr, which may be gone: under the forced command it is the SSH channel, and a
    closed channel raises BrokenPipeError (Python ignores SIGPIPE). A lost line changes nothing: the
    journal and the deploy log are the record, and the exit code stays the one the run earned."""
    try:
        print(text, file=sys.stderr, flush=True)
    except (OSError, ValueError):  # ValueError: stderr already closed
        # The unwritten bytes stay in the old stream's buffer, and the interpreter's exit flush of
        # sys.stderr would fail again and turn any exit code into 120; this stream has none.
        sys.stderr = io.StringIO()


def record(host: Host, journal: Journal, message: str, prog: str = "bootstrap-secrets") -> None:
    """One line to the journal, the deploy log and then stderr; callers pass names only, no value.
    The durable copies come first, so a closed stderr (a dropped SSH session) never loses them."""
    line = f"{datetime.now(UTC).isoformat()} {prog}: {message}"
    try:
        append_log(host, journal, message, line)
    finally:
        say(line)


def append_log(host: Host, journal: Journal, message: str, line: str) -> None:
    journal(message)
    host.deploy_log.parent.mkdir(mode=LOG_DIR_MODE, parents=True, exist_ok=True)
    mine = os.geteuid()  # root on a host: the log and its directory must be ours, never writable
    info = host.deploy_log.parent.lstat()  # by others, and never a link a local user can aim
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != mine or info.st_mode & OTHERS_WRITE:
        raise PermissionError(f"{host.deploy_log.parent} is a link, not ours or writable by others")
    fd = os.open(host.deploy_log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, LOG_MODE)
    with os.fdopen(fd, "a", encoding="utf-8") as log:
        info = os.fstat(log.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != mine or info.st_mode & OTHERS_WRITE:
            raise PermissionError(f"{host.deploy_log} is not ours or is writable by others")
        log.write(f"{line}\n")


def main(
    argv: Sequence[str] | None = None,
    chown: Chown = os.chown,
    journal: Journal = to_journal,
    stdin: BinaryIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap-secrets", description=__doc__)
    parser.add_argument("mode", choices=["init", "restore"])
    parser.add_argument("--env-file", type=Path, required=True, help="host env/<env>.env")
    parser.add_argument(
        "--allow-new-key-version",
        action="append",
        default=[],
        metavar="NAME",
        help="restore only, owner decision: add one new newest version of this lost app key",
    )
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    parser.add_argument("--age", type=Path, default=escrow.AGE, help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    host, new = Host(args.root, chown), list(dict.fromkeys(args.allow_new_key_version))
    try:
        if (args.mode == "init" and new) or not set(new) <= set(APP_KEYS):
            raise Refused("--allow-new-key-version is for restore, with an app-key name")
        to = escrow.recipients(args.env_file)
        refuse_if_used(host)
        if args.mode == "init":
            keys = {name: [mint(1)] for name in APP_KEYS}
        else:
            keys = parse((stdin or sys.stdin.buffer).read(), set(new))
            for name in new:
                lines = keys.setdefault(name, [])
                lines.append(mint(max(map(version, lines), default=0) + 1))
        path = install(host, keys, to, args.age, mark=args.mode == "restore")
    except (Refused, escrow.EscrowError) as exc:
        say(f"bootstrap-secrets: refused, nothing written: {exc}")
        return 2
    except OSError as exc:
        say(f"bootstrap-secrets: failed, nothing left: {exc.strerror} {exc.filename}")
        return 1
    minted = [f"{name} v{version(keys[name][-1])}" for name in new]
    try:
        for line in minted:
            record(host, journal, f"restore minted {line} (--allow-new-key-version)")
        record(host, journal, f"{args.mode}: {len(keys)} key files installed, escrow bundle {path}")
    except OSError as exc:
        say(  # the run is committed here: report it, never roll back or retry
            "bootstrap-secrets: the key files and the escrow bundle are installed"
            f"{' with the .restored marker' if args.mode == 'restore' else ''}, but writing "
            f"the log failed: {exc.strerror} {exc.filename}. "
            f"{''.join(f'Minted by override: {line}. ' for line in minted)}"
            f"Do not run {args.mode} again; see the runbook."
        )
        return 3
    return 0
