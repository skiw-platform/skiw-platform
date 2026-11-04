"""`skiw-deploy --key <role> deploy <digest> [<run-id>]` and `rollback <digest>` (spec §8.4 H3;
runbooks deploy.md, rollback.md).

Run as root through one sudo rule, reached only from the forced command `skiw-deploy-ssh`. Steps:
(3) check the digest, the key role and host config, take the deploy lock; production: staging must
report that digest running with checks=passed (G11 (b), `skiw-staging-status` over SSH); pull by
digest with the GHCR read token on stdin; (4) `migrate --plan`, and when it is not empty the
pre-migration dump; (5) the host's applied-contract list grows by the image's contract migrations
(before `migrate`, which can apply some and then fail), then `migrate`, then
`check_tenancy_schema` (plan M4c-6b; a failure leaves the migrations applied and the old digest
serving: the fix is a forward migration, runbook host-rebuild.md); (6) switch web and worker
(SKIW_IMAGE in the state file, `up -d`); (7) `/readyz` 200 and the worker registered, else switch
back and alert (migrations are never reversed); staging then writes its status line (G12), after
removing the old one before the switch; (9) production appends one line to the append-only
accepted-digest record; (11) one value-free line to the journal and the deploy log.
`rollback` (production key only): a digest from the accepted record, no staging check, no
`migrate`, refused across an applied contract migration the target does not ship; then 6-7.
Every tool call is bounded (subprocess timeout) except `migrate`: killing its client would leave
the migration running in its container while the lock is released. Every file written is synced,
with its directory, before success is reported. Tool output and secret values are never printed.
Exit 0 done, 1 failed (the old digest still serves), 2 refused (nothing changed), 3 done but the
accepted-digest or log line failed. The journal and deploy-log line is written before the stderr
copy; a stderr that is gone (a dropped SSH session) changes neither the line nor the exit code.
"""

