"""skiw-health (spec §8.4 H7; plan §3 M1j; UNI-09, UNI-19).

A temporary root stands in for the host: the host env file, /proc files, the dump directory and the
state file are real files there; a recording owner, chown, clock, statvfs and tool runner stand in
for the rest. The tool fakes answer as the tools do: a non-zero exit, a timeout, unparsable output.
The /readyz request and the Telegram channel run against a local TLS fake (conftest
`tls_server`) in their own tests.
"""

import hashlib
import json
import os
import secrets
import socket
import ssl
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pytest

from skiw_host import alert, apply, deploy, hardening, health
from skiw_host.alert import Alert
from skiw_host.health import CHECKS, Probe, Result, State, Track

HOST = Path(__file__).resolve().parents[1]
CI_ENV = HOST / "env" / "ci.env"
START = 1_800_000_000.0
PLANTED = secrets.token_urlsafe(24)  # generated per run; must never reach any output
MEMINFO = "MemTotal: {} kB\nMemAvailable: {} kB\nSwapTotal: {} kB\nSwapFree: {} kB\n"
DUMP_NAME = "20261020T010203Z.dump.age"


def cid(service: str) -> str:
    return hashlib.sha256(service.encode()).hexdigest()


def container(service: str, **state: Any) -> dict[str, Any]:
    labels = {"com.docker.compose.project": "skiw", "com.docker.compose.service": service}
    return {
        "Id": cid(service),
        "Config": {"Labels": labels, "Env": [f"SECRET={PLANTED}"]},
        "State": {"Status": "running", **state},
        "RestartCount": 0,
    }


class Fake:
    """The channel; the weekly heartbeats are kept apart (`beats`) from every other message."""

    def __init__(self) -> None:
        self.sent: list[Alert] = []
        self.beats: list[Alert] = []
        self.error: Exception | None = None
        self.tries = 0

    def send(self, message: Alert) -> None:
        self.tries += 1
        if self.error:
            raise self.error
        (self.beats if message.check == "heartbeat" else self.sent).append(message)


