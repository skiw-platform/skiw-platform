"""`skiw-deploy`, its forced command `skiw-deploy-ssh` and `skiw-staging-status` (spec §8.4 H3;
plan §3 M1g).

A fake runner stands in for docker (login, pull by digest, image inspect, compose run/up/stop/exec,
rm), curl, ssh (the staging status call), lsattr and chattr, with their documented failure rules:
`compose up` recreates web and worker only when the image changed (an unchanged worker keeps its
procrastinate id) and may apply a change and still exit 1; any tool may exit non-zero, print
nothing, a cut line, extra lines or bytes that are not text; every call but `migrate` goes through
the bounded runner and may time out (subprocess.run kills the client; a `compose run` container
then keeps running until removed). ssh exits 255 on its own failure and otherwise with the remote
command's code; lsattr prints `<flags> <path>` or exits 1; chattr may exit 0 on a file system that
then still shows no `a` flag. A fake clock stands in for time. The GHCR token is generated per test
and must reach `docker login` on stdin only, never argv, output or a log.
"""

import errno
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from secrets import token_urlsafe

import pytest

from skiw_host import apply, deploy, hardening

HOST = Path(__file__).resolve().parents[1]
REPO = "ghcr.io/skiw-platform/skiw-platform"
NEW, OLD = f"sha256:{'a' * 64}", f"sha256:{'b' * 64}"
NO_PLAN = "Planned operations:\n  No planned migration operations.\n"
A_PLAN = "Planned operations:\njobs.0002_x\n    Raw SQL operation\n"
COMMIT = "c" * 40
FINGERPRINT = "SHA256:" + "F" * 43
HOST_KEY = "ssh-ed25519 " + "A" * 68
CONTRACT = "jobs.0003_drop_old"