import argparse
import fcntl
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import syslog
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from skiw_host import apply
from skiw_host.bootstrap_db import ONE_LINE, Failed, Runner, psql_script, run_command, settings
from skiw_host.bootstrap_secrets import (
    Chown,
    Host,
    Journal,
    Refused,
    record,
    say,
    sync_dir,
    to_journal,
)
from skiw_host.hardening import SECRET_MODE, SECRETS, Bad, Owner, read_file, stat_owner

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
RUN_ID = re.compile(r"[1-9][0-9]{0,19}")
REPOSITORY = re.compile(r"ghcr\.io/([a-z0-9-]+)/[a-z0-9][a-z0-9._-]*")
HOSTNAME = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
# What `skiw-deploy-ssh` accepts in SSH_ORIGINAL_COMMAND; nothing else runs.
SSH_COMMAND = re.compile(
    r"deploy sha256:[0-9a-f]{64}(?: [1-9][0-9]{0,19})?|rollback sha256:[0-9a-f]{64}"
)
ROLES = ("production", "staging")
SBIN = "/usr/local/sbin/skiw-deploy"
LOCK = "run/skiw-deploy.lock"
LOCK_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0600
TOKEN_FILE = f"{SECRETS}/ghcr_read_token"
HEARTBEAT_S = 10  # procrastinate 3.10 Worker.update_heartbeat_interval (default)
POLL_S = 2
SWITCH_S = 300  # bound on one `docker compose up -d` or `stop` (switch and recovery)
TOOL_S = 120  # bound on a short tool call: login, inspect, `migrate --plan`, labels, lsattr, chattr
PULL_S = 900  # bound on `docker pull`
TimedRunner = Callable[[list[str], bytes, float], subprocess.CompletedProcess[bytes]]
# The pre-migration dump: the `backup` service (infra/host/backup/predeploy) prints exactly this one
# line when the encrypted dump and its checksum are written; anything else stops before `migrate`.
# The fixed container name lets a timed-out run be removed (killing the client leaves it running).
DUMP_NAME = "skiw-predeploy"
DUMP = ["--profile", "ops", "run", "--rm", "--name", DUMP_NAME, "-T", "backup", "predeploy"]
DUMP_DONE = re.compile(r"predeploy [0-9]{8}T[0-9]{6}Z\.dump\.age [0-9a-f]{64}")
PLAN = ["--profile", "deploy", "run", "--rm", "-T", "migrate", "python", "app/manage.py", "migrate"]
WORKERS = "SELECT coalesce(max(id), 0) FROM procrastinate_workers;"
# Server-side bounds, so a statement stuck behind a lock is cancelled by the database too, not only
# its `docker compose exec` client by the subprocess timeout.
BOUND = "SET statement_timeout = {0}; SET lock_timeout = {0};"
LIVE = (
    "SELECT count(*) FROM procrastinate_workers"
    " WHERE id > {} AND last_heartbeat > now() - interval '{} seconds';"
)
JOURNAL: Journal = partial(to_journal, ident="skiw-deploy")
# Plan M4c-6b: the tenancy schema check after `migrate`, before the switch (a short tool call).
CHECK = ["--profile", "deploy", "run", "--rm", "-T", "migrate"]
CHECK += ["python", "app/manage.py", "check_tenancy_schema"]
LABELS = ["--profile", "deploy", "run", "--rm", "-T", "migrate"]
LABELS += ["python", "app/manage.py", "migration_labels"]
MIGRATION = re.compile(r"[a-z_][a-z0-9_]{0,99}\.[A-Za-z0-9_]{1,200}")
COMMIT = re.compile(r"[0-9a-f]{40}")
HEAD_LABEL, COMMIT_LABEL = "skiw.migration-head", "org.opencontainers.image.revision"
CONTRACTS_LABEL = "skiw.contract-migrations"  # set by CI (skiw_host.labels); not read here
ACCEPTED = "var/lib/skiw/accepted-digests"  # production only, append-only (chattr +a)
APPLIED = "var/lib/skiw/applied-contracts"  # contract migrations whose `migrate` succeeded here
STATUS = "var/lib/skiw/staging-status"  # staging only: the last deploy's check line (G12)
STATUS_KEY_FILE = f"{SECRETS}/staging_status_key"
STATUS_S = 30  # bound on the staging status SSH call
TIME = r"[0-9]{8}T[0-9]{6}Z"
CHECK_LINE = re.compile(
    rf"digest=(sha256:[0-9a-f]{{64}}) checked=({TIME}) readyz=200 worker=registered"
    r" head=(match|differs|unlabelled) checks=(passed|failed)"
)
STATUS_LINE = re.compile(rf"{CHECK_LINE.pattern} running=(yes|no)")
NAMES = r"(?:[a-z_][a-z0-9_]*\.[A-Za-z0-9_]+(?:,[a-z_][a-z0-9_]*\.[A-Za-z0-9_]+)*)"
ACCEPTED_LINE = re.compile(  # group 1 the digest, group 2 the commit
    rf"digest=(sha256:[0-9a-f]{{64}}) commit=([0-9a-f]{{40}}) run=[1-9][0-9]{{0,19}}"
    rf" staging_checked={TIME} deployed={TIME} readyz=200 head=({NAMES}|-)"
    rf" contracts=({NAMES}|-) key=SHA256:[A-Za-z0-9+/]{{43}}"
)
STAGING = re.compile(r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}):([1-9][0-9]{0,4})")
HOST_KEY = re.compile(r"ssh-ed25519 [A-Za-z0-9+/]{68}")
FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
HOST_ALIAS = "skiw-staging"  # the known_hosts name of the pinned key, whatever the port
LSATTR_FLAGS = re.compile(r"[a-zA-Z-]{1,64}")


class RecordFailed(Exception):
    """The deploy is done, but its accepted-digest line could not be written (exit 3)."""


class TimedOut(Failed):
    """A bounded tool call passed its bound; subprocess.run killed the client."""


@dataclass(frozen=True)
class Config:
    environment: str
    repository: str
    hostname: str
    timeout: int
    dump_timeout: int = 0  # SKIW_DEPLOY_DUMP_TIMEOUT_S
    staging: tuple[str, str] = ("", "")  # production: staging's host and SSH port
    host_key: str = ""  # production: staging's ed25519 host key
    fingerprint: str = ""  # production: the owner's deploy key (G6)


def now() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def to_alert(message: str) -> None:  # picked up by the health alert sender (M1j)
    syslog.openlog("skiw-deploy")
    syslog.syslog(syslog.LOG_ALERT, message)


