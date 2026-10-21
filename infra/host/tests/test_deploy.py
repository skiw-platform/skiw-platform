"""`skiw-deploy` and its forced command `skiw-deploy-ssh` (spec §8.4 H3; plan §3 M1g, first part).

A fake runner stands in for docker (login, pull by digest, image inspect, compose run/up/stop/exec)
and curl, with their documented failure rules: `compose up` recreates web and worker only when the
image changed (an unchanged worker keeps its procrastinate id) and may apply a change and still
exit 1; a bounded command may time out. A fake clock stands in for time. The GHCR token is
generated per test and must reach `docker login` on stdin only, never argv, output or a log.
"""

import fcntl
import json
import os
import re
import stat
import subprocess
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
        self.out = {"plan": (0, NO_PLAN), "dump": (1, ""), "migrate": (0, "")}
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

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        assert self.secret not in " ".join(argv)  # the token never in argv
        code, out = self.answer(argv, stdin)
        return subprocess.CompletedProcess(argv, code, out.encode(), b"")

    def timed(
        self, argv: list[str], stdin: bytes, bound: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.bounds.append((next(a for a in ("curl", "exec", "up", "stop") if a in argv), bound))
        line = " ".join(argv) + stdin.decode()
        if (error := self.raises[1]) and self.raises[0] in line:
            self.calls.append(argv)
            self.raises = ("", None)  # once: the recovery's own commands run normally
            raise error
        if self.slow[0] and self.slow[0] in line:
            self.now += self.slow[1]
        return self.runner(argv, stdin)

    def serve(self, image: str) -> None:
        self.put(apply.STATE, f"SKIW_IMAGE={image}\n")
        self.running, self.worker = image, self.top

    def answer(self, argv: list[str], stdin: bytes) -> tuple[int, str]:
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
            if "inspect" in self.out:
                return self.out["inspect"]
            return (0, json.dumps([argv[-1]]) + "\n") if argv[-1] in self.pulled else (1, "[]\n")
        if argv[0] == "curl":  # no response: exit 7 and %{http_code} 000
            return (0, "200") if self.running in self.healthy else (7, "000")
        if argv[0] == "env" and argv[2:4] == ["docker", "compose"]:
            return self.compose(argv[1].removeprefix("SKIW_IMAGE="), argv[8:], stdin)
        return 127, ""

    def compose(self, image: str, args: list[str], stdin: bytes) -> tuple[int, str]:
        if args[-1] == "--plan":
            return self.out["plan"]
        if args[-1] == "predeploy":
            return self.out["dump"]
        if args[-1] == "migrate":
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
    assert len(rig.calls) == 9 and rig.calls[0][3] == "login" and rig.calls[1][3] == "pull"
    assert rig.calls[3][-1] == "--plan" and rig.calls[4][-1] == "migrate"  # no dump: no plan
    assert rig.calls[6][-2:] == ["up", "-d"] and rig.calls[7][0] == "curl"
    assert not any(Path(c[2]).exists() for c in rig.calls[:2])  # the login config is removed
    assert rig.journal == [f"deploy {NEW} key staging run 42: deployed; previous {OLD}"]
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
    assert [c[-1] for c in rig.calls if c[0] == "env"][-6:-3] == ["--plan", "predeploy", "migrate"]


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
    assert all(0 < bound <= limits[kind] for kind, bound in rig.bounds)  # each probe bounded
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
        ("rollback", OLD),  # M1g-2
    ],
)
def test_a_bad_request_is_refused_and_nothing_runs(rig: Rig, argv: tuple[str, ...]) -> None:
    assert rig.run("--key", "staging", *argv) == 2
    assert rig.calls == [] and not (rig.root / apply.STATE).exists()
    if argv[0] == "deploy":  # unchecked caller input never reaches the log
        assert rig.journal[0].startswith("deploy key staging: refused: the digest is not")


@pytest.mark.parametrize(
    ("key", "values"),
    [
        ("production", {}),  # the production key on staging
        ("production", {"SKIW_ENVIRONMENT": "production"}),  # until the G11 check (M1g-2)
        ("staging", {"SKIW_ENVIRONMENT": "production"}),
        ("staging", {"SKIW_ENVIRONMENT": ""}),
        ("staging", {"SKIW_IMAGE_REPOSITORY": "ghcr.io/someone-else"}),
        ("staging", {"SKIW_IMAGE_REPOSITORY": "docker.io/skiw-platform/skiw-platform"}),
        ("staging", {"SKIW_HOSTNAME": ""}),
        ("staging", {"SKIW_DEPLOY_HEALTH_TIMEOUT_S": "0"}),
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