def names(*migrations: str, contracts: tuple[str, ...] = ()) -> dict[str, list[str]]:
    """migration_labels' output for an image shipping these migrations, the last one the head."""
    return {"head": [migrations[-1]], "contracts": list(contracts), "migrations": list(migrations)}


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "root"
        env = (HOST / "env/ci.env").read_text()
        self.put(apply.ENV, env)
        self.put(apply.COMPOSE, "services: {}\n")
        self.secret = token_urlsafe(24)
        self.put(deploy.TOKEN_FILE, f"{self.secret}\n", hardening.SECRET_MODE)
        (self.root / "run").mkdir()
        self.registry = {f"{REPO}@{NEW}", f"{REPO}@{OLD}"}  # digests the fixed repository has
        self.logged_in: set[str] = set()  # docker --config dirs holding a login
        self.pulled: set[str] = set()
        self.running: str | None = None  # the image web and worker run
        self.healthy = {f"{REPO}@{OLD}", f"{REPO}@{NEW}"}
        self.out: dict[str, tuple[int, str | bytes]] = {
            "plan": (0, NO_PLAN),
            "dump": (1, ""),
            "migrate": (0, ""),
            "check": (0, "tenancy schema check: ok\n"),
        }
        both = names("jobs.0001_x", "jobs.0002_y")
        self.names = {f"{REPO}@{NEW}": both, f"{REPO}@{OLD}": both}  # migration_labels per image
        self.labels: dict[str, dict[str, str] | None] = {  # docker image labels per image
            image: {deploy.COMMIT_LABEL: COMMIT, deploy.HEAD_LABEL: "jobs.0002_y"}
            for image in self.names
        }
        self.staging = (0, "")  # what staging's skiw-staging-status prints (code, line)
        self.append_only, self.chattr = False, True  # the record's `a` flag; chattr +a sets it
        self.chattr_code = 0  # chattr's exit code (0 may still set nothing on some file systems)
        self.known_hosts = ""  # what ssh found in its UserKnownHostsFile
        self.at_migrate: str | None = None  # the applied-contract list when `migrate` started
        self.lsattr: tuple[int, str | bytes] | None = (
            None  # override what lsattr prints (code, output)
        )
        self.removed: list[str] = []  # `docker rm --force` names
        self.rm_code = 0
        self.dump_running = False  # a timed-out dump container still runs until removed
        self.on_curl: Callable[[], object] = lambda: None
        self.top = 4  # the highest procrastinate worker id
        self.worker: int | None = None  # the live worker's id
        self.registered = True  # a recreated worker registers and keeps its heartbeat fresh
        self.partial: set[str] = set()  # `up` with these images applies them, then exits 1
        self.broken: set[str] = set()  # `up` with these images changes nothing, exits 1
        self.slow: tuple[str, float] = ("", 0.0)  # a command (substring) and the time it takes
        self.raises: tuple[str, BaseException | None] = ("", None)
        self.bounds: list[tuple[str, float]] = []
        self.scripts: list[str] = []  # psql scripts sent to db  # (curl | exec | up | stop, bound)
        self.calls: list[list[str]] = []
        self.now = 0.0
        self.journal: list[str] = []
        self.alerts: list[str] = []

    def put(self, rel: str, text: str, mode: int = apply.CONFIG) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        path.write_text(text)
        os.chmod(path, mode)

    def call(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        assert self.secret not in " ".join(argv)  # the token never in argv
        code, out = self.answer(argv, stdin)
        data = out if isinstance(out, bytes) else out.encode()
        return subprocess.CompletedProcess(argv, code, data, b"")

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        """The unbounded runner: `migrate` only (deploy.py docstring)."""
        assert argv[0] == "env" and argv[-1] == "migrate", argv
        return self.call(argv, stdin)

    KINDS: tuple[str, ...] = ("curl", "ssh", "lsattr", "chattr", "login", "pull", "rm")
    KINDS += ("predeploy", "migration_labels", "--plan", "inspect", "exec", "up", "stop")
    KINDS += ("check_tenancy_schema",)

    def timed(
        self, argv: list[str], stdin: bytes, bound: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.bounds.append((next(a for a in self.KINDS if a in argv), bound))
        line = " ".join(argv) + stdin.decode()
        if (error := self.raises[1]) and self.raises[0] in line:
            self.calls.append(argv)
            self.raises = ("", None)  # once: the recovery's own commands run normally
            if "predeploy" in argv:  # the client is killed; its container runs on
                self.dump_running = True
            raise error
        if self.slow[0] and self.slow[0] in line:
            self.now += self.slow[1]
        return self.call(argv, stdin)

    def serve(self, image: str) -> None:
        self.put(apply.STATE, f"SKIW_IMAGE={image}\n")
        self.running, self.worker = image, self.top

    def answer(self, argv: list[str], stdin: bytes) -> tuple[int, str | bytes]:
        if argv[:2] == ["docker", "--config"] and argv[3] == "login":
            ok = "--password-stdin" in argv and stdin == f"{self.secret}\n".encode()
            self.logged_in |= {argv[2]} if ok else set()
            return (0, "Login Succeeded\n") if ok else (1, "")
        if argv[:2] == ["docker", "--config"] and argv[3] == "pull":  # by digest: exit 1 if absent
            if argv[2] not in self.logged_in or argv[4] not in self.registry:
                return 1, ""
            self.pulled.add(argv[4])
            return 0, f"Digest: {argv[4].partition('@')[2]}\n"
        if argv[:3] == ["docker", "image", "inspect"]:
            if argv[-1] not in self.pulled:
                return 1, "[]\n"
            if argv[4] == "{{json .Config.Labels}}":
                return 0, json.dumps(self.labels.get(argv[-1])) + "\n"
            if "inspect" in self.out:
                return self.out["inspect"]
            return 0, json.dumps([argv[-1]]) + "\n"
        if argv[0] == "ssh":
            known = next(o for o in argv if o.startswith("UserKnownHostsFile="))
            self.known_hosts = Path(known.partition("=")[2]).read_text()
            return self.staging
        if argv[:2] == ["lsattr", "-d"]:
            if self.lsattr is not None:
                return self.lsattr
            if not Path(argv[2]).exists():
                return 1, ""  # "No such file or directory" on stderr
            return 0, f"-----{'a' if self.append_only else '-'}--------e------- {argv[2]}\n"
        if argv[:2] == ["chattr", "+a"]:
            self.append_only |= self.chattr
            return self.chattr_code, ""
        if argv[:3] == ["docker", "rm", "--force"]:
            self.removed.append(argv[3])
            self.dump_running &= self.rm_code != 0
            return self.rm_code, ""
        if argv[0] == "curl":  # no response: exit 7 and %{http_code} 000
            self.on_curl()
            return (0, "200") if self.running in self.healthy else (7, "000")
        if argv[0] == "env" and argv[2:4] == ["docker", "compose"]:
            return self.compose(argv[1].removeprefix("SKIW_IMAGE="), argv[8:], stdin)
        return 127, ""

    def compose(self, image: str, args: list[str], stdin: bytes) -> tuple[int, str | bytes]:
        if args[-1] == "--plan":
            return self.out["plan"]
        if args[-1] == "migration_labels":
            if "labels" in self.out:
                return self.out["labels"]
            return 0, json.dumps(self.names[image]) + "\n"
        if args[-1] == "predeploy":
            assert args[args.index("--name") + 1] == deploy.DUMP_NAME
            if self.dump_running:  # "the container name is already in use"
                return 1, ""
            return self.out["dump"]
        if args[-1] == "check_tenancy_schema":
            return self.out["check"]
        if args[-1] == "migrate":
            applied = self.root / deploy.APPLIED
            self.at_migrate = applied.read_text() if applied.exists() else None
            return self.out["migrate"]
        if args[:2] == ["up", "-d"]:
            if image in self.broken:
                return 1, ""
            if image != self.running:  # changed: web and worker recreated, a new worker id
                self.top += 1
                self.running, self.worker = image, self.top if self.registered else None
            return int(image in self.partial), ""
        if args == ["stop", "web", "worker"]:
            self.running = self.worker = None
            return 0, ""
        if args[:3] == ["exec", "-T", "db"]:
            self.scripts.append(stdin.decode())
            if b"max(id)" in stdin:
                return 0, f"{self.top}\n"
            above = int(stdin.decode().partition("WHERE id > ")[2].split()[0])
            return 0, "1\n" if self.worker and self.worker > above else "0\n"
        return 1, ""

    def run(self, *argv: str) -> int:
        d = deploy.Deploy(self.root, self.runner, lambda p, i: (0, 0), lambda p, u, g: None)
        d.clock, d.sleep, d.timed = lambda: self.now, self.tick, self.timed
        args = [*argv, "--root", str(self.root)]
        code = deploy.main(args, journal=self.journal.append, alert=self.alerts.append, d=d)
        logged = "".join(self.journal) + (self.root / "var/log/skiw/deploy.log").read_text()
        assert self.secret not in logged and len(self.journal) == 1
        return code

    def production(self) -> None:
        values = {"SKIW_ENVIRONMENT": "production", "SKIW_STAGING_SSH": "staging.skiw.test:2222"}
        values |= {"SKIW_STAGING_HOST_KEY": HOST_KEY, "SKIW_DEPLOY_KEY_FINGERPRINT": FINGERPRINT}
        text = (self.root / apply.ENV).read_text() + "".join(
            f"{k}={v}\n" for k, v in values.items()
        )
        self.put(apply.ENV, text)
        armour = "-----BEGIN OPENSSH PRIVATE KEY-----\n{}\n-----END OPENSSH PRIVATE KEY-----\n"
        self.put(deploy.STATUS_KEY_FILE, armour.format(token_urlsafe(48)), hardening.SECRET_MODE)
        self.green(NEW)

    def green(self, digest: str, checks: str = "passed", running: str = "yes") -> None:
        line = f"digest={digest} checked=20261022T090000Z readyz=200 worker=registered"
        self.staging = (0, f"{line} head=match checks={checks} running={running}\n")

    def accepted(self) -> list[str]:
        path = self.root / deploy.ACCEPTED
        return path.read_text().splitlines() if path.exists() else []

    def tick(self, seconds: float) -> None:
        self.now += seconds

    def state(self) -> str:
        return (self.root / apply.STATE).read_text()


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_a_deploy_pulls_migrates_switches_and_checks_health(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")
    assert rig.run("--key", "staging", "deploy", NEW, "42") == 0
    assert rig.state() == f"SKIW_IMAGE={REPO}@{NEW}\n" and rig.running == f"{REPO}@{NEW}"
    steps = [c[3] if c[1] == "--config" else c[-1] if c[0] == "env" else c[0] for c in rig.calls]
    assert steps[:2] == ["login", "pull"] and steps[4:8] == [
        "migration_labels",
        "--plan",
        "migrate",
        "check_tenancy_schema",
    ]
    assert steps[9:11] == ["-d", "curl"] and len(steps) == 12  # no dump: nothing planned
    assert not any(Path(c[2]).exists() for c in rig.calls[:2])  # the login config is removed
    assert rig.journal == [
        f"deploy {NEW} key staging run 42: deployed; previous {OLD}; staging checks passed"
    ]
    status = (rig.root / deploy.STATUS).read_text()
    assert deploy.CHECK_LINE.fullmatch(status.strip()) and status.startswith(f"digest={NEW} ")
    assert status.strip().endswith("head=match checks=passed") and rig.accepted() == []
    assert rig.secret not in capsys.readouterr().err and rig.alerts == []
    assert (rig.root / deploy.LOCK).stat().st_mode & 0o777 == 0o600


def test_a_pending_migration_runs_the_dump_first_and_a_failed_dump_stops(rig: Rig) -> None:
    rig.out["plan"] = (0, A_PLAN)
    for dump in ((1, ""), (0, "pg_dump (PostgreSQL) 17.11\n")):  # today's backup: not a dump
        rig.calls.clear()
        rig.journal.clear()
        rig.out["dump"] = dump
        assert rig.run("--key", "staging", "deploy", NEW) == 1
        assert rig.calls[-1][-1] == "predeploy" and rig.running is None
        assert not (rig.root / apply.STATE).exists()
    rig.out["dump"] = (0, f"predeploy 20261021T101500Z.dump.age {'c' * 64}\n")
    rig.journal.clear()
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    env = [c[-1] for c in rig.calls if c[0] == "env"]
    assert env[-7:-3] == ["--plan", "predeploy", "migrate", "check_tenancy_schema"]


@pytest.mark.parametrize(
    "fault",
    [
        {"migrate": (1, "")},  # old containers keep serving
        {"plan": (0, "Operations to perform:\n")},  # not a plan: fail closed
        {"plan": (1, "")},
    ],
)
def test_a_failed_migration_step_stops_before_the_switch(
    rig: Rig, fault: dict[str, tuple[int, str]]
) -> None:
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")
    rig.running = f"{REPO}@{OLD}"
    rig.out.update(fault)
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == f"SKIW_IMAGE={REPO}@{OLD}\n"
    assert not any(c[-2:] == ["up", "-d"] for c in rig.calls) and rig.alerts == []


def test_a_failed_schema_check_stops_after_migrate_and_before_the_switch(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    """Plan M4c-6b: the migrations stay applied (never reversed), the old digest keeps serving, and
    the check's own lines (table names and reasons) are withheld like any tool output."""
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")
    rig.running = f"{REPO}@{OLD}"
    rig.out["check"] = (1, "public.loose: not on the global list and has no agency_id column\n")
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == f"SKIW_IMAGE={REPO}@{OLD}\n"
    assert [c[-1] for c in rig.calls if c[0] == "env"][-2:] == ["migrate", "check_tenancy_schema"]
    assert not any(c[-2:] == ["up", "-d"] for c in rig.calls) and rig.alerts == []
    assert ("check_tenancy_schema", deploy.TOOL_S) in rig.bounds
    assert rig.journal == [
        f"deploy {NEW} key staging run none: failed: `check_tenancy_schema` exited 1"
    ]
    assert "public.loose" not in capsys.readouterr().err


@pytest.mark.parametrize("fault", ["readyz", "worker"])
def test_a_failed_health_check_switches_back_and_alerts(rig: Rig, fault: str) -> None:
    rig.serve(f"{REPO}@{OLD}")
    if fault == "readyz":
        rig.healthy = {f"{REPO}@{OLD}"}
    else:
        rig.registered = False
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == f"SKIW_IMAGE={REPO}@{OLD}\n"
    assert rig.alerts == [f"deploy {NEW} failed its health check; switched back to {OLD}"]
    assert rig.now >= (60 if fault == "readyz" else 2 * deploy.HEARTBEAT_S)
    assert sum(c[-1] == "migrate" for c in rig.calls) == 1  # never reversed, never re-run
    assert "migrations were not reversed" in rig.journal[0]


def test_a_failed_first_deploy_leaves_nothing_to_switch_back_to(rig: Rig) -> None:
    rig.healthy = {f"{REPO}@{OLD}"}  # NEW fails /readyz
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running is None and not (rig.root / apply.STATE).exists()
    assert ("stop", deploy.SWITCH_S) in rig.bounds  # the cleanup is bounded too
    assert rig.alerts == [
        f"deploy {NEW} failed its health check; no previous digest: web and worker stopped"
    ]
    rig.calls.clear()
    rig.journal.clear()
    rig.registered = False  # OLD passes /readyz but its worker never registers
    assert rig.run("--key", "staging", "deploy", OLD) == 1
    assert rig.running is None and not (rig.root / apply.STATE).exists()  # NEW not restarted
    assert not any(f"={REPO}@{NEW}" in " ".join(c) for c in rig.calls)


@pytest.mark.parametrize("fault", ["partial", "raises"])
def test_a_failed_switch_is_recovered_like_a_failed_health_check(rig: Rig, fault: str) -> None:
    rig.serve(f"{REPO}@{OLD}")
    before = rig.state()
    if fault == "partial":  # `up` recreated the services with NEW, then exited 1
        rig.partial = {f"{REPO}@{NEW}"}
    else:  # after the state replacement, the candidate's `up` raises
        rig.raises = (" up -d", OSError(5, "Input/output error"))
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == before
    assert any(c[-2:] == ["up", "-d"] and c[1].endswith(NEW) for c in rig.calls)
    assert rig.alerts == [f"deploy {NEW} failed its switch; switched back to {OLD}"]
    assert sum(c[-1] == "migrate" for c in rig.calls) == 1  # never reversed, never re-run


def test_a_failed_recovery_is_alerted_as_such_and_releases_the_lock(rig: Rig) -> None:
    rig.serve(f"{REPO}@{OLD}")
    rig.healthy, rig.broken = {f"{REPO}@{OLD}"}, {f"{REPO}@{OLD}"}
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert len(rig.alerts) == 1 and "RECOVERY FAILED, switching back to" in rig.alerts[0]
    assert "RECOVERY FAILED" in rig.journal[0] and "migrations were not reversed" in rig.journal[0]
    fd = os.open(rig.root / deploy.LOCK, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # free again
    os.close(fd)


def test_the_same_healthy_digest_deploys_twice(rig: Rig) -> None:
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    worker = rig.worker
    rig.journal.clear()
    assert rig.run("--key", "staging", "deploy", NEW) == 0  # Compose keeps the running worker
    assert rig.worker == worker and rig.alerts == [] and "deployed" in rig.journal[0]


@pytest.mark.parametrize(
    "fault",
    [
        ("last_heartbeat", 120.0, None),  # a positive count that arrives after the deadline
        ("last_heartbeat", 0.0, subprocess.TimeoutExpired("docker", 20)),  # never returns
        ("curl", 0.0, subprocess.TimeoutExpired("curl", 5)),
    ],
)
def test_a_late_or_hanging_health_probe_fails_the_deploy(
    rig: Rig, fault: tuple[str, float, BaseException | None]
) -> None:
    rig.serve(f"{REPO}@{OLD}")
    rig.slow, rig.raises = (fault[0], fault[1]), (fault[0], fault[2])
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.alerts[0].endswith(f"switched back to {OLD}")
    limits = {"curl": 60, "exec": 2 * deploy.HEARTBEAT_S, "up": deploy.SWITCH_S}
    limits |= {"pull": deploy.PULL_S}
    assert all(0 < bound <= limits.get(kind, deploy.TOOL_S) for kind, bound in rig.bounds)
    assert [b for kind, b in rig.bounds if kind == "up"] == [deploy.SWITCH_S] * 2  # and recovery
    for argv in (c for c in rig.calls if c[0] == "curl"):
        assert 1 <= int(argv[argv.index("--max-time") + 1]) <= 5
    for script in (s for s in rig.scripts if "last_heartbeat" in s):  # cancelled in the database
        ms = [int(x) for x in re.findall(r"(?:statement|lock)_timeout = ([0-9]+);", script)]
        assert len(ms) == 2 and all(0 < m <= 2 * deploy.HEARTBEAT_S * 1000 for m in ms)
    fd = os.open(rig.root / deploy.LOCK, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # the lock was released
    os.close(fd)


@pytest.mark.parametrize(
    "argv",
    [
        ("deploy", f"sha256:{'A' * 64}"),
        ("deploy", f"{NEW}\n"),
        ("deploy", f" {NEW}"),
        ("deploy", "sha256:abc"),
        ("deploy", f"{REPO}@{NEW}"),
        ("deploy", "latest"),
        ("deploy", NEW, "01"),
        ("deploy", NEW, "1;id"),
        ("rollback", OLD),  # rollback takes the production key only
    ],
)
def test_a_bad_request_is_refused_and_nothing_runs(rig: Rig, argv: tuple[str, ...]) -> None:
    assert rig.run("--key", "staging", *argv) == 2
    assert rig.calls == [] and not (rig.root / apply.STATE).exists()
    if argv[0] == "rollback":
        assert rig.journal[0].endswith("refused: rollback takes the owner's production key only")
    if argv[0] == "deploy":  # unchecked caller input never reaches the log
        assert rig.journal[0].startswith("deploy key staging: refused: the digest is not")


@pytest.mark.parametrize(
    ("key", "values"),
    [
        ("production", {}),  # the production key on staging
        ("production", {"SKIW_ENVIRONMENT": "production"}),  # no staging SSH, host key, fingerprint
        ("staging", {"SKIW_ENVIRONMENT": "production"}),
        ("staging", {"SKIW_ENVIRONMENT": ""}),
        ("staging", {"SKIW_IMAGE_REPOSITORY": "ghcr.io/someone-else"}),
        ("staging", {"SKIW_IMAGE_REPOSITORY": "docker.io/skiw-platform/skiw-platform"}),
        ("staging", {"SKIW_HOSTNAME": ""}),
        ("staging", {"SKIW_DEPLOY_HEALTH_TIMEOUT_S": "0"}),
        ("staging", {"SKIW_DEPLOY_DUMP_TIMEOUT_S": ""}),
        ("staging", {"SKIW_DEPLOY_DUMP_TIMEOUT_S": "0"}),
    ],
)
def test_a_key_or_host_config_that_does_not_fit_is_refused(
    rig: Rig, key: str, values: dict[str, str]
) -> None:
    text = (rig.root / apply.ENV).read_text() + "".join(f"{k}={v}\n" for k, v in values.items())
    rig.put(apply.ENV, text)
    assert rig.run("--key", key, "deploy", NEW) == 2 and rig.calls == []


def group_writable(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) | stat.S_IWGRP
    os.chmod(path, mode)


@pytest.mark.parametrize(
    "unsafe",
    [
        lambda rig: group_writable(rig.root / apply.ENV),
        lambda rig: rig.put(deploy.TOKEN_FILE, f"{rig.secret}\n", 0o440),
        lambda rig: rig.put(deploy.TOKEN_FILE, "", hardening.SECRET_MODE),
        lambda rig: rig.put(apply.STATE, f"SKIW_IMAGE=ghcr.io/other/app@{OLD}\n"),
        lambda rig: group_writable(rig.root / "srv/skiw"),
        lambda rig: (rig.root / "run" / "skiw-deploy.lock").symlink_to(rig.root / "x"),
    ],
)
def test_an_unsafe_file_is_refused_before_anything_changes(
    rig: Rig, unsafe: Callable[[Rig], object]
) -> None:
    unsafe(rig)
    assert rig.run("--key", "staging", "deploy", NEW) == 2
    assert not any(c[0] == "env" for c in rig.calls) and rig.running is None


def test_a_held_lock_refuses_a_second_deploy(rig: Rig) -> None:
    fd = os.open(rig.root / deploy.LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert rig.run("--key", "staging", "deploy", NEW) == 2 and rig.calls == []
    finally:
        os.close(fd)


@pytest.mark.parametrize("fault", ["foreign", "inspect"])
def test_a_digest_the_repository_does_not_hold_fails_at_the_pull(rig: Rig, fault: str) -> None:
    if fault == "foreign":  # a digest of another repository: not found in this one
        rig.registry = {f"{REPO}@{OLD}"}
    else:
        rig.out["inspect"] = (0, json.dumps([f"{REPO}@{OLD}"]))  # pulled, but another digest
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert not any(c[0] == "env" for c in rig.calls)


def test_a_failed_log_line_after_a_deploy_exits_3(rig: Rig) -> None:
    rig.put("var/log/skiw", "not a directory\n")
    d = deploy.Deploy(rig.root, rig.runner, lambda p, i: (0, 0), lambda p, u, g: None)
    d.clock, d.sleep, d.timed = lambda: rig.now, rig.tick, rig.timed
    argv = ["--key", "staging", "deploy", NEW, "--root", str(rig.root)]
    assert deploy.main(argv, journal=rig.journal.append, alert=rig.alerts.append, d=d) == 3


class ClosedChannel:
    """stderr under the forced command once the SSH client is gone: every write raises EPIPE
    (Python ignores SIGPIPE). Notes what the journal and the deploy log held at the first write."""

    def __init__(self, rig: Rig) -> None:
        self.rig = rig
        self.seen: tuple[list[str], str] | None = None

    def write(self, text: str) -> int:
        if self.seen is None:
            log = self.rig.root / "var/log/skiw/deploy.log"
            self.seen = (list(self.rig.journal), log.read_text() if log.exists() else "")
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")

    def flush(self) -> None:
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


@pytest.mark.parametrize(
    ("case", "code", "result"),
    [
        ("deployed", 0, "deployed; previous"),
        ("failed", 1, "failed: "),
        ("refused", 2, "refused: "),
    ],
)
def test_a_dropped_ssh_session_still_logs_the_line_and_keeps_the_exit_code(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, case: str, code: int, result: str
) -> None:
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")
    if case == "failed":
        rig.out["migrate"] = (1, "")
    channel = ClosedChannel(rig)
    monkeypatch.setattr(sys, "stderr", channel)
    key = "production" if case == "refused" else "staging"  # production refuses: no host config
    assert rig.run("--key", key, "deploy", NEW, "42") == code
    monkeypatch.undo()
    [line] = (rig.root / "var/log/skiw/deploy.log").read_text().splitlines()
    assert f"skiw-deploy: deploy {NEW} key {key} run 42" in line and result in line
    assert len(rig.journal) == 1 and result in rig.journal[0]
    assert channel.seen == (rig.journal, f"{line}\n")  # both written before stderr was tried


def test_a_dropped_ssh_session_and_a_failed_log_still_exit_3(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.put("var/log/skiw", "not a directory\n")
    monkeypatch.setattr(sys, "stderr", ClosedChannel(rig))
    d = deploy.Deploy(rig.root, rig.runner, lambda p, i: (0, 0), lambda p, u, g: None)
    d.clock, d.sleep, d.timed = lambda: rig.now, rig.tick, rig.timed
    argv = ["--key", "staging", "deploy", NEW, "--root", str(rig.root)]
    assert deploy.main(argv, journal=rig.journal.append, alert=rig.alerts.append, d=d) == 3
    assert len(rig.journal) == 1 and "deployed" in rig.journal[0]


@pytest.mark.parametrize(
    "command",
    [
        "",
        "id",
        "deploy",
        "deploy sha256:abc",
        f"deploy {NEW};id",
        f"deploy {NEW} $(id)",
        f"deploy {NEW} 1 2",
        f"deploy {NEW}\n",
        f"deploy  {NEW}",
        f"deploy {REPO}@{NEW}",
        f"rollback {OLD} 1",
        f"deploy sha256:{'A' * 64}",
        f"--key production deploy {NEW}",
    ],
)
def test_the_forced_command_refuses_anything_else_and_runs_nothing(command: str) -> None:
    ran: list[list[str]] = []
    env = {"SSH_ORIGINAL_COMMAND": command}
    assert deploy.ssh_main(["--key", "staging"], env, lambda p, a: ran.append(a)) == 2
    assert ran == []


def test_the_forced_command_takes_the_key_role_from_authorized_keys_only() -> None:
    ran: list[list[str]] = []
    env = {"SSH_ORIGINAL_COMMAND": f"deploy {NEW} 7"}
    for argv in ([], ["--key"], ["--key", "owner"], ["--key", "staging", "--key", "production"]):
        assert deploy.ssh_main(argv, env, lambda p, a: ran.append(a)) == 2
    assert ran == []
    deploy.ssh_main(["--key", "staging"], env, lambda p, a: ran.append(a))
    deploy.ssh_main(
        ["--key", "production"],
        {"SSH_ORIGINAL_COMMAND": f"rollback {OLD}"},
        lambda p, a: ran.append(a),
    )
    sbin = "/usr/local/sbin/skiw-deploy"
    assert ran == [
        ["/usr/bin/sudo", "-n", sbin, "--key", "staging", "deploy", NEW, "7"],
        ["/usr/bin/sudo", "-n", sbin, "--key", "production", "rollback", OLD],
    ]


def test_a_staging_image_without_the_head_label_fails_the_staging_checks(rig: Rig) -> None:
    for labels, verdict in (({deploy.COMMIT_LABEL: COMMIT}, "unlabelled"), (None, "unlabelled")):
        rig.labels[f"{REPO}@{NEW}"] = labels
        rig.journal.clear()
        assert rig.run("--key", "staging", "deploy", NEW) == 0  # deployed and healthy
        status = (rig.root / deploy.STATUS).read_text()
        assert status.strip().endswith(f"head={verdict} checks=failed")
    rig.labels[f"{REPO}@{NEW}"] = {deploy.HEAD_LABEL: "jobs.0001_x"}
    rig.journal.clear()
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    assert (rig.root / deploy.STATUS).read_text().strip().endswith("head=differs checks=failed")


def test_a_production_deploy_checks_staging_and_adds_exactly_one_accepted_line(rig: Rig) -> None:
    rig.production()
    rig.serve(f"{REPO}@{OLD}")
    assert rig.run("--key", "production", "deploy", NEW, "77") == 0
    assert rig.running == f"{REPO}@{NEW}" and rig.append_only
    [line] = rig.accepted()
    assert deploy.ACCEPTED_LINE.fullmatch(line)
    assert line.startswith(f"digest={NEW} commit={COMMIT} run=77 staging_checked=20261022T090000Z")
    assert line.endswith(f"head=jobs.0002_y contracts=- key={FINGERPRINT}")
    [ssh] = [c for c in rig.calls if c[0] == "ssh"]
    assert (
        ssh[-2:] == ["skiw-deploy@staging.skiw.test", "status"]
        and "StrictHostKeyChecking=yes" in ssh
    )
    assert ("ssh", deploy.STATUS_S) in rig.bounds  # the status call is bounded
    assert not list((rig.root / "run").glob("skiw-status-*"))  # the known_hosts file is removed
    assert not (rig.root / deploy.STATUS).exists()  # production writes no staging status


@pytest.mark.parametrize(
    "staging",
    [
        (0, ""),  # nothing to report
        (255, ""),  # ssh failed (host key mismatch, refused, unreachable)
        (0, "digest=sha256:x checks=passed\n"),  # not a status line
        "other digest",
        "checks failed",
        "not running",
        "head differs",  # a line that says passed without head=match is not trusted
        "timeout",
        "cut",  # the connection dropped mid-line
        "two lines",
        "banner first",
        "exit 1 with a line",  # the forced command failed after printing
        "not text",
    ],
)
def test_production_refuses_unless_staging_runs_that_digest_with_checks_passed(
    rig: Rig, staging: object
) -> None:
    rig.production()
    rig.serve(f"{REPO}@{OLD}")
    if staging == "other digest":
        rig.green(OLD)
    elif staging == "checks failed":
        rig.green(NEW, checks="failed")
    elif staging == "not running":
        rig.green(NEW, running="no")
    elif staging == "head differs":
        rig.green(NEW)
        rig.staging = (0, str(rig.staging[1]).replace("head=match", "head=differs"))
    elif staging == "timeout":
        rig.raises = ("ssh", subprocess.TimeoutExpired("ssh", deploy.STATUS_S))
    elif isinstance(staging, tuple):
        rig.staging = staging
    else:
        rig.green(NEW)
        line = str(rig.staging[1])
        rig.staging = {
            "cut": (0, line[:-12]),
            "two lines": (0, line + line),
            "banner first": (0, "Welcome to Ubuntu\n" + line),
            "exit 1 with a line": (1, line),
            "not text": (0, line.replace("checked=", "checked=\u00e9")),
        }[str(staging)]
    assert rig.run("--key", "production", "deploy", NEW, "77") == 2
    assert not any(c[0] in ("docker", "env") for c in rig.calls) and rig.accepted() == []
    assert rig.running == f"{REPO}@{OLD}" and "staging" in rig.journal[0]


@pytest.mark.parametrize("fault", ["no run id", "no commit label", "no chattr", "staging key"])
def test_production_refuses_without_run_id_commit_label_append_only_record_or_owner_key(
    rig: Rig, fault: str
) -> None:
    rig.production()
    argv = ["--key", "production", "deploy", NEW, "77"]
    if fault == "no run id":
        argv = argv[:-1]
    elif fault == "no commit label":
        rig.labels[f"{REPO}@{NEW}"] = {deploy.HEAD_LABEL: "jobs.0002_y"}
    elif fault == "no chattr":
        rig.chattr, rig.chattr_code = False, 1  # e.g. a filesystem without the attribute
    else:
        argv[1] = "staging"
    assert rig.run(*argv) == 2
    assert rig.accepted() == [] and not any(c[-1] == "migrate" for c in rig.calls)


def test_a_failed_production_health_check_restores_the_previous_digest_without_a_line(
    rig: Rig,
) -> None:
    rig.production()
    rig.serve(f"{REPO}@{OLD}")
    rig.healthy = {f"{REPO}@{OLD}"}
    assert rig.run("--key", "production", "deploy", NEW, "77") == 1
    assert rig.running == f"{REPO}@{OLD}" and rig.accepted() == []
    assert rig.alerts == [f"deploy {NEW} failed its health check; switched back to {OLD}"]


def test_a_failed_accepted_line_after_a_healthy_deploy_exits_3_and_alerts(rig: Rig) -> None:
    rig.production()

    def tamper() -> None:  # the record replaced by a directory while the deploy runs
        path = rig.root / deploy.ACCEPTED
        if path.is_file():
            path.unlink()
            path.mkdir()

    rig.on_curl = tamper
    assert rig.run("--key", "production", "deploy", NEW, "77") == 3
    assert rig.running == f"{REPO}@{NEW}"  # it is serving: never switched back for the record
    assert rig.alerts == [f"deploy {NEW} is running but its accepted-digest line failed"]
    assert "accepted-digest line failed" in rig.journal[0]
    line = rig.journal[0].partition("; line: ")[2]  # for the hand append in deploy.md
    assert deploy.ACCEPTED_LINE.fullmatch(line) and line.startswith(f"digest={NEW} commit={COMMIT}")


def test_a_record_hard_linked_while_the_deploy_runs_gets_no_line(rig: Rig) -> None:
    rig.production()
    rig.on_curl = lambda: os.link(rig.root / deploy.ACCEPTED, rig.root / "run/second-name")
    assert rig.run("--key", "production", "deploy", NEW, "77") == 3
    assert rig.accepted() == [] and "not a regular file owned by root" in rig.journal[0]


def test_a_status_key_file_that_is_not_an_openssh_key_refuses_before_ssh(rig: Rig) -> None:
    rig.production()
    rig.put(deploy.STATUS_KEY_FILE, "not a key\n", hardening.SECRET_MODE)
    assert rig.run("--key", "production", "deploy", NEW, "77") == 2
    assert "is not an OpenSSH private key" in rig.journal[0]
    assert not any(c[0] == "ssh" for c in rig.calls) and rig.accepted() == []


def test_migrate_adds_the_image_contracts_to_the_applied_list(rig: Rig) -> None:
    rig.names[f"{REPO}@{NEW}"] = names(
        "jobs.0000_older", "jobs.0001_x", CONTRACT, contracts=(CONTRACT,)
    )
    rig.put(deploy.APPLIED, "jobs.0000_older\n")
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    assert (rig.root / deploy.APPLIED).read_text() == f"jobs.0000_older\n{CONTRACT}\n"


def accept(rig: Rig, *digests: str) -> None:
    line = "digest={} commit=" + COMMIT + " run=5 staging_checked=20261020T000000Z"
    line += " deployed=20261020T000100Z readyz=200 head=jobs.0002_y contracts=- key=" + FINGERPRINT
    rig.put(deploy.ACCEPTED, "".join(line.format(d) + "\n" for d in digests))


def test_a_rollback_to_an_accepted_digest_skips_staging_and_migrate(rig: Rig) -> None:
    rig.production()
    accept(rig, OLD, NEW)
    rig.serve(f"{REPO}@{NEW}")
    rig.green(f"sha256:{'d' * 64}")  # staging already runs a newer digest: not consulted
    assert rig.run("--key", "production", "rollback", OLD) == 0
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == f"SKIW_IMAGE={REPO}@{OLD}\n"
    assert not any(c[0] == "ssh" or c[-1] in ("migrate", "--plan", "predeploy") for c in rig.calls)
    assert len(rig.accepted()) == 2 and rig.journal[0].endswith(f"rolled back; previous {NEW}")
    assert rig.journal[0].startswith(
        f"rollback {OLD} key production run none fingerprint {FINGERPRINT}: "
    )


def test_the_log_line_names_the_production_key_fingerprint_and_staging_only_its_role(
    rig: Rig,
) -> None:
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    assert rig.journal[0].startswith(f"deploy {NEW} key staging run none: ")  # role only
    assert "fingerprint" not in rig.journal[0]
    rig.journal.clear()
    rig.production()
    assert rig.run("--key", "production", "deploy", NEW, "77") == 0
    assert rig.journal[0].startswith(
        f"deploy {NEW} key production run 77 fingerprint {FINGERPRINT}: "
    )


@pytest.mark.parametrize(
    "case", ["unknown", "staging only", "contract", "staging key", "malformed"]
)
def test_a_rollback_is_refused_outside_the_accepted_record_or_across_a_contract(
    rig: Rig, case: str
) -> None:
    rig.production()
    rig.serve(f"{REPO}@{NEW}")
    accept(rig, *((NEW,) if case == "unknown" else (NEW, OLD)))
    key = "production"
    if case == "staging only":  # staging ran it, production never accepted it
        accept(rig, NEW)
        rig.green(OLD)
    elif case == "contract":  # NEW's migrate applied a contract migration OLD does not ship
        rig.put(deploy.APPLIED, f"{CONTRACT}\n")
    elif case == "staging key":
        key = "staging"
    elif case == "malformed":
        rig.put(deploy.ACCEPTED, (rig.root / deploy.ACCEPTED).read_text() + "garbage\n")
    assert rig.run("--key", key, "rollback", OLD) == 2
    assert rig.running == f"{REPO}@{NEW}" and not any(c[-2:] == ["up", "-d"] for c in rig.calls)


def test_the_staging_status_program_prints_the_last_line_and_whether_it_runs(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = lambda p, i: (0, 0)  # noqa: E731
    assert deploy.status_main(rig.root, owner) == 1  # no status yet: nothing printed
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    capsys.readouterr()
    assert deploy.status_main(rig.root, owner) == 0
    line = capsys.readouterr().out.strip()
    assert deploy.STATUS_LINE.fullmatch(line) and line.endswith("checks=passed running=yes")
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")  # another digest runs now
    assert deploy.status_main(rig.root, owner) == 0
    assert capsys.readouterr().out.strip().endswith("running=no")
    rig.put(deploy.STATUS, "digest=forged checks=passed\n")
    assert deploy.status_main(rig.root, owner) == 1 and capsys.readouterr().out == ""


def test_the_status_call_pins_the_staging_host_key_under_one_alias(rig: Rig) -> None:
    rig.production()
    assert rig.run("--key", "production", "deploy", NEW, "77") == 0
    assert rig.known_hosts == f"{deploy.HOST_ALIAS} {HOST_KEY}\n"
    [ssh] = [c for c in rig.calls if c[0] == "ssh"]
    assert f"HostKeyAlias={deploy.HOST_ALIAS}" in ssh and "HostKeyAlgorithms=ssh-ed25519" in ssh
    assert ssh[ssh.index("-p") + 1] == "2222"


@pytest.mark.parametrize("remove", ["works", "fails"])
def test_a_hanging_pre_migration_dump_is_bounded_and_its_container_removed(
    rig: Rig, remove: str
) -> None:
    rig.put(apply.ENV, (rig.root / apply.ENV).read_text() + "SKIW_DEPLOY_DUMP_TIMEOUT_S=45\n")
    rig.serve(f"{REPO}@{OLD}")
    rig.out["plan"] = (0, A_PLAN)
    rig.out["dump"] = (0, f"predeploy 20261021T101500Z.dump.age {'c' * 64}\n")
    rig.raises = ("predeploy", subprocess.TimeoutExpired("docker", 45))
    if remove == "fails":
        rig.rm_code = 1  # e.g. the daemon did not answer in time
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert ("predeploy", 45) in rig.bounds  # the host value, not a default
    assert not any(c[-1] == "migrate" for c in rig.calls) and rig.at_migrate is None
    assert rig.running == f"{REPO}@{OLD}" and rig.state() == f"SKIW_IMAGE={REPO}@{OLD}\n"
    assert "pre-migration dump timed out" in rig.journal[0] and rig.alerts == []
    if remove == "works":
        assert rig.removed == [deploy.DUMP_NAME] and not rig.dump_running
        assert ("rm", deploy.TOOL_S) in rig.bounds
        assert "its container removed" in rig.journal[0]
        return
    assert rig.dump_running and f"docker rm --force {deploy.DUMP_NAME}" in rig.journal[0]
    rig.journal.clear()  # the next deploy cannot start a second dump beside the first
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert not any(c[-1] == "migrate" for c in rig.calls)


def test_a_migrate_that_fails_halfway_has_its_contracts_recorded_first(rig: Rig) -> None:
    rig.production()
    accept(rig, OLD)
    rig.serve(f"{REPO}@{OLD}")
    rig.names[f"{REPO}@{NEW}"] = names("jobs.0001_x", CONTRACT, contracts=(CONTRACT,))
    rig.out["migrate"] = (1, "")  # applied the contract migration, then a later one failed
    assert rig.run("--key", "production", "deploy", NEW, "77") == 1
    assert rig.at_migrate == f"{CONTRACT}\n"  # on disk before `migrate` started
    assert rig.running == f"{REPO}@{OLD}" and len(rig.accepted()) == 1
    rig.journal.clear()
    rig.names[f"{REPO}@{OLD}"] = names("jobs.0001_x")  # OLD does not ship the contract
    assert rig.run("--key", "production", "rollback", OLD) == 2
    assert "applied contract migrations are not in the target" in rig.journal[0]


@pytest.mark.parametrize("key", ["staging", "production"])
def test_a_deploy_of_an_older_digest_cannot_cross_an_applied_contract(rig: Rig, key: str) -> None:
    if key == "production":
        rig.production()
        rig.green(OLD)  # staging runs OLD: the staging check alone would let it pass
    rig.serve(f"{REPO}@{NEW}")
    rig.put(deploy.APPLIED, f"{CONTRACT}\n")  # NEW's migrate applied a contract migration
    rig.names[f"{REPO}@{OLD}"] = names("jobs.0001_x")  # OLD does not ship it
    assert rig.run("--key", key, "deploy", OLD, "77") == 2
    assert "applied contract migrations are not in the target" in rig.journal[0]
    assert not any(c[-1] in ("migrate", "predeploy") or c[-2:] == ["up", "-d"] for c in rig.calls)
    assert rig.running == f"{REPO}@{NEW}"


@pytest.mark.parametrize(
    "output",
    [
        (0, ""),
        (0, "not json\n"),
        (0, json.dumps(names("jobs.0001_x")) + "\nSystem check identified no issues\n"),
        (0, json.dumps({"head": [], "contracts": []}) + "\n"),  # a key missing
        (0, json.dumps(names("jobs.0001_x") | {"extra": []}) + "\n"),
        (0, json.dumps({"head": ["x.1"], "contracts": [], "migrations": []}) + "\n"),
        (0, json.dumps(names("jobs.0001_x; DROP")) + "\n"),
        (0, b"\xff\xfe"),
        (1, json.dumps(names("jobs.0001_x")) + "\n"),  # printed, then failed
        "timeout",
    ],
)
def test_migration_labels_output_that_is_not_the_one_object_stops_before_migrate(
    rig: Rig, output: object
) -> None:
    rig.serve(f"{REPO}@{OLD}")
    if output == "timeout":
        rig.raises = ("migration_labels", subprocess.TimeoutExpired("docker", deploy.TOOL_S))
    else:
        rig.out["labels"] = output  # type: ignore[assignment]
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert not any(c[-1] == "migrate" or c[-2:] == ["up", "-d"] for c in rig.calls)
    assert rig.running == f"{REPO}@{OLD}" and "failed:" in rig.journal[0]
    assert "DROP" not in rig.journal[0]  # tool output is never shown


@pytest.mark.parametrize(
    "labels", [{deploy.COMMIT_LABEL: 7}, ["not", "a", "map"]], ids=["number", "list"]
)
def test_image_labels_that_are_not_strings_stop_before_migrate(rig: Rig, labels: object) -> None:
    rig.labels[f"{REPO}@{NEW}"] = labels  # type: ignore[assignment]
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert not any(c[-1] == "migrate" for c in rig.calls)


@pytest.mark.parametrize(
    "fault",
    [
        "lsattr fails",
        "lsattr prints a bare flag",
        "lsattr prints another path",
        "lsattr prints two lines",
        "lsattr prints bytes",
        "lsattr hangs",
        "chattr exits 0 but sets nothing",
        "chattr hangs",
    ],
)
def test_the_record_is_refused_unless_lsattr_shows_it_append_only(rig: Rig, fault: str) -> None:
    rig.production()
    flags = "-----a--------e-------"
    path = rig.root / deploy.ACCEPTED
    outputs: dict[str, tuple[int, str | bytes]] = {
        "lsattr fails": (1, ""),
        "lsattr prints a bare flag": (0, "a\n"),
        "lsattr prints another path": (0, f"{flags} /var/lib/skiw/other\n"),
        "lsattr prints two lines": (0, f"{flags} {path}\n{flags} {path}\n"),
        "lsattr prints bytes": (0, b"\xff" + f"a {path}\n".encode()),
    }
    rig.lsattr = outputs.get(fault)
    if fault == "lsattr hangs":
        rig.raises = ("lsattr", subprocess.TimeoutExpired("lsattr", deploy.TOOL_S))
    elif fault == "chattr exits 0 but sets nothing":
        rig.chattr = False
    elif fault == "chattr hangs":
        rig.raises = ("chattr", subprocess.TimeoutExpired("chattr", deploy.TOOL_S))
    assert rig.run("--key", "production", "deploy", NEW, "77") == 2
    assert "cannot be made append-only" in rig.journal[0]
    assert not any(c[0] in ("ssh", "docker", "env") for c in rig.calls)
    assert all(0 < b <= deploy.TOOL_S for kind, b in rig.bounds if kind in ("lsattr", "chattr"))


@pytest.mark.parametrize(
    "content",
    ["garbage\n", "{line}", "{line}\n\n", "{line}\nd\u00e9j\u00e0\n"],
    ids=["garbage", "cut last line", "empty line", "not ascii"],
)
def test_a_malformed_accepted_record_refuses_deploy_and_rollback(rig: Rig, content: str) -> None:
    rig.production()
    accept(rig, OLD)
    line = (rig.root / deploy.ACCEPTED).read_text().strip()
    rig.put(deploy.ACCEPTED, content.format(line=line))
    rig.serve(f"{REPO}@{NEW}")
    for argv in (("deploy", NEW, "77"), ("rollback", OLD)):
        rig.journal.clear()
        assert rig.run("--key", "production", *argv) == 2
        assert rig.journal[0].endswith("holds a line that is not in its format")
    assert not any(c[0] in ("ssh", "docker", "env") for c in rig.calls)


def test_a_rollback_whose_image_commit_differs_from_the_record_is_refused(rig: Rig) -> None:
    rig.production()
    accept(rig, OLD)
    rig.serve(f"{REPO}@{NEW}")
    rig.labels[f"{REPO}@{OLD}"] = {deploy.COMMIT_LABEL: "d" * 40}
    assert rig.run("--key", "production", "rollback", OLD) == 2
    assert rig.running == f"{REPO}@{NEW}" and "commit label" in rig.journal[0]


def test_staging_drops_its_status_line_before_a_switch_that_then_fails(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = lambda p, i: (0, 0)  # noqa: E731
    assert rig.run("--key", "staging", "deploy", NEW) == 0
    assert deploy.status_main(rig.root, owner) == 0
    rig.healthy, rig.registered = set(), True  # the same digest now fails /readyz
    rig.journal.clear()
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert not (rig.root / deploy.STATUS).exists()  # no stale checks=passed for production
    capsys.readouterr()
    assert deploy.status_main(rig.root, owner) == 1 and capsys.readouterr().out == ""


def fd_path(fd: int) -> str:
    if sys.platform == "darwin":
        return fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).rstrip(b"\0").decode()
    return os.readlink(f"/proc/self/fd/{fd}")


def barriers(rig: Rig, monkeypatch: pytest.MonkeyPatch, fail: tuple[str, str] | None) -> list[str]:
    """Record every fsync as `file <rel>` or `dir <rel>`; raise EIO once at `fail`: the fsync of
    that file (`file`) or of its directory right after it (`dir`)."""
    events: list[str] = []
    real = os.fsync
    base = str(rig.root.resolve())

    def fsync(fd: int) -> None:
        kind = "dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        rel = fd_path(fd).removeprefix(base).lstrip("/").removesuffix(".skiw-new")
        events.append(f"{kind} {rel}")
        if fail and not any(e.startswith("FAILED") for e in events):
            target, where = fail
            last = events[-2] if len(events) > 1 else ""
            if (where == "file" and events[-1] == f"file {target}") or (
                where == "dir" and kind == "dir" and last == f"file {target}"
            ):
                events.append("FAILED")
                raise OSError(errno.EIO, "failpoint")
        real(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    rig.journal = JournalLog(events)
    return events


class JournalLog(list[str]):
    """The journal, also marking where the result line falls among the fsync events."""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    def append(self, line: str) -> None:
        self.events.append("result")
        super().append(line)


def test_every_written_file_and_its_directory_are_synced_before_the_result(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.production()
    rig.serve(f"{REPO}@{OLD}")
    events = barriers(rig, monkeypatch, None)
    assert rig.run("--key", "production", "deploy", NEW, "77") == 0
    monkeypatch.undo()
    lib = "var/lib/skiw"
    for rel in (deploy.ACCEPTED, deploy.APPLIED, apply.STATE):
        last = max(i for i, e in enumerate(events) if e == f"file {rel}")
        assert f"dir {lib}" in events[last + 1 :], rel
    assert events.count(f"file {deploy.ACCEPTED}") == 2  # created, then the appended line
    assert events[-1] == "result"
    rig2 = Rig(rig.root.parent / "staging")
    events = barriers(rig2, monkeypatch, None)
    assert rig2.run("--key", "staging", "deploy", NEW) == 0
    last = max(i for i, e in enumerate(events) if e == f"file {deploy.STATUS}")
    assert events[last + 1 :] == [f"dir {lib}", "result"]


@pytest.mark.parametrize(
    ("role", "target", "where", "code"),
    [
        ("staging", deploy.APPLIED, "file", 1),
        ("staging", deploy.APPLIED, "dir", 1),
        ("staging", apply.STATE, "dir", 1),
        ("staging", deploy.STATUS, "file", 1),
        ("staging", deploy.STATUS, "dir", 1),
        ("production", deploy.ACCEPTED, "dir", 1),  # the new, empty record: before the pull
        ("production", deploy.ACCEPTED, "file", 1),
    ],
)
def test_a_failed_sync_never_reports_success(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, role: str, target: str, where: str, code: int
) -> None:
    if role == "production":
        rig.production()
    rig.serve(f"{REPO}@{OLD}")
    events = barriers(rig, monkeypatch, (target, where))
    assert rig.run("--key", role, "deploy", NEW, "77") == code
    monkeypatch.undo()
    assert "FAILED" in events and rig.journal[0].split(": ", 1)[1].startswith("failed: ")
    if target in (deploy.APPLIED, deploy.ACCEPTED):  # nothing ran on the schema, no switch
        assert rig.at_migrate is None and rig.running == f"{REPO}@{OLD}"
    if target in (apply.STATE, deploy.STATUS):  # switched back, alerted, never reported done
        step = "switch" if target == apply.STATE else "staging status line"
        assert rig.alerts == [f"deploy {NEW} failed its {step}; switched back to {OLD}"]
        assert rig.running == f"{REPO}@{OLD}"


def test_a_failed_sync_of_the_accepted_line_exits_3(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.production()
    rig.put(deploy.ACCEPTED, "")  # exists: only the appended line is synced
    rig.append_only = True
    events = barriers(rig, monkeypatch, (deploy.ACCEPTED, "dir"))
    assert rig.run("--key", "production", "deploy", NEW, "77") == 3
    monkeypatch.undo()
    assert "FAILED" in events and rig.running == f"{REPO}@{NEW}"
    assert rig.alerts == [f"deploy {NEW} is running but its accepted-digest line failed"]