def run_timed(argv: list[str], stdin: bytes, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """subprocess.run kills the child and raises TimeoutExpired when the bound passes."""
    return subprocess.run(argv, input=stdin, capture_output=True, check=False, timeout=timeout)  # noqa: S603 - argv built here, no shell


class Deploy:
    def __init__(self, root: Path, run: Runner, owner: Owner, chown: Chown) -> None:
        self.root, self.run, self.owner, self.chown = root, run, owner, chown
        self.timed: TimedRunner = run_timed  # every tool call but `migrate` (module docstring)
        self.clock: Callable[[], float] = time.monotonic
        self.sleep: Callable[[float], None] = time.sleep

    def read(self, rel: str, mode: int | None = None) -> bytes:
        """A root-owned file reached through no link and no writable directory, never a link."""
        try:
            apply.untrusted(self.root, [rel], lambda p: self.owner(p, p.lstat()))
            return read_file(self.root / rel, self.owner, 0, mode)
        except Bad as exc:
            raise Refused(str(exc)) from None
        except OSError as exc:  # missing, or a link (ELOOP)
            raise Refused(f"/{rel}: {exc.strerror}") from None

    def ok(
        self, argv: list[str], label: str, stdin: bytes = b"", bound: float | None = TOOL_S
    ) -> str:
        """Exit 0 or Failed; `bound` None only for `migrate` (module docstring)."""
        try:
            done = self.run(argv, stdin) if bound is None else self.timed(argv, stdin, bound)
        except subprocess.TimeoutExpired:
            raise TimedOut(f"`{label}` timed out") from None
        if done.returncode != 0:  # the output may quote config or data: withheld
            raise Failed(f"`{label}` exited {done.returncode}")
        return done.stdout.decode("utf-8")

    def compose(self, image: str) -> list[str]:
        """The new or old image wins over the state file (Compose: environment before env file)."""
        files = ["-f", str(self.root / apply.COMPOSE), "--env-file", str(self.root / apply.ENV)]
        return ["env", f"SKIW_IMAGE={image}", "docker", "compose", *files]


def host_config(d: Deploy, key: str, action: str) -> Config:
    values = settings(d.root / apply.ENV, d.read(apply.ENV).decode("utf-8"))
    environment = values.get("SKIW_ENVIRONMENT", "")
    if environment not in ROLES:
        raise Refused("SKIW_ENVIRONMENT in the host env file is not production or staging")
    if key != environment:
        raise Refused(f"the {key} deploy key is refused on {environment}")
    if action == "rollback" and key != "production":
        raise Refused("rollback takes the owner's production key only")
    repository, hostname = values.get("SKIW_IMAGE_REPOSITORY", ""), values.get("SKIW_HOSTNAME", "")
    timeout = values.get("SKIW_DEPLOY_HEALTH_TIMEOUT_S", "")
    dump_timeout = values.get("SKIW_DEPLOY_DUMP_TIMEOUT_S", "")
    if not REPOSITORY.fullmatch(repository):
        raise Refused("SKIW_IMAGE_REPOSITORY is not a ghcr.io/<owner>/<name> repository")
    if not HOSTNAME.fullmatch(hostname) or not re.fullmatch(r"[1-9][0-9]{0,2}", timeout):
        raise Refused("SKIW_HOSTNAME or SKIW_DEPLOY_HEALTH_TIMEOUT_S is empty or invalid")
    if not re.fullmatch(r"[1-9][0-9]{0,4}", dump_timeout):
        raise Refused("SKIW_DEPLOY_DUMP_TIMEOUT_S is empty or invalid")
    d.read(apply.COMPOSE)  # Compose reads it as root: root-owned, never through a link
    config = Config(environment, repository, hostname, int(timeout), int(dump_timeout))
    if environment == "staging":
        return config
    staging = STAGING.fullmatch(values.get("SKIW_STAGING_SSH", ""))
    host_key, fingerprint = (
        values.get("SKIW_STAGING_HOST_KEY", ""),
        values.get("SKIW_DEPLOY_KEY_FINGERPRINT", ""),
    )
    if not staging or int(staging[2]) > 65535 or not HOST_KEY.fullmatch(host_key):
        raise Refused("SKIW_STAGING_SSH (host:port) or SKIW_STAGING_HOST_KEY is empty or invalid")
    if not FINGERPRINT.fullmatch(fingerprint):
        raise Refused("SKIW_DEPLOY_KEY_FINGERPRINT is not the owner's key fingerprint (G6)")
    return replace(
        config, staging=(staging[1], staging[2]), host_key=host_key, fingerprint=fingerprint
    )


def lock(d: Deploy) -> int:
    apply.untrusted(d.root, [LOCK, apply.STATE], lambda p: d.owner(p, p.lstat()))
    try:
        fd = os.open(
            d.root / LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, LOCK_MODE
        )
    except OSError as exc:  # a link planted at the lock path: ELOOP
        raise Refused(f"/{LOCK} cannot be opened safely ({exc.strerror})") from None
    info = os.fstat(fd)
    try:
        if not stat.S_ISREG(info.st_mode) or d.owner(d.root / LOCK, info) != apply.ROOT:
            raise Refused(f"/{LOCK} is not a regular file owned by root")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Refused("another skiw-deploy holds the deploy lock") from None
    except BaseException:
        os.close(fd)
        raise
    return fd


def current(d: Deploy, repository: str) -> tuple[str, bytes] | None:
    """The running image and the state file's exact content, or None: no deploy has succeeded
    (a failed first deploy removes the state it wrote)."""
    path = d.root / apply.STATE
    if not path.exists() and not path.is_symlink():
        return None
    data = d.read(apply.STATE, apply.CONFIG)
    image = settings(path, data.decode("utf-8")).get("SKIW_IMAGE", "")
    if image.partition("@")[0] != repository or not DIGEST.fullmatch(image.partition("@")[2]):
        raise Refused(f"/{apply.STATE} does not name an image of the fixed repository")
    return image, data


def pull(d: Deploy, repository: str, image: str) -> None:
    value = d.read(TOKEN_FILE, SECRET_MODE).decode("ascii").removesuffix("\n")
    if not ONE_LINE.fullmatch(value):
        raise Refused(f"/{TOKEN_FILE} is empty or not one printable line")
    user = REPOSITORY.fullmatch(repository)[1]  # type: ignore[index]  # checked in host_config
    config = tempfile.mkdtemp(prefix="skiw-deploy-", dir=d.root / "run")  # 0700, removed below
    try:
        docker = ["docker", "--config", config]
        login = [*docker, "login", "ghcr.io", "--username", user, "--password-stdin"]
        d.ok(login, "docker login", f"{value}\n".encode())  # the token only ever on stdin
        d.ok([*docker, "pull", image], "docker pull", bound=PULL_S)
    finally:
        shutil.rmtree(config, ignore_errors=True)
    found = json.loads(
        d.ok(
            ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image],
            "docker image inspect",
        )
    )
    if not isinstance(found, list) or image not in found:
        raise Failed("the pulled image does not carry the requested digest")


