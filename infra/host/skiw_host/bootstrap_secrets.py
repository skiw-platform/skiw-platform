"""`bootstrap-secrets init` (spec §8.4 H4; runbook docs/runbooks/host-rebuild.md).

`restore` follows in M1d-2.

The run checks everything in memory first, then writes the escrow bundle, then installs the key
files; any failure after that removes every file the run wrote, so no key is installed without its
escrow and a failed run leaves an empty store. Messages name keys and paths, never values (UNI-09).
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import syslog
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from skiw_host import escrow
from skiw_host.secrets import APP_KEYS, OWNER

KEY_BYTES = 32  # app/config/env.py MIN_KEY_BYTES
FORMAT = "skiw-escrow-1"
Chown = Callable[[str, int, int], None]
Journal = Callable[[str], None]


class Refused(Exception):
    pass


class Host:
    def __init__(self, root: Path, chown: Chown) -> None:
        self.secrets = root / "etc/skiw/secrets"
        self.escrow = root / "srv/skiw/escrow"
        self.deploy_log = root / "var/log/skiw/deploy.log"  # [A] path shared with skiw-deploy (M1g)
        self.chown = chown


def to_journal(message: str) -> None:
    syslog.openlog("bootstrap-secrets")
    syslog.syslog(syslog.LOG_NOTICE, message)


def mint(version: int) -> str:
    return f"v{version}:{base64.b64encode(os.urandom(KEY_BYTES)).decode('ascii')}"


def sha256(line: str) -> str:
    return hashlib.sha256(line.encode("ascii")).hexdigest()


def refuse_if_used(host: Host) -> None:
    if host.secrets.exists() and any(host.secrets.iterdir()):
        raise Refused(f"{host.secrets} is not empty: init needs an empty store")


def bundle(keys: dict[str, list[str]], created: datetime) -> bytes:
    entries = {
        name: [{"line": x, "sha256": sha256(x)} for x in lines] for name, lines in keys.items()
    }
    return json.dumps({"format": FORMAT, "created": created.isoformat(), "keys": entries}).encode()


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


def install(host: Host, keys: dict[str, list[str]], to: list[str], age: Path) -> Path:
    created = datetime.now(UTC)
    for directory in (host.secrets, host.escrow):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        host.chown(str(directory), 0, 0)
    path = host.escrow / f"{created:%Y%m%dT%H%M%SZ}.bundle.age"
    escrow.encrypt(path, bundle(keys, created), to, age)
    written = [path]
    try:
        for name, lines in keys.items():
            text = "".join(f"{line}\n" for line in lines)
            written.append(write(host, host.secrets / name, text, OWNER[name]))
        fd = os.open(host.secrets, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except BaseException:
        for done in written:
            done.unlink(missing_ok=True)
        raise
    return path


def record(host: Host, journal: Journal, message: str) -> None:
    """One line to stderr, the journal and the deploy log; callers pass names only, no value."""
    line = f"{datetime.now(UTC).isoformat()} bootstrap-secrets: {message}"
    print(line, file=sys.stderr)
    journal(message)
    host.deploy_log.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    with host.deploy_log.open("a", encoding="utf-8") as log:
        log.write(f"{line}\n")


def main(
    argv: Sequence[str] | None = None,
    chown: Chown = os.chown,
    journal: Journal = to_journal,
) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap-secrets", description=__doc__)
    parser.add_argument("mode", choices=["init"])
    parser.add_argument("--env-file", type=Path, required=True, help="host env/<env>.env")
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    parser.add_argument("--age", type=Path, default=escrow.AGE, help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    host = Host(args.root, chown)
    try:
        to = escrow.recipients(args.env_file)
        refuse_if_used(host)
        keys = {name: [mint(1)] for name in APP_KEYS}
        path = install(host, keys, to, args.age)
    except (Refused, escrow.EscrowError) as exc:
        print(f"bootstrap-secrets: refused, nothing written: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(
            f"bootstrap-secrets: failed, nothing left: {exc.strerror} {exc.filename}",
            file=sys.stderr,
        )
        return 1
    record(host, journal, f"{args.mode}: {len(keys)} key files installed, escrow bundle {path}")
    return 0
