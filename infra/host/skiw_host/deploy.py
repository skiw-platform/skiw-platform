"""`skiw-deploy --key <role> deploy <digest> [<run-id>]` (spec §8.4 H3; runbook deploy.md).

Run as root through one sudo rule, reached only from the forced command `skiw-deploy-ssh`. Steps:
(3) check the digest, the key role and host config, take the deploy lock, pull by digest with the
GHCR read token on stdin; (4) `migrate --plan`, and when it is not empty the pre-migration dump;
(5) `migrate`; (6) switch web and worker (SKIW_IMAGE in the state file, `docker compose up -d`);
(7) `/readyz` 200 and a new worker registered, else switch back and alert (migrations are never
reversed); (11) one value-free line to the journal and the deploy log. Tool output and secret
values are never printed. Exit 0 done, 1 failed (the old digest still serves), 2 refused (nothing
changed), 3 done but the log line failed.
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
from functools import partial
from pathlib import Path

from skiw_host import apply
from skiw_host.bootstrap_db import ONE_LINE, Failed, Runner, psql_script, run_command, settings
from skiw_host.bootstrap_secrets import Chown, Host, Journal, Refused, record, to_journal
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
TimedRunner = Callable[[list[str], bytes, float], subprocess.CompletedProcess[bytes]]
# The pre-migration dump hook: the `backup` service's `predeploy` command (built in M1g-2) prints
# exactly this one line when the encrypted dump and its checksum are written. Anything else,
# including today's plain pg_dump, stops the deploy before `migrate`.
DUMP = ["--profile", "ops", "run", "--rm", "-T", "backup", "predeploy"]
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


def to_alert(message: str) -> None:  # picked up by the health alert sender (M1j)
    syslog.openlog("skiw-deploy")
    syslog.syslog(syslog.LOG_ALERT, message)


def run_timed(argv: list[str], stdin: bytes, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """subprocess.run kills the child and raises TimeoutExpired when the bound passes."""
    return subprocess.run(argv, input=stdin, capture_output=True, check=False, timeout=timeout)  # noqa: S603 - argv built here, no shell


class Deploy:
    def __init__(self, root: Path, run: Runner, owner: Owner, chown: Chown) -> None:
        self.root, self.run, self.owner, self.chown = root, run, owner, chown
        self.timed: TimedRunner = run_timed  # the switch, the health probes and the recovery
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

    def ok(self, argv: list[str], label: str, stdin: bytes = b"", bound: float = 0) -> str:
        done = self.timed(argv, stdin, bound) if bound else self.run(argv, stdin)
        if done.returncode != 0:  # the output may quote config or data: withheld
            raise Failed(f"`{label}` exited {done.returncode}")
        return done.stdout.decode("utf-8")

    def compose(self, image: str) -> list[str]:
        """The new or old image wins over the state file (Compose: environment before env file)."""
        files = ["-f", str(self.root / apply.COMPOSE), "--env-file", str(self.root / apply.ENV)]
        return ["env", f"SKIW_IMAGE={image}", "docker", "compose", *files]


def host_config(d: Deploy, key: str) -> tuple[str, str, int]:
    values = settings(d.root / apply.ENV, d.read(apply.ENV).decode("utf-8"))
    environment = values.get("SKIW_ENVIRONMENT", "")
    if environment not in ROLES:
        raise Refused("SKIW_ENVIRONMENT in the host env file is not production or staging")
    if key != environment:
        raise Refused(f"the {key} deploy key is refused on {environment}")
    if environment == "production":  # G11 staging check and the accepted-digest record: M1g-2
        raise Refused("production deploys need the staging check, which arrives in M1g-2")
    repository, hostname = values.get("SKIW_IMAGE_REPOSITORY", ""), values.get("SKIW_HOSTNAME", "")
    timeout = values.get("SKIW_DEPLOY_HEALTH_TIMEOUT_S", "")
    if not REPOSITORY.fullmatch(repository):
        raise Refused("SKIW_IMAGE_REPOSITORY is not a ghcr.io/<owner>/<name> repository")
    if not HOSTNAME.fullmatch(hostname) or not re.fullmatch(r"[1-9][0-9]{0,2}", timeout):
        raise Refused("SKIW_HOSTNAME or SKIW_DEPLOY_HEALTH_TIMEOUT_S is empty or invalid")
    d.read(apply.COMPOSE)  # Compose reads it as root: root-owned, never through a link
    return repository, hostname, int(timeout)


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
        d.ok([*docker, "pull", image], "docker pull")
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


def workers(d: Deploy, image: str, query: str, bound: float) -> int:
    """One count, bounded by `bound` seconds on the client and in the database."""
    psql = [*d.compose(image), "exec", "-T", "db", "sh", "-c", psql_script()]
    limits = BOUND.format(max(1, int(bound * 1000)))
    script = f"\\pset format unaligned\n\\pset tuples_only on\n{limits}\n{query}\n"
    out = d.ok(psql, "psql", script.encode(), bound).strip()
    if not re.fullmatch(r"[0-9]{1,19}", out):
        raise Failed("psql did not print one count")
    return int(out)


def write_state(d: Deploy, data: bytes | None) -> None:
    """Replace the state file atomically with `data`, or remove it (None)."""
    try:  # checked before the pull too; a change since then fails here (migrate has run)
        apply.untrusted(d.root, [apply.STATE], lambda p: d.owner(p, p.lstat()))
        apply.make_directories(d.root, Path(apply.STATE).parent, d.chown)
    except Refused as exc:
        raise Failed(str(exc)) from None
    if data is None:
        (d.root / apply.STATE).unlink(missing_ok=True)
        return
    tmp = d.root / f"{apply.STATE}.skiw-new"
    tmp.unlink(missing_ok=True)  # a leftover of a stopped run, in a root-only directory
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, apply.CONFIG)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, apply.CONFIG)
    d.chown(str(tmp), *apply.ROOT)
    os.replace(tmp, d.root / apply.STATE)


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


def deploy(
    d: Deploy, alert: Journal, image: str, repository: str, hostname: str, timeout: int
) -> str:
    found = current(d, repository)
    previous, prior = found if found else (None, None)
    pull(d, repository, image)
    if pending(d, image):
        out = d.ok([*d.compose(image), *DUMP], "pre-migration dump")
        if not DUMP_DONE.fullmatch(out.strip()):
            raise Failed("the pre-migration dump did not report a written dump")
    d.ok([*d.compose(image), *PLAN], "migrate")  # as skiw_migrator; old containers keep serving
    # Same digest: Compose keeps the running worker, so its fresh heartbeat is the proof; a new
    # digest recreates the worker, which must register above the ids that existed before.
    floor = 0 if previous == image else workers(d, image, WORKERS, 2 * HEARTBEAT_S)
    was = (previous or "none").rpartition("@")[2]
    step = "switch"
    try:  # from the state replacement on, every failure goes through the recovery below
        switch(d, image)
        step = "health check"
        if healthy(d, image, hostname, timeout, floor):
            return f"deployed; previous {was}"
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
        alert(f"deploy {image.partition('@')[2]} failed its {step}; {back}")
    except Exception:  # reported and alerted, never hidden
        back = f"RECOVERY FAILED, switching back to {was}: see docs/runbooks/deploy.md"
        alert(f"deploy {image.partition('@')[2]} failed its {step}; {back}")
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
        what = f"{args.action} {args.digest} key {args.key} run {args.run_id or 'none'}"
        if args.action == "rollback":
            raise Refused("rollback arrives in M1g-2: see docs/runbooks/rollback.md")
        repository, hostname, timeout = host_config(d, args.key)
        fd = lock(d)
        result = deploy(d, alert, f"{repository}@{args.digest}", repository, hostname, timeout)
        code = 0
    except Refused as exc:  # raised only before the pull: nothing changed
        result, code = f"refused: {exc}", 2
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
        print(
            f"skiw-deploy: writing the log failed: {exc.strerror} {exc.filename}", file=sys.stderr
        )
        return 3 if code == 0 else code
    return code


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