def pending(d: Deploy, image: str) -> bool:
    lines = [
        x.strip()
        for x in d.ok([*d.compose(image), *PLAN, "--plan"], "migrate --plan").splitlines()
        if x.strip()
    ]
    if lines == ["Planned operations:", "No planned migration operations."]:
        return False
    if lines[:1] == ["Planned operations:"] and len(lines) > 1:
        return True
    raise Failed("`migrate --plan` printed something that is not a plan")


def image_labels(d: Deploy, image: str) -> dict[str, str]:
    argv = ["docker", "image", "inspect", "--format", "{{json .Config.Labels}}", image]
    found = json.loads(d.ok(argv, "docker image inspect"))
    if found is None:
        return {}
    if not isinstance(found, dict) or not all(isinstance(v, str) for v in found.values()):
        raise Failed("docker image inspect gave labels that are not strings")
    return found


def migration_labels(d: Deploy, image: str) -> dict[str, list[str]]:
    """`migration_labels` in the image itself (no database): head, contracts, migrations."""
    return parse_migration_labels(d.ok([*d.compose(image), *LABELS], "migration_labels"))


def parse_migration_labels(text: str) -> dict[str, list[str]]:
    """The one JSON object `migration_labels` prints, checked (also for CI: skiw_host.labels)."""
    found = json.loads(text)
    keys = ("head", "contracts", "migrations")
    if not isinstance(found, dict) or sorted(found) != sorted(keys):
        raise Failed("migration_labels printed something else")
    for key in keys:
        names = found[key]
        if not isinstance(names, list) or not all(
            isinstance(n, str) and MIGRATION.fullmatch(n) for n in names
        ):
            raise Failed("migration_labels printed something else")
    if not set(found["head"]) | set(found["contracts"]) <= set(found["migrations"]):
        raise Failed("migration_labels printed a head or contract it does not ship")
    return found


def read_lines(d: Deploy, rel: str, line: re.Pattern[str]) -> list[str]:
    """Every line of a root-owned 0644 file (missing: none); one malformed line refuses."""
    path = d.root / rel
    if not path.exists() and not path.is_symlink():
        return []
    data = d.read(rel, apply.CONFIG)
    lines = data.decode("ascii", "replace").splitlines()
    whole = not data or data.endswith(b"\n")  # a cut last line is never read as a shorter one
    if not whole or not data.isascii() or not all(line.fullmatch(x) for x in lines):
        raise Refused(f"/{rel} holds a line that is not in its format")  # never shown
    return lines


