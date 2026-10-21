"""`skiw-deploy` and its forced command `skiw-deploy-ssh` (spec §8.4 H3; plan §3 M1g, first part).

A fake runner stands in for docker (login, pull by digest, image inspect, compose run/up/stop/exec)
and curl, with their documented failure rules; a fake clock stands in for time. The GHCR token is
generated per test and must reach `docker login` on stdin only, never argv, output or a log.
"""

import fcntl
import json
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from secrets import token_urlsafe

import pytest

from skiw_host import apply, deploy, hardening

HOST = Path(__file__).resolve().parents[1]
REPO = "ghcr.io/charliekhc/skiw-platform"
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
        self.out = {"plan": (0, NO_PLAN), "dump": (1, ""), "migrate": (0, ""), "up": (0, "")}
        self.workers, self.registered = 4, True
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
            self.running = image if self.out["up"][0] == 0 else self.running
            return self.out["up"]
        if args == ["stop", "web", "worker"]:
            self.running = None
            return 0, ""
        if args[:3] == ["exec", "-T", "db"]:
            if b"max(id)" in stdin:
                return 0, f"{self.workers}\n"
            return 0, "1\n" if self.registered and self.running else "0\n"
        return 1, ""

    def run(self, *argv: str) -> int:
        d = deploy.Deploy(self.root, self.runner, lambda p, i: (0, 0), lambda p, u, g: None)
        d.clock, d.sleep = lambda: self.now, self.tick
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
    rig.put(apply.STATE, f"SKIW_IMAGE={REPO}@{OLD}\n")
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


def test_a_first_deploy_that_fails_its_health_check_stops_web_and_worker(rig: Rig) -> None:
    rig.healthy = set()
    assert rig.run("--key", "staging", "deploy", NEW) == 1
    assert rig.running is None and rig.alerts and "web and worker stopped" in rig.alerts[0]


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
        ("staging", {"SKIW_IMAGE_REPOSITORY": "docker.io/charliekhc/skiw-platform"}),
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