class Rig:
    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp, self.root = tmp, tmp / "root"
        (self.root / "etc/skiw").mkdir(parents=True)
        (self.root / apply.ENV).write_text(CI_ENV.read_text())
        (self.root / "var/lib/skiw").mkdir(parents=True)
        (self.root / "run").mkdir()
        (self.root / "proc").mkdir()
        (self.root / health.LISTS_STAMP).parent.mkdir(parents=True)
        (self.root / health.LISTS_STAMP).write_text("")
        self.lists_age = 0.0  # seconds since the last successful `apt-get update`
        dumps = self.root / apply.BACKUPS
        dumps.mkdir(parents=True, mode=0o700)
        dumps.chmod(0o700)  # mkdir mode is masked by the umask
        self.owners: dict[str, tuple[int, int]] = {apply.BACKUPS: (10003, 10003)}
        self.meminfo(available=50, swap=1000, free=1000)
        self.loadavg("0.50 0.40 0.30 1/200 1234")
        self.clock = START
        self.disks: dict[str, int] = {}  # rel -> % used; absent: 50
        self.inodes: dict[str, int] = {}
        self.missing: set[str] = set()
        self.containers = [container(s) for s in health.SERVICES]
        self.out: dict[str, tuple[int, str] | str] = {"apt-get": (0, ""), "journalctl": (0, "")}
        self.calls: list[list[str]] = []
        self.bounds: list[float] = []
        self.journal: list[str] = []
        self.chowns: list[str] = []
        self.answer: tuple[int, float] | Exception = (200, START + 60 * 86400)
        self.cpus: int | None = 2
        self.fake: Fake | None = None
        monkeypatch.setattr(alert, "channel", lambda values, token, context: self.fake)

    def meminfo(self, total: int = 1000, available: int = 50, swap: int = 0, free: int = 0) -> None:
        text = MEMINFO.format(total * 1000, total * 10 * available, swap, free)  # available: %
        (self.root / "proc/meminfo").write_text(text)

    def loadavg(self, text: str) -> None:
        (self.root / "proc/loadavg").write_text(text)

    def owner(self, path: Path, info: os.stat_result) -> tuple[int, int]:
        inside = path.is_relative_to(self.root)
        return self.owners.get(str(path.relative_to(self.root)), (0, 0)) if inside else (0, 0)

    def chown(self, path: str, uid: int, gid: int) -> None:
        self.chowns.append(Path(path).name)

    def timed(
        self, argv: list[str], stdin: bytes, bound: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        self.bounds.append(bound)
        key = " ".join(argv[:2]) if argv[0] == "docker" else argv[0]
        if key == "docker ps" and key not in self.out:
            answer: tuple[int, str] | str = (0, "".join(f"{c['Id']}\n" for c in self.containers))
        elif key == "docker inspect" and key not in self.out:
            answer = (0, json.dumps(self.containers))
        else:
            answer = self.out[key]
        if isinstance(answer, str):  # "timeout"
            raise subprocess.TimeoutExpired(argv, bound)
        code, text = answer
        return subprocess.CompletedProcess(argv, code, text.encode(), PLANTED.encode())

    def statvfs(self, path: Path) -> os.statvfs_result:
        rel = str(path.relative_to(self.root)).removeprefix(".")
        if rel in self.missing:
            raise FileNotFoundError(2, "No such file or directory")
        used, inodes = self.disks.get(rel, 50) * 10, self.inodes.get(rel, 10) * 10
        fields = (4096, 4096, 1000, 1000 - used, 1000 - used, 1000, 1000 - inodes, 1000, 0, 255)
        return os.statvfs_result(fields, {"f_fsid": health.DISKS.index(rel) + 1})

    def request(self, p: Probe) -> tuple[int, float]:
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def wire(self, p: Probe) -> None:
        stamp = self.clock - self.lists_age
        if (self.root / health.LISTS_STAMP).exists():
            os.utime(self.root / health.LISTS_STAMP, (stamp, stamp))
        p.timed, p.now, p.statvfs = self.timed, lambda: self.clock, self.statvfs
        p.cpus, p.request = lambda: self.cpus, self.request

    def probe(self) -> Probe:
        p = Probe(self.root, "skiw.test", self.owner, State())
        self.wire(p)
        return p

    def check(self, name: str) -> Result:
        return health.judge(self.probe(), CHECKS[name][0])

    def run(self, *extra: str, context: alert.Context = ssl.create_default_context) -> int:
        argv = ["--env-file", str(self.root / apply.ENV), "--root", str(self.root), *extra]
        return health.main(
            argv,
            self.timed,
            self.owner,
            self.chown,
            self.journal.append,
            self.wire,
            context,
        )

    def alerts(self) -> list[str]:
        """The journal without the weekly heartbeat's lines."""
        return [line for line in self.journal if not line.startswith("heartbeat")]

    def alerting(self, channel: str, chat: str) -> None:
        """The host env file's alert settings (the last line of a key wins)."""
        with (self.root / apply.ENV).open("a") as env:
            env.write(f"SKIW_ALERT_CHANNEL={channel}\nSKIW_ALERT_TO={chat}\n")

    def place_token(self, mode: int = 0o400) -> str:
        """A bot token made now, placed as the owner places it (runbook health-alerts.md)."""
        token = f"{secrets.randbelow(9 * 10**9) + 10**9}:{secrets.token_urlsafe(27)}"
        store = self.root / hardening.SECRETS
        store.mkdir(mode=0o700, exist_ok=True)
        store.chmod(0o700)
        (self.root / alert.CREDENTIAL).write_text(f"{token}\n")
        (self.root / alert.CREDENTIAL).chmod(mode)
        return token

    def state(self) -> dict[str, Any]:
        doc: dict[str, Any] = json.loads((self.root / health.STATE).read_text())
        return doc

    def dump(self, name: str, age_s: float = 0) -> None:
        path = self.root / apply.BACKUPS / name
        path.write_text("x")
        os.utime(path, (self.clock - age_s, self.clock - age_s))


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    return Rig(tmp_path, monkeypatch)


def test_a_healthy_host_exits_0_sends_only_its_heartbeat_and_writes_its_state(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.fake = Fake()
    assert rig.run() == 0
    assert rig.fake.sent == [] and rig.alerts() == []
    assert [(a.check, a.value) for a in rig.fake.beats] == [("heartbeat", "12 checks, 0 bad")]
    assert len(CHECKS) == 12 and rig.state()["heartbeat"] == health.week(START)
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == [f"OK {name}" for name in CHECKS]
    state = rig.root / health.STATE
    assert state.stat().st_mode & 0o777 == 0o644 and rig.chowns == ["health.state.skiw-new"]
    assert set(rig.state()["tracks"]) == set(CHECKS)
    assert rig.state()["restarts"] == {c["Id"]: 0 for c in rig.containers}


def set_disk(rel: str, pct: int, kind: str = "space") -> Callable[[Rig], None]:
    return lambda r: (r.disks if kind == "space" else r.inodes).__setitem__(rel, pct)


def set_state(service: str, **state: Any) -> Callable[[Rig], None]:
    def change(r: Rig) -> None:
        r.containers = [
            container(service, **state) if c["Id"] == cid(service) else c for c in r.containers
        ]

    return change


def dumps(*names: tuple[str, float]) -> Callable[[Rig], None]:
    def place(r: Rig) -> None:
        for name, age in names:
            r.dump(name, age)

    return place


def security(line: str) -> Callable[[Rig], None]:
    return lambda r: r.out.__setitem__("apt-get", (0, line))


SECURITY = (
    "Inst libssl3t64 [3.0.13-0ubuntu3.4] (3.0.13-0ubuntu3.5 Ubuntu:24.04/noble-security [amd64])"
)
UPDATES = (
    "Inst tzdata [2025a-0ubuntu0.24.04] (2025b-0ubuntu0.24.04 Ubuntu:24.04/noble-updates [all])"
)
PAIR = ((DUMP_NAME, 0.0), (f"{DUMP_NAME}.sha256", 0.0))


@pytest.mark.parametrize(
    ("name", "change", "bad"),
    [
        ("disk", set_disk("var/lib/docker", 80), True),  # plan: alert at 80 %
        ("disk", set_disk("var/lib/docker", 79), False),
        ("disk", set_disk("", 80, "inodes"), True),
        ("memory", lambda r: r.meminfo(available=14), True),  # >= 15 % free (G-LOAD)
        ("memory", lambda r: r.meminfo(available=15), False),
        ("swap", lambda r: r.meminfo(swap=1000, free=500), True),
        ("swap", lambda r: r.meminfo(swap=1000, free=510), False),
        ("swap", lambda r: r.meminfo(swap=0, free=0), False),  # no swap at all
        ("load", lambda r: r.loadavg("9 9 2.01 1/2 3"), True),  # 15 min, 2 CPUs
        ("load", lambda r: r.loadavg("9 9 2.00 1/2 3"), False),
        ("tls-certificate", lambda r: setattr(r, "answer", (200, START + 13 * 86400 + 60)), True),
        ("tls-certificate", lambda r: setattr(r, "answer", (200, START + 14 * 86400 + 60)), False),
        ("readyz", lambda r: setattr(r, "answer", (503, START + 60 * 86400)), True),
        ("containers", set_state("web", Status="exited"), True),
        ("containers", set_state("db", Health={"Status": "unhealthy"}), True),
        ("containers", set_state("clamav", Health={"Status": "starting"}), True),
        ("containers", set_state("db", Health={"Status": "healthy"}), False),
        ("containers", lambda r: r.containers.pop(), True),  # a service is missing
        ("dump", dumps(*PAIR), False),
        ("dump", dumps(PAIR[0]), True),  # no checksum
        ("dump", dumps(PAIR[1]), True),  # a checksum without its dump
        ("dump", dumps((f".{DUMP_NAME}.tmp", 3601)), True),  # a leftover temporary file
        ("dump", dumps((f".{DUMP_NAME}.tmp", 60)), False),  # a dump being written now
        ("dump", dumps(("notes.txt", 0)), True),
        ("dump", lambda r: (r.root / apply.BACKUPS).chmod(0o755), True),
        ("dump", lambda r: r.owners.pop(apply.BACKUPS), True),  # owned by root, not the backup uid
        ("security-updates", security(SECURITY), True),
        ("security-updates", security(UPDATES), False),
        ("security-updates", lambda r: setattr(r, "lists_age", 48 * 3600 + 1), True),  # LISTS_S
        ("security-updates", lambda r: setattr(r, "lists_age", 48 * 3600), False),
        ("reboot", lambda r: (r.root / "run/reboot-required").write_text(""), True),
    ],
)
def test_each_check_has_its_threshold(
    rig: Rig, name: str, change: Callable[[Rig], Any], bad: bool
) -> None:
    assert rig.check(name).bad is False  # the healthy baseline
    change(rig)
    assert rig.check(name).bad is bad


def test_the_dump_age_is_judged_once_m6_sets_it(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    rig.clock = datetime(2026, 10, 20, 1, 2, 3, tzinfo=UTC).timestamp() + 23 * 3600  # DUMP_NAME
    dumps(*PAIR)(rig)
    assert rig.check("dump") == Result(False, "newest 23 h old")
    monkeypatch.setattr(health, "DUMP_AGE_H", 24)
    assert rig.check("dump").bad is False
    rig.clock += 2 * 3600
    assert rig.check("dump") == Result(True, "newest 25 h old")
    for name in os.listdir(rig.root / apply.BACKUPS):
        os.unlink(rig.root / apply.BACKUPS / name)
    assert rig.check("dump") == Result(True, "no dump yet")


def remove(rel: str) -> Callable[[Rig], None]:
    return lambda r: (r.root / rel).unlink()


def stamp_directory(r: Rig) -> None:
    (r.root / health.LISTS_STAMP).unlink()
    (r.root / health.LISTS_STAMP).mkdir()


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("containers", lambda r: r.out.__setitem__("docker ps", (1, ""))),
        ("containers", lambda r: r.out.__setitem__("docker ps", "timeout")),
        ("containers", lambda r: r.out.__setitem__("docker ps", (0, f"{PLANTED}\n"))),
        ("containers", lambda r: r.out.__setitem__("docker inspect", (0, f"not json {PLANTED}"))),
        ("containers", lambda r: r.out.__setitem__("docker inspect", (0, "[]"))),  # ids differ
        ("containers", set_state("web", Status=f"x {PLANTED}")),
        ("containers", set_state("web", Health={"Status": None})),
        ("security-updates", lambda r: r.out.__setitem__("apt-get", (100, ""))),
        ("security-updates", lambda r: r.out.__setitem__("apt-get", "timeout")),
        ("security-updates", security(f"W: {PLANTED}")),
        ("security-updates", remove(health.LISTS_STAMP)),  # no stamp: not known to be fresh
        ("security-updates", stamp_directory),
        ("check-hardening", lambda r: (r.root / health.HARDENING_STATE).write_text(PLANTED)),
        ("deploy-alert", lambda r: r.out.__setitem__("journalctl", (1, ""))),
        ("deploy-alert", lambda r: r.out.__setitem__("journalctl", (0, f"{PLANTED}\n"))),
        ("deploy-alert", lambda r: r.out.__setitem__("journalctl", (0, '{"__CURSOR": "a b"}\n'))),
        ("memory", lambda r: (r.root / "proc/meminfo").write_text("MemTotal: 10 kB\n")),
        ("memory", lambda r: r.meminfo(total=0)),
        ("swap", lambda r: (r.root / "proc/meminfo").write_text("SwapTotal: 10 kB\n")),
        ("load", lambda r: r.loadavg("garbage")),
        ("load", lambda r: r.loadavg("1 1 nan 1/2 3")),
        ("load", lambda r: setattr(r, "cpus", None)),
        ("disk", lambda r: r.missing.add("srv/skiw")),
        ("readyz", lambda r: setattr(r, "answer", ssl.SSLCertVerificationError(PLANTED))),
        ("tls-certificate", lambda r: setattr(r, "answer", TimeoutError(PLANTED))),
        ("dump", lambda r: os.rmdir(r.root / apply.BACKUPS)),
    ],
)
def test_each_check_fails_closed_without_echoing_tool_output(
    rig: Rig, name: str, change: Callable[[Rig], Any]
) -> None:
    change(rig)
    result = rig.check(name)
    assert result.bad is True and PLANTED not in result.value


def test_every_tool_call_is_bounded(rig: Rig) -> None:
    rig.fake = Fake()
    assert rig.run() == 0
    assert rig.bounds and set(rig.bounds) == {30}  # TOOL_S, as the runbook and the unit budget say
    assert (health.PROBE_S, health.HARDENING_S) == (10, 600)  # the runbook's /readyz and monthly


def test_docker_inspect_is_given_container_ids_only(rig: Rig) -> None:
    rig.out["docker ps"] = (0, "--format={{json .Config.Env}}\n")  # never passed on as a flag
    assert rig.check("containers").bad is True
    assert [c[:2] for c in rig.calls] == [["docker", "ps"]]


def test_pending_security_updates_alert_after_48_hours(rig: Rig) -> None:
    rig.fake = Fake()
    security(SECURITY)(rig)
    assert rig.run() == 1 and rig.fake.sent == []
    rig.clock += 48 * 3600 - 1  # unattended-upgrades had two days
    assert rig.run() == 1 and rig.fake.sent == []
    rig.clock += 1
    assert rig.run() == 1
    assert [(a.check, a.value) for a in rig.fake.sent] == [
        ("security-updates", "1 security updates pending")
    ]


def test_package_lists_not_updated_alert_without_running_apt(rig: Rig) -> None:
    """PR-60 P2: stale lists cannot show a new security update, so they are bad themselves."""
    rig.fake = Fake()
    rig.lists_age = 72 * 3600
    assert rig.check("security-updates") == Result(True, "package lists not updated for 72 h")
    assert rig.calls == []  # apt-get is not asked
    assert rig.run() == 1
    rig.clock += health.UPDATES_S
    assert rig.run() == 1
    assert [(a.check, a.value) for a in rig.fake.sent] == [
        ("security-updates", "package lists not updated for 72 h")
    ]


MONDAY = datetime(2026, 10, 26, tzinfo=UTC).timestamp()  # 00:00 UTC, ISO week 2026-W44


def test_the_heartbeat_week_starts_on_monday_0000_utc() -> None:
    assert (health.HEARTBEAT_WEEKDAY, health.HEARTBEAT_HOUR) == (0, 0)  # 08:00 in Kuala Lumpur
    assert health.week(MONDAY - 1) == "2026-W43"
    assert health.week(MONDAY) == health.week(MONDAY + 7 * 86400 - 1) == "2026-W44"
    assert health.week(datetime(2027, 1, 3, tzinfo=UTC).timestamp()) == "2026-W53"


def test_the_heartbeat_is_sent_on_the_first_run_of_each_week(rig: Rig) -> None:
    rig.fake = Fake()
    rig.clock = MONDAY - 300  # Sunday 23:55
    assert rig.run() == 0 and len(rig.fake.beats) == 1  # the first run ever
    rig.clock = MONDAY
    assert rig.run() == 0 and len(rig.fake.beats) == 2  # a new week
    for _ in range(3):
        rig.clock += 2 * 86400
        assert rig.run() == 0
    assert len(rig.fake.beats) == 2 and rig.state()["heartbeat"] == "2026-W44"
    rig.disks["var/log"] = 95
    rig.clock = MONDAY + 7 * 86400
    assert rig.run() == 1
    assert [b.value for b in rig.fake.beats] == ["12 checks, 0 bad"] * 2 + ["12 checks, 1 bad"]
    assert rig.fake.beats[-1].payload() == {
        "check": "heartbeat",
        "host": rig.fake.beats[-1].host,
        "value": "12 checks, 1 bad",
    }


def test_an_undelivered_heartbeat_is_due_on_every_run_until_delivered(rig: Rig) -> None:
    rig.fake = Fake()
    rig.clock = MONDAY
    rig.fake.error = ConnectionRefusedError()
    for _ in range(2):
        assert rig.run() == 3 and rig.state()["heartbeat"] == ""  # not marked sent
        rig.clock += 300
    assert rig.fake.tries == 2 and rig.state()["owed"] == []  # never queued
    rig.fake.error = None
    assert rig.run() == 0 and len(rig.fake.beats) == 1 and rig.state()["heartbeat"] == "2026-W44"
    rig.clock += 300
    assert rig.run() == 0 and len(rig.fake.beats) == 1


def test_a_week_old_undelivered_heartbeat_is_replaced_by_the_new_weeks(rig: Rig) -> None:
    rig.fake = Fake()
    rig.clock = MONDAY
    assert rig.run() == 0
    rig.fake.error = ConnectionRefusedError()
    rig.clock = MONDAY + 7 * 86400  # W45's heartbeat fails all week
    for _ in range(3):
        assert rig.run() == 3
        rig.clock += 2 * 86400
    rig.fake.error = None
    rig.clock = MONDAY + 14 * 86400 + 600  # W46
    assert rig.run() == 0
    assert len(rig.fake.beats) == 2 and rig.state()["heartbeat"] == "2026-W46"
    assert rig.run() == 0 and len(rig.fake.beats) == 2  # W45's is not sent late


class Sender:
    def __init__(self, ok: bool = True) -> None:
        self.sent: list[str] = []
        self.ok = ok

    def __call__(self, value: str) -> bool:
        self.sent.append(value)
        return self.ok


def test_a_condition_alerts_after_its_grace_reminds_and_recovers_once() -> None:
    track, send, bad, good = Track(), Sender(), Result(True, "web exited"), Result(False, "up")
    t = START
    health.step(track, bad, t, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == []  # one bad run is not enough
    for t in (START + 300, START + 600, START + 900):
        health.step(track, bad, t, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == ["web exited"]  # once, not every run
    health.step(track, bad, START + 300 + 6 * 3600 - 1, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == ["web exited"]  # no reminder before 6 hours
    health.step(track, bad, START + 300 + health.REMINDER_S, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == ["web exited"] * 2  # the reminder
    t = START + 300 + health.REMINDER_S
    health.step(track, good, t + 300, health.GRACE_S, health.RECOVER_S, send)
    assert len(send.sent) == 2  # one good run is not a recovery
    health.step(track, good, t + 600, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent[-1] == "recovered: up" and not track.announced and track.ok_since is None


def test_a_flapping_check_sends_nothing_new() -> None:
    track, send = Track(), Sender()
    for i in range(40):  # bad, ok, bad, ok ... every 5 minutes for over 3 hours
        result = Result(i % 2 == 0, "web exited" if i % 2 == 0 else "up")
        health.step(track, result, START + 300 * i, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == []  # never bad for its grace, so never announced
    track = Track(announced=True, sent=START)
    for i in range(80):  # 6 h 40 min
        result = Result(i % 2 == 0, "web exited" if i % 2 == 0 else "up")
        health.step(track, result, START + 300 * i, health.GRACE_S, health.RECOVER_S, send)
    assert send.sent == ["web exited"]  # only the reminder after REMINDER_S; never `recovered`


def test_an_undelivered_alert_is_tried_again_next_run() -> None:
    track, failing = Track(), Sender(ok=False)
    health.step(track, Result(True, "full"), START, 0, health.RECOVER_S, failing)
    health.step(track, Result(True, "full"), START + 300, 0, health.RECOVER_S, failing)
    assert failing.sent == ["full", "full"] and track.announced is False


def test_runs_share_their_state_through_the_state_file(rig: Rig) -> None:
    rig.fake = Fake()
    set_state("web", Status="exited")(rig)
    assert rig.run() == 1 and rig.fake.sent == []  # bad once: within its grace
    rig.clock += 300
    assert rig.run() == 1 and [a.payload()["value"] for a in rig.fake.sent] == ["web exited"]
    rig.clock += 300
    assert rig.run() == 1 and len(rig.fake.sent) == 1
    rig.containers = [container(s) for s in health.SERVICES]
    for _ in range(2):
        rig.clock += 300
        assert rig.run() == 0
    assert rig.fake.sent[-1].value == "recovered: 5 services up" and len(rig.fake.sent) == 2


def test_restarts_are_events_counted_against_the_last_run(rig: Rig) -> None:
    rig.fake = Fake()
    rig.containers[1]["RestartCount"] = 2
    assert rig.run() == 0
    assert [(a.check, a.value) for a in rig.fake.sent] == [("containers", "restarted: web 2x")]
    assert rig.run() == 0 and len(rig.fake.sent) == 1  # the same count: nothing new
    rig.containers[1]["RestartCount"] = 3
    assert rig.run() == 0 and rig.fake.sent[-1].value == "restarted: web 1x"


def test_deploy_alert_lines_are_counted_never_read(rig: Rig) -> None:
    rig.fake = Fake()
    lines = [{"__CURSOR": f"s=ab;i={i}", "MESSAGE": f"{PLANTED} user@example.com"} for i in (1, 2)]
    rig.out["journalctl"] = (0, "".join(json.dumps(x) + "\n" for x in lines))
    assert rig.run() == 0
    journal = [argv for argv in rig.calls if argv[0] == "journalctl"]
    assert journal[0][-1] == "--since=-1h" and "--identifier=skiw-deploy" in journal[0]
    assert [(a.check, a.value) for a in rig.fake.sent] == [
        ("deploy-alert", "2 skiw-deploy alert lines in the journal")
    ]
    rig.out["journalctl"] = (0, "")
    assert rig.run() == 0 and len(rig.fake.sent) == 1
    assert rig.calls[-1][-1] == "--after-cursor=s=ab;i=2" and rig.state()["cursor"] == "s=ab;i=2"


def test_an_undelivered_event_is_owed_until_delivered_and_owed_events_are_capped(rig: Rig) -> None:
    rig.fake = Fake()
    rig.fake.error = ConnectionRefusedError()
    rig.containers[1]["RestartCount"] = 1
    assert rig.run() == 3
    assert rig.state()["owed"] == [["containers", "restarted: web 1x"]]
    rig.fake.error = None
    assert rig.run() == 0 and [a.value for a in rig.fake.sent] == ["restarted: web 1x"]
    assert rig.state()["owed"] == []
    rig.fake.error = ConnectionRefusedError()
    for count in range(2, 2 + health.OWED_MAX + 5):
        rig.containers[1]["RestartCount"] = count
        assert rig.run() == 3
    assert len(rig.state()["owed"]) == 20  # OWED_MAX


def test_without_a_channel_a_due_alert_goes_to_the_journal_and_exits_3(rig: Rig) -> None:
    (rig.root / "run/reboot-required").write_text("")
    assert rig.run() == 3  # SKIW_ALERT_CHANNEL empty: nothing leaves the host
    host = rig.journal[0].split()[1]
    assert rig.alerts() == [
        f"reboot {host} reboot required",
        "reboot: not sent off the host: no alert channel",
    ]
    assert host.startswith("staging:")
    assert rig.state()["tracks"]["reboot"]["announced"] is False  # due again next run
    assert rig.run() == 3 and len(rig.journal) == 4  # no heartbeat without a channel


def test_a_failing_channel_is_tried_once_per_run(rig: Rig) -> None:
    rig.fake = Fake()
    rig.fake.error = TimeoutError()
    (rig.root / "run/reboot-required").write_text("")
    rig.disks["var/log"] = 95
    assert rig.run() == 3 and rig.fake.tries == 1
    assert sum("not sent off the host" in line for line in rig.journal) == 3  # and the heartbeat


def test_a_bad_check_with_its_alert_delivered_exits_1(rig: Rig) -> None:
    rig.fake = Fake()
    rig.disks["var/log"] = 95
    assert rig.run() == 1
    [sent] = rig.fake.sent
    assert sent.payload() == {
        "check": "disk",
        "host": sent.host,
        "value": "/var/log space 95% used",
    }


def test_no_tool_output_or_secret_reaches_any_output(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.fake = Fake()
    rig.out["apt-get"] = (0, SECURITY.replace("libssl3t64", PLANTED))
    rig.out["journalctl"] = (0, json.dumps({"__CURSOR": "s=1", "MESSAGE": PLANTED}) + "\n")
    rig.containers[0]["RestartCount"] = 1
    set_state("web", Status="exited")(rig)
    for _ in range(3):
        rig.run()
        rig.clock += health.UPDATES_S
    out = capsys.readouterr()
    sent = [json.dumps(a.payload()) for a in rig.fake.sent]
    assert len(sent) >= 3 and all(len(a.payload()) == 3 for a in rig.fake.sent)
    for text in (out.out, out.err, *rig.journal, *sent, (rig.root / health.STATE).read_text()):
        assert PLANTED not in text


def link_state(r: Rig) -> None:
    target = r.tmp / "elsewhere"
    target.write_text("{}")
    (r.root / health.STATE).symlink_to(target)


def hard_link(r: Rig) -> None:
    os.link(r.root / health.STATE, r.tmp / "second-name")


def state_bytes(data: bytes) -> Callable[[Rig], object]:
    return lambda r: (r.root / health.STATE).write_bytes(data)


@pytest.mark.parametrize(
    "spoil",
    [
        link_state,
        hard_link,
        lambda r: r.owners.__setitem__(health.STATE, (1000, 0)),
        lambda r: (r.root / health.STATE).chmod(0o666),
        state_bytes(b"{" * (health.STATE_MAX + 1)),
        state_bytes(b"not json"),
        state_bytes(
            json.dumps({"tracks": {}, "restarts": {}, "cursor": "", "owed": [["x", 1]]}).encode()
        ),
        state_bytes(
            json.dumps({"tracks": {"Disk": {}}, "restarts": {}, "cursor": "", "owed": []}).encode()
        ),
        state_bytes(
            json.dumps({"tracks": {}, "restarts": {"x": 1}, "cursor": "", "owed": []}).encode()
        ),
        state_bytes(
            json.dumps({"tracks": {}, "restarts": {}, "cursor": "a b", "owed": []}).encode()
        ),
    ],
)
def test_an_unsafe_or_unreadable_state_file_is_reported_and_replaced(
    rig: Rig, spoil: Callable[[Rig], object]
) -> None:
    rig.fake = Fake()
    assert rig.run() == 0
    if spoil is not link_state:
        os.chmod(rig.root / health.STATE, 0o644)
    else:
        (rig.root / health.STATE).unlink()
    spoil(rig)
    assert rig.run() == 0
    assert [a.check for a in rig.fake.sent] == ["health-state"]
    state = rig.root / health.STATE
    assert not state.is_symlink() and state.stat().st_nlink == 1 and rig.state()["owed"] == []
    if spoil is link_state:
        assert (rig.tmp / "elsewhere").read_text() == "{}"  # never written through the link


def test_the_state_file_itself_is_checked_as_it_is_opened(tmp_path: Path) -> None:
    """The path check covers the directories; the file is checked on the descriptor opened."""
    parent = tmp_path / "var/lib/skiw"
    parent.mkdir(parents=True)
    state = tmp_path / health.STATE
    good = tmp_path / "good"
    good.write_text("{}")
    good.chmod(0o644)

    def read() -> bytes | None:
        return health.read_state(tmp_path, health.STATE, lambda q, i: (0, 0))

    state.symlink_to(good)  # a valid state file behind a link
    with pytest.raises(OSError):  # O_NOFOLLOW: never followed
        read()
    state.unlink()
    os.mkfifo(state, 0o644)
    state.chmod(0o644)
    with pytest.raises(hardening.Bad):  # not a regular file
        read()


def test_a_state_file_reached_through_a_linked_directory_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "health.state").write_text("{}")
    (elsewhere / "health.state").chmod(0o644)
    (tmp_path / "var/lib").mkdir(parents=True)
    (tmp_path / "var/lib/skiw").symlink_to(elsewhere)
    with pytest.raises(hardening.Bad):
        health.read_state(tmp_path, health.STATE, lambda q, i: (0, 0))


def test_a_state_file_that_cannot_be_written_safely_exits_3(rig: Rig) -> None:
    rig.fake = Fake()
    (rig.root / "var/lib/skiw").chmod(0o777)  # others could swap the file: refused
    assert rig.run() == 3
    assert rig.journal[-1] == f"/{health.STATE} not written (Failed)"
    assert not (rig.root / health.STATE).exists()


def test_the_state_file_is_synced_with_its_directory(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[str] = []
    real_fsync = os.fsync
    monkeypatch.setattr(deploy, "sync_dir", lambda d: synced.append(str(d)))

    def fsync(fd: int) -> None:
        synced.append("file")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    rig.fake = Fake()
    assert rig.run() == 0
    assert synced == ["file", str(rig.root / "var/lib/skiw")]


@pytest.mark.parametrize(
    ("line", "fake"),
    [
        ("SKIW_ENVIRONMENT=dev", None),
        ("SKIW_HOSTNAME=", None),
        ("SKIW_ALERT_CHANNEL=pager", "real"),
    ],
)
def test_a_bad_host_config_refuses_before_any_check(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, line: str, fake: str | None
) -> None:
    if fake:
        monkeypatch.undo()  # the real alert.channel judges the setting
    with (rig.root / apply.ENV).open("a") as env:
        env.write(f"{line}\n")
    assert rig.run() == 2
    assert rig.calls == [] and not (rig.root / health.STATE).exists()
    assert rig.journal[0].startswith("refused, nothing checked:")


@pytest.mark.parametrize(
    ("channel", "chat"),
    [
        ("smtp", "42"),  # SMTP was not built (amendment 2026-10-24)
        ("Telegram", "42"),
        ("", "42"),
        ("telegram", ""),
        ("telegram", "@skiw_alerts"),  # a username: the chat id only
        ("telegram", "42/../x"),
        ("telegram", "1" * 17),
    ],
)
def test_a_bad_alert_setting_refuses_before_any_check(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, channel: str, chat: str
) -> None:
    monkeypatch.undo()  # the real alert.channel
    rig.alerting(channel, chat)
    assert rig.run() == 2 and rig.calls == []
    assert rig.journal[0].startswith("refused, nothing checked: SKIW_ALERT_")


def test_without_a_channel_a_healthy_host_sends_no_heartbeat_and_exits_0(rig: Rig) -> None:
    """Owner decision 2026-10-25: the heartbeat starts when the channel is turned on."""
    rig.clock = MONDAY
    for _ in range(3):
        assert rig.run() == 0
        rig.clock += 7 * 86400
    assert rig.journal == [] and rig.state()["heartbeat"] == ""


def test_a_telegram_channel_without_its_token_runs_the_checks_and_exits_3(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.undo()  # the real alert.channel; the token is read only when a message is sent
    rig.alerting("telegram", "-1001234567890")
    assert rig.run() == 3 and rig.calls
    assert rig.journal[-1] == "heartbeat: not sent off the host (FileNotFoundError)"
    assert rig.state()["heartbeat"] == ""  # due again next run


def test_it_refuses_unless_root(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    assert health.main([], rig.timed, rig.owner, rig.chown, rig.journal.append) == 2
    assert rig.calls == []


def test_the_test_flag_sends_one_alert_and_checks_nothing(rig: Rig) -> None:
    assert rig.run("--test") == 3  # no channel
    rig.fake = Fake()
    assert rig.run("--test") == 0 and [a.check for a in rig.fake.sent] == ["alert-test"]
    assert rig.calls == [] and not (rig.root / health.STATE).exists()


@pytest.mark.parametrize(
    ("answer", "value"),
    [
        (
            (1, f"PASS sshd\nFAIL secret-store: {PLANTED} is missing\nFAIL pg-hba: x\n"),
            "failed: secret-store, pg-hba",
        ),
        ((2, ""), "refused (exit 2)"),
        ((1, f"garbage {PLANTED}"), "exit 1"),
        ((127, ""), "exit 127"),
        ("timeout", "timed out"),
    ],
)
def test_the_monthly_run_writes_its_result_and_the_five_minute_run_alerts_it(
    rig: Rig, answer: tuple[int, str] | str, value: str
) -> None:
    rig.fake = Fake()
    rig.out[health.CHECK_HARDENING] = answer
    assert rig.run("--hardening") == 1
    assert rig.fake.tries == 0  # the monthly run sends nothing itself
    assert rig.calls == [[health.CHECK_HARDENING]] and rig.bounds == [health.HARDENING_S]
    assert (rig.root / health.HARDENING_STATE).stat().st_mode & 0o777 == 0o644
    assert not (rig.root / health.STATE).exists()
    assert rig.run() == 1
    assert [(a.check, a.value) for a in rig.fake.sent] == [("check-hardening", value)]
    assert rig.calls.count([health.CHECK_HARDENING]) == 1  # the 5-minute run only reads it
    assert PLANTED not in (rig.root / health.HARDENING_STATE).read_text()
    rig.out[health.CHECK_HARDENING] = (0, "")
    rig.clock += 30 * 86400
    assert rig.run("--hardening") == 0  # next month
    for _ in range(2):  # ok on two runs: recovered
        rig.clock += 300
        assert rig.run() == 0
    assert rig.fake.sent[-1].value == "recovered: every check passed"


def test_an_undelivered_monthly_alert_is_tried_every_five_minutes_not_next_month(
    rig: Rig,
) -> None:
    """PR-60 P2: the monthly run's result is alerted by the 5-minute run, owed like any check."""
    rig.fake = Fake()
    rig.out[health.CHECK_HARDENING] = (1, "FAIL sshd: x\n")
    assert rig.run("--hardening") == 1
    rig.fake.error = TimeoutError()
    for _ in range(3):
        assert rig.run() == 3 and rig.fake.sent == []
        rig.clock += 300
    rig.fake.error = None
    assert rig.run() == 1
    assert [(a.check, a.value) for a in rig.fake.sent] == [("check-hardening", "failed: sshd")]
    assert rig.calls.count([health.CHECK_HARDENING]) == 1  # run once, by --hardening


def test_the_monthly_result_is_judged_by_its_age_and_read_safely(rig: Rig) -> None:
    assert rig.check("check-hardening") == Result(False, "no monthly run yet")
    rig.out[health.CHECK_HARDENING] = (0, "")
    assert rig.run("--hardening") == 0
    rig.clock += health.HARDENING_AGE_S
    assert rig.check("check-hardening") == Result(False, "every check passed")
    rig.clock += 1  # the monthly timer stopped
    assert rig.check("check-hardening") == Result(True, "the last monthly run is 33 days old")
    result = rig.root / health.HARDENING_STATE
    for doc in (
        {"bad": "no", "value": "every check passed", "at": START},
        {"bad": False, "value": f"x/{PLANTED}", "at": START},
        {"bad": False, "value": "ok", "at": START, "more": 1},
        {"bad": False, "value": "ok", "at": float("nan")},
    ):
        result.write_text(json.dumps(doc))
        assert rig.check("check-hardening") == Result(True, "cannot read the monthly result")
    result.chmod(0o666)
    assert rig.check("check-hardening").value.endswith("is not a root:root 0644 file with one link")


def test_a_monthly_result_that_cannot_be_written_exits_3(rig: Rig) -> None:
    rig.out[health.CHECK_HARDENING] = (0, "")
    (rig.root / "var/lib/skiw").chmod(0o777)
    assert rig.run("--hardening") == 3
    assert rig.journal == [f"/{health.HARDENING_STATE} not written (Failed)"]


def test_only_read_only_tools_run_and_no_http_but_readyz(rig: Rig) -> None:
    """UNI-19: nothing here is reached over HTTP; the checks call these tools only."""
    rig.fake = Fake()
    assert rig.run() == 0
    used = {" ".join(argv[:2]) if argv[0] == "docker" else argv[0] for argv in rig.calls}
    assert used == {"docker ps", "docker inspect", "apt-get", "journalctl"}
    flat = " ".join(" ".join(argv) for argv in rig.calls)
    for word in ("exec", "logs", "psql", "curl", "wget", "http", "compose", "--now", "restart"):
        assert word not in flat.split(), word
    assert "--simulate" in flat and "--identifier=skiw-deploy" in flat
    assert health.REQUEST.startswith("GET /readyz HTTP/1.1\r\n") and health.REQUEST.endswith(
        "\r\n\r\n"
    )


# --- the /readyz request against a local TLS fake standing in for Caddy ----------------------


class Server(Protocol):
    port: int
    handler: Callable[[ssl.SSLSocket], None]

    def client(self) -> ssl.SSLContext: ...

    @property
    def stop(self) -> "Waiter": ...


class Waiter(Protocol):
    def wait(self, timeout: float) -> bool: ...


def caddy(server: Server, reply: bytes | None, seen: list[bytes]) -> None:
    def handle(tls: ssl.SSLSocket) -> None:
        data = b""
        while b"\r\n\r\n" not in data and (chunk := tls.recv(4096)):
            data += chunk
        seen.append(data)
        if reply is None:
            server.stop.wait(30)
            return
        if reply == b"drip":
            while not server.stop.wait(0.3):
                tls.sendall(b"H")
        tls.sendall(reply)

    server.handler = handle


def tls_probe(server: Server, context: alert.Context | None = None) -> Probe:
    p = Probe(Path("/nonexistent"), "skiw.test", lambda path, info: (0, 0), State())
    p.address, p.context = ("127.0.0.1", server.port), context or server.client
    return p


def test_readyz_sends_one_get_and_reads_the_status_and_certificate(tls_server: Server) -> None:
    seen: list[bytes] = []
    caddy(tls_server, b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", seen)
    p = tls_probe(tls_server)
    assert health.judge(p, health.readyz) == Result(False, "status 200")
    certificate = health.judge(p, health.certificate)  # the same request, not a second one
    assert certificate.bad is False and certificate.value.startswith("expires in 29 days")
    assert seen == [health.REQUEST.format("skiw.test").encode()]


@pytest.mark.parametrize(
    ("reply", "value"),
    [
        (b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n", "status 503"),
        (b"SSH-2.0-OpenSSH\r\n", "cannot read the /readyz answer"),
        (b"", "cannot read the /readyz answer"),  # closed without an answer
        (None, "cannot read ("),  # silent: the socket timeout or the deadline ends it
        (b"drip", "cannot read (Deadline)"),  # a byte at a time: only the deadline ends it
    ],
)
def test_readyz_fails_closed(
    tls_server: Server, monkeypatch: pytest.MonkeyPatch, reply: bytes | None, value: str
) -> None:
    monkeypatch.setattr(health, "PROBE_S", 1)
    caddy(tls_server, reply, [])
    start = time.monotonic()
    result = health.judge(tls_probe(tls_server), health.readyz)
    assert result.bad and result.value.startswith(value) and time.monotonic() - start < 5


def test_a_certificate_that_does_not_verify_fails_both_checks(tls_server: Server) -> None:
    seen: list[bytes] = []
    caddy(tls_server, b"HTTP/1.1 200 OK\r\n\r\n", seen)
    p = tls_probe(tls_server, ssl.create_default_context)  # the system CAs do not know it
    for check in (health.readyz, health.certificate):
        assert health.judge(p, check) == Result(True, "cannot read (SSLCertVerificationError)")
    assert seen == []  # the request is never sent over an unverified connection


# --- the Telegram channel, end to end against a local TLS fake standing in for the Bot API ----

CHAT = "-1001234567890"
OK = b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{"ok":true}'
UNAUTHORIZED = b'HTTP/1.1 401 Unauthorized\r\nContent-Length: 12\r\n\r\n{"ok":false}'


def bot_api(
    server: Server, monkeypatch: pytest.MonkeyPatch, rig: Rig, replies: list[bytes | None]
) -> list[tuple[bytes, list[str]]]:
    """api.telegram.org:443 reaches the fake (any other address is refused), which answers with
    `replies[0]` (None: never). Each request is kept with the journal as it was then."""
    real = socket.create_connection

    def connect(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        if tuple(address) != ("api.telegram.org", 443):
            raise ConnectionRefusedError(f"not routed in tests: {address}")
        return real(("127.0.0.1", server.port), *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", connect)
    seen: list[tuple[bytes, list[str]]] = []

    def handle(tls: ssl.SSLSocket) -> None:
        data = b""
        while b"\r\n\r\n" not in data and (chunk := tls.recv(65536)):
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        sizes = [x for x in head.split(b"\r\n") if x.lower().startswith(b"content-length:")]
        while sizes and len(body) < int(sizes[0].split(b":")[1]) and (chunk := tls.recv(65536)):
            body += chunk  # read the whole request: closing on unread data resets the connection
        seen.append((data, list(rig.journal)))
        if (reply := replies[0]) is None:
            server.stop.wait(30)
            return
        tls.sendall(reply)

    server.handler = handle
    return seen


def test_the_channel_is_journaled_first_and_the_token_reaches_no_output(
    rig: Rig,
    tls_server: Server,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.undo()  # the real alert.channel, credential and Telegram transport
    token = rig.place_token()
    rig.alerting("telegram", CHAT)
    replies: list[bytes | None] = [OK]
    seen = bot_api(tls_server, monkeypatch, rig, replies)
    rig.containers[1]["RestartCount"] = 1
    assert rig.run(context=tls_server.client) == 0
    assert len(seen) == 2  # the restart, then the heartbeat
    for (head, journal), check in zip(seen, ("containers", "heartbeat"), strict=True):
        assert head.startswith(f"POST /bot{token}/sendMessage HTTP/1.1\r\n".encode())
        assert journal[-1].startswith(f"{check} staging:")  # journaled before it was sent
    rig.containers[1]["RestartCount"] = 2
    replies[0] = UNAUTHORIZED  # a revoked token
    assert rig.run(context=tls_server.client) == 3
    assert rig.journal[-1] == "containers: not sent off the host (HTTPError 401)"
    out = capfd.readouterr()
    for text in (out.out, out.err, *rig.journal, (rig.root / health.STATE).read_text()):
        assert token.partition(":")[2] not in text and "api.telegram.org" not in text


def test_a_bot_api_that_never_answers_ends_the_run_within_the_bound_with_exit_3(
    rig: Rig, tls_server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.undo()
    monkeypatch.setattr(alert, "SEND_S", 0.5)
    rig.place_token()
    rig.alerting("telegram", CHAT)
    rig.containers[1]["RestartCount"] = 1
    seen = bot_api(tls_server, monkeypatch, rig, [None])
    start = time.monotonic()
    assert rig.run(context=tls_server.client) == 3
    assert time.monotonic() - start < 5 and len(seen) == 1  # the rest wait for the next run
    assert rig.state()["owed"] == [["containers", "restarted: web 1x"]]
    assert rig.journal[-1] == "heartbeat: not sent off the host (Undelivered)"  # Down


@pytest.mark.parametrize("mode", [0o440, 0o600, 0o444])
def test_an_unsafe_token_file_is_not_used_and_the_run_exits_3(
    rig: Rig, tls_server: Server, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    monkeypatch.undo()
    rig.place_token(mode)
    rig.alerting("telegram", CHAT)
    seen = bot_api(tls_server, monkeypatch, rig, [OK])
    assert rig.run(context=tls_server.client) == 3 and seen == []
    assert rig.journal[-1] == "heartbeat: not sent off the host (UnsafeCredential)"
    assert rig.state()["heartbeat"] == ""  # due again next run