def staging_check(d: Deploy, cfg: Config, digest: str) -> str:
    """G11 (b): staging's forced command prints its status line; it must be that one line, naming
    this digest, running, head=match and checks=passed. Returns staging's check time."""
    key = d.read(STATUS_KEY_FILE, SECRET_MODE)  # root, 0400, no link: ssh reads the same file
    if not key.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----"):
        raise Refused(f"/{STATUS_KEY_FILE} is not an OpenSSH private key")
    host, port = cfg.staging
    scratch = tempfile.mkdtemp(prefix="skiw-status-", dir=d.root / "run")  # 0700
    try:
        known = Path(scratch) / "known_hosts"
        known.write_text(f"{HOST_ALIAS} {cfg.host_key}\n", encoding="ascii")
        options = ["IdentitiesOnly=yes", "BatchMode=yes", "StrictHostKeyChecking=yes"]
        options += [f"UserKnownHostsFile={known}", "GlobalKnownHostsFile=/dev/null"]
        options += [f"HostKeyAlias={HOST_ALIAS}", "HostKeyAlgorithms=ssh-ed25519"]
        options += ["ConnectTimeout=10", "RequestTTY=no"]
        ssh = ["ssh", "-F", "/dev/null", "-i", str(d.root / STATUS_KEY_FILE), "-p", port]
        ssh += [x for o in options for x in ("-o", o)] + [f"skiw-deploy@{host}", "status"]
        try:
            done = d.timed(ssh, b"", STATUS_S)
        except subprocess.TimeoutExpired:
            raise Refused("the staging status call timed out") from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    out = done.stdout.removesuffix(b"\n")  # exactly one line: no banner, no second line
    text = out.decode("ascii") if out.isascii() else ""
    found = STATUS_LINE.fullmatch(text) if done.returncode == 0 else None
    if not found:
        raise Refused("staging did not answer with one status line")  # its output is not shown
    if found[1] != digest or found.group(3, 4, 5) != ("match", "passed", "yes"):
        raise Refused("staging does not report this digest running with checks=passed")
    return found[2]


def lsattr_append_only(d: Deploy, path: Path) -> bool:
    """`lsattr -d` printed exactly `<flags> <path>` and the flags hold `a`; anything else: no."""
    done = d.timed(["lsattr", "-d", str(path)], b"", TOOL_S)
    flags, _, rest = done.stdout.decode("ascii", "replace").partition(" ")
    shape = rest == f"{path}\n" and LSATTR_FLAGS.fullmatch(flags) is not None
    return done.returncode == 0 and shape and "a" in flags


def ensure_record(d: Deploy) -> None:
    """The accepted-digest record exists, root-owned 0644, append-only (`chattr +a`, checked with
    `lsattr`) and every line in its format. A new one is synced with its directory."""
    apply.untrusted(d.root, [ACCEPTED], lambda p: d.owner(p, p.lstat()))
    path = d.root / ACCEPTED
    if not path.exists() and not path.is_symlink():
        apply.make_directories(d.root, Path(ACCEPTED).parent, d.chown)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(path, flags, apply.CONFIG)
        try:
            os.fchmod(fd, apply.CONFIG)  # exact 0644 under any umask
            d.chown(str(path), *apply.ROOT)  # just made with O_EXCL in a root-only directory
            os.fsync(fd)
        finally:
            os.close(fd)
        sync_dir(path.parent)
    read_lines(d, ACCEPTED, ACCEPTED_LINE)  # root 0644, no link, every line whole and valid
    try:
        if lsattr_append_only(d, path):
            return
        done = d.timed(["chattr", "+a", str(path)], b"", TOOL_S)
        if done.returncode == 0 and lsattr_append_only(d, path):
            return
    except subprocess.TimeoutExpired:
        pass
    raise Refused(f"/{ACCEPTED} cannot be made append-only (chattr +a)")


def append_record(d: Deploy, line: str) -> None:
    """One whole line to the root 0644 record, synced with its directory before success."""
    try:
        fd = os.open(d.root / ACCEPTED, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "ab") as handle:
            info = os.fstat(handle.fileno())
            ours = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            if not ours or d.owner(d.root / ACCEPTED, info) != apply.ROOT:
                raise RecordFailed(f"/{ACCEPTED} is not a regular file owned by root")
            if stat.S_IMODE(info.st_mode) != apply.CONFIG:
                raise RecordFailed(f"/{ACCEPTED} has mode {stat.S_IMODE(info.st_mode):04o}")
            handle.write(f"{line}\n".encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        sync_dir((d.root / ACCEPTED).parent)
    except OSError as exc:
        raise RecordFailed(f"/{ACCEPTED}: {exc.strerror}") from None


def workers(d: Deploy, image: str, query: str, bound: float) -> int:
    """One count, bounded by `bound` seconds on the client and in the database."""
    psql = [*d.compose(image), "exec", "-T", "db", "sh", "-c", psql_script()]
    limits = BOUND.format(max(1, int(bound * 1000)))
    script = f"\\pset format unaligned\n\\pset tuples_only on\n{limits}\n{query}\n"
    out = d.ok(psql, "psql", script.encode(), bound).strip()
    if not re.fullmatch(r"[0-9]{1,19}", out):
        raise Failed("psql did not print one count")
    return int(out)


def write_state(d: Deploy, data: bytes | None, rel: str = apply.STATE) -> None:
    """Replace a root-owned 0644 file under /var/lib/skiw atomically with `data`, or remove it; the
    file and the directory entry are synced before it returns."""
    try:  # checked before the pull too; a change since then fails here
        apply.untrusted(d.root, [rel], lambda p: d.owner(p, p.lstat()))
        apply.make_directories(d.root, Path(rel).parent, d.chown)
    except Refused as exc:
        raise Failed(str(exc)) from None
    target = d.root / rel
    if data is None:
        target.unlink(missing_ok=True)
        sync_dir(target.parent)
        return
    tmp = d.root / f"{rel}.skiw-new"
    tmp.unlink(missing_ok=True)  # a leftover of a stopped run, in a root-only directory
    fd = os.open(
        tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, apply.CONFIG
    )
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(handle.fileno(), apply.CONFIG)  # exact 0644 under any umask
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    d.chown(str(tmp), *apply.ROOT)  # made with O_EXCL in a root-only directory
    os.replace(tmp, target)
    sync_dir(target.parent)


def switch(d: Deploy, image: str) -> None:
    write_state(d, f"SKIW_IMAGE={image}\n".encode("ascii"))
    d.ok([*d.compose(image), "up", "-d"], "docker compose up", bound=SWITCH_S)


def within(d: Deploy, limit: float, probe: Callable[[float], bool]) -> bool:
    """Poll `probe(seconds left)` until it passes; a result that arrives after the deadline is
    rejected, and each probe is itself bounded by the time left."""
    deadline = d.clock() + limit
    while (left := deadline - d.clock()) > 0:
        passed = probe(left)
        if d.clock() > deadline:
            return False
        if passed:
            return True
        d.sleep(min(POLL_S, max(0.0, deadline - d.clock())))
    return False


def healthy(d: Deploy, image: str, hostname: str, timeout: int, floor: int) -> bool:
    """/readyz 200 through Caddy within the timeout, then a worker with an id above `floor` and a
    fresh heartbeat within two heartbeat intervals. A timeout or error raises (not healthy)."""

    def ready(left: float) -> bool:  # curl exits non-zero (and writes 000) without a response
        curl = ["curl", "--silent", "--output", "/dev/null", "--write-out", "%{http_code}"]
        curl += ["--max-time", str(max(1, min(5, math.floor(left))))]
        curl += ["--resolve", f"{hostname}:443:127.0.0.1", f"https://{hostname}/readyz"]
        done = d.timed(curl, b"", left)
        return done.returncode == 0 and done.stdout == b"200"

    def registered(left: float) -> bool:
        return workers(d, image, LIVE.format(floor, 2 * HEARTBEAT_S), left) > 0

    return within(d, timeout, ready) and within(d, 2 * HEARTBEAT_S, registered)


def pre_migration_dump(d: Deploy, image: str, bound: int) -> None:
    """H3 step 4, bounded by SKIW_DEPLOY_DUMP_TIMEOUT_S. On a timeout the dump container is removed:
    killing the `compose run` client alone would leave pg_dump running after the deploy stopped."""
    try:
        out = d.ok([*d.compose(image), *DUMP], "pre-migration dump", bound=bound)
    except TimedOut:
        try:
            d.ok(["docker", "rm", "--force", DUMP_NAME], "docker rm")
            left = "its container removed"
        except Failed:
            left = f"its container {DUMP_NAME} may still run: docker rm --force {DUMP_NAME}"
        raise Failed(f"the pre-migration dump timed out; {left}") from None
    if not DUMP_DONE.fullmatch(out.strip()):
        raise Failed("the pre-migration dump did not report a written dump")


def deploy(  # the H3 steps in order, one recovery boundary
    d: Deploy, alert: Journal, cfg: Config, digest: str, run_id: str, rollback: bool
) -> str:
    image = f"{cfg.repository}@{digest}"
    found = current(d, cfg.repository)
    previous, prior = found if found else (None, None)
    production = cfg.environment == "production"
    commits: set[str] = set()  # rollback: the commits the record holds for this digest
    if rollback:  # a digest this host accepted before (spec H3 step 10)
        for line in read_lines(d, ACCEPTED, ACCEPTED_LINE):
            fields = ACCEPTED_LINE.fullmatch(line)
            if fields and fields[1] == digest:  # read_lines matched every line already
                commits.add(fields[2])
        if not commits:
            raise Refused("the digest is not in the accepted-digest record")
    elif production:
        ensure_record(d)
        if not run_id:
            raise Refused("a production deploy needs the green main CI run id")
        checked = staging_check(d, cfg, digest)
    applied = set(read_lines(d, APPLIED, MIGRATION))
    pull(d, cfg.repository, image)
    labels = image_labels(d, image)
    names = migration_labels(d, image)
    if production and not rollback and not COMMIT.fullmatch(labels.get(COMMIT_LABEL, "")):
        raise Refused(f"the image has no commit label {COMMIT_LABEL}")
    # A deploy of an older digest is a rollback too: neither may cross an applied contract.
    if crossing := applied - set(names["migrations"]):
        raise Refused(f"{len(crossing)} applied contract migrations are not in the target")
    if rollback:
        if labels.get(COMMIT_LABEL) not in commits:  # the record and the image must agree
            raise Refused("the image's commit label is not the one the accepted record holds")
    else:
        if pending(d, image):
            pre_migration_dump(d, image, cfg.dump_timeout)
        # Recorded before `migrate`: it may apply a contract migration and then fail on a later
        # one. A list that names a contract that was not applied only refuses more rollbacks.
        union = sorted(applied | set(names["contracts"]))
        write_state(d, "".join(f"{n}\n" for n in union).encode("ascii"), APPLIED)
        d.ok([*d.compose(image), *PLAN], "migrate", bound=None)  # old containers serve on
        d.ok([*d.compose(image), *CHECK], "check_tenancy_schema")  # a fail: old ones serve on
    if not production:  # G12: the old status line goes before the switch; a failed deploy has none
        write_state(d, None, STATUS)
    # Same digest: Compose keeps the running worker, so its fresh heartbeat is the proof; a new
    # digest recreates the worker, which must register above the ids that existed before.
    floor = 0 if previous == image else workers(d, image, WORKERS, 2 * HEARTBEAT_S)
    was = (previous or "none").rpartition("@")[2]
    step = "switch"
    try:  # from the state replacement on, every failure goes through the recovery below
        switch(d, image)
        step = "health check"
        if healthy(d, image, cfg.hostname, cfg.timeout, floor):
            done = f"{'rolled back' if rollback else 'deployed'}; previous {was}"
            if rollback:
                return done
            if not production:  # G12: /readyz through Caddy and the worker passed above
                step = "staging status line"
                head = ",".join(names["head"])
                label = labels.get(HEAD_LABEL)
                match = "unlabelled" if label is None else "match" if label == head else "differs"
                result = "passed" if match == "match" else "failed"
                line = f"digest={digest} checked={now()} readyz=200 worker=registered"
                write_state(d, f"{line} head={match} checks={result}\n".encode("ascii"), STATUS)
                return f"{done}; staging checks {result}"
            record = f"digest={digest} commit={labels[COMMIT_LABEL]} run={run_id}"
            record += f" staging_checked={checked} deployed={now()} readyz=200"
            record += f" head={','.join(names['head']) or '-'}"
            record += f" contracts={','.join(names['contracts']) or '-'} key={cfg.fingerprint}"
            try:
                append_record(d, record)
            except RecordFailed as exc:  # the line holds checked values only, no tool output
                alert(f"deploy {digest} is running but its accepted-digest line failed")
                failed = f"{done}; but the accepted-digest line failed ({exc}); line: {record}"
                raise RecordFailed(failed) from None
            return f"{done}; accepted"
    except RecordFailed:
        raise
    except Exception:  # noqa: S110 - a failed or unreadable step: recover below
        pass
    try:  # each command bounded by SWITCH_S; migrations are never reversed
        if previous is None:
            try:
                d.ok([*d.compose(image), "stop", "web", "worker"], "compose stop", bound=SWITCH_S)
            finally:
                write_state(d, None)  # a failed first image is never a later switch-back target
            back = "no previous digest: web and worker stopped"
        else:
            write_state(d, prior)
            d.ok([*d.compose(previous), "up", "-d"], "docker compose up", bound=SWITCH_S)
            back = f"switched back to {was}"
        alert(f"deploy {digest} failed its {step}; {back}")
    except Exception:  # reported and alerted, never hidden
        back = f"RECOVERY FAILED, switching back to {was}: see docs/runbooks/deploy.md"
        alert(f"deploy {digest} failed its {step}; {back}")
    raise Failed(f"the {step} failed; {back}; migrations were not reversed")


def main(
    argv: Sequence[str] | None = None,
    run: Runner = run_command,
    owner: Owner = stat_owner,
    chown: Chown = os.chown,
    journal: Journal = JOURNAL,
    alert: Journal = to_alert,
    d: Deploy | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="skiw-deploy", description=__doc__)
    parser.add_argument("--key", choices=ROLES, required=True, help="from authorized_keys")
    parser.add_argument("action", choices=["deploy", "rollback"])
    parser.add_argument("digest")
    parser.add_argument("run_id", nargs="?", default="")
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    d = d or Deploy(args.root, run, owner, chown)
    what = f"{args.action} key {args.key}"  # argparse choices; the rest only once it is checked
    code, fd = 1, -1
    try:
        if args.root == Path("/") and os.geteuid() != 0:
            raise Refused("run it as root")
        if not DIGEST.fullmatch(args.digest) or not RUN_ID.fullmatch(args.run_id or "1"):
            raise Refused(
                "the digest is not sha256: and 64 lowercase hex, or the run id not a number"
            )
        if args.action == "rollback" and args.run_id:
            raise Refused("rollback takes no run id")
        what = f"{args.action} {args.digest} key {args.key} run {args.run_id or 'none'}"
        cfg = host_config(d, args.key, args.action)
        if cfg.fingerprint:  # production: the one owner key its authorized_keys line admits (H3 11)
            what += f" fingerprint {cfg.fingerprint}"
        fd = lock(d)
        rollback = args.action == "rollback"
        result = deploy(d, alert, cfg, args.digest, args.run_id, rollback)
        code = 0
    except Refused as exc:  # raised only before any change: nothing changed
        result, code = f"refused: {exc}", 2
    except RecordFailed as exc:
        result, code = str(exc), 3
    except Failed as exc:
        result = f"failed: {exc}"
    except OSError as exc:
        result = f"failed: {exc.strerror} {exc.filename}"
    except Exception as exc:  # unparsable tool output: its type, never its text
        result = f"failed: cannot read a tool's output ({type(exc).__name__})"
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        record(Host(args.root, chown), journal, f"{what}: {result}", "skiw-deploy")
    except OSError as exc:
        say(f"skiw-deploy: writing the log failed: {exc.strerror} {exc.filename}")
        return 3 if code == 0 else code
    return code


def status_main(root: Path = Path("/"), owner: Owner = stat_owner) -> int:
    """`skiw-staging-status` (G11 (b)): the forced command of production's status key on staging.
    Ignores SSH_ORIGINAL_COMMAND; prints the last staging check line and whether that digest is
    the one running now, or nothing (exit 1) when there is no well-formed line."""
    d = Deploy(root, run_command, owner, lambda p, u, g: None)
    try:
        lines = read_lines(d, STATUS, CHECK_LINE)
        state = settings(root / apply.STATE, d.read(apply.STATE, apply.CONFIG).decode("ascii"))
    except (Refused, UnicodeDecodeError):
        return 1
    if not lines:
        return 1
    running = state.get("SKIW_IMAGE", "").rpartition("@")[2]
    digest = CHECK_LINE.fullmatch(lines[-1])[1]  # type: ignore[index]  # read_lines checked it
    print(f"{lines[-1]} running={'yes' if running == digest else 'no'}")
    return 0


def ssh_main(
    argv: Sequence[str] | None = None,
    environ: dict[str, str] | None = None,
    execv: Callable[[str, list[str]], object] = os.execv,
) -> int:
    """The forced command of both deploy keys. The key role is the authorized_keys argument; the
    caller supplies only SSH_ORIGINAL_COMMAND, which must match SSH_COMMAND exactly."""
    args = list(sys.argv[1:] if argv is None else argv)
    command = (os.environ if environ is None else environ).get("SSH_ORIGINAL_COMMAND", "")
    if len(args) != 2 or args[0] != "--key" or args[1] not in ROLES:
        print(
            "skiw-deploy-ssh: refused: authorized_keys must pass --key production|staging",
            file=sys.stderr,
        )
        return 2
    if not SSH_COMMAND.fullmatch(command):
        print(
            "skiw-deploy-ssh: refused: expected `deploy <digest> [<run-id>]`, `rollback <digest>`",
            file=sys.stderr,
        )
        return 2
    sudo = ["/usr/bin/sudo", "-n", SBIN, "--key", args[1], *command.split(" ")]
    execv(sudo[0], sudo)  # fixed program, argv checked above, no shell
    return 1  # reached only when a test replaces execv
