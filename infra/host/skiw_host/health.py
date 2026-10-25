"""`skiw-health` and `skiw-health --hardening` (spec §8.4 H7; plan §3 M1j; runbook
health-alerts.md).

Run as root by skiw-health.timer every 5 minutes, and with --hardening by skiw-hardening.timer once
a month: that run only runs check-hardening and writes its result to hardening.state, and the
5-minute run alerts that result like any check, so an undelivered alert is retried every 5 minutes,
not next month. Read-only on the host except its own state file under /var/lib/skiw. Every check
is one entry in CHECKS and gives ok or bad with one value built here from numbers, service and
check names; a tool that is missing, times out, exits non-zero or prints what cannot be parsed
makes the check bad (fail closed). Tool output, database rows, application logs and secret values
never reach a value: the journal check counts skiw-deploy's alert lines and reads no message. The
only HTTP requests are `GET /readyz` to Caddy on 127.0.0.1 and the alert channel's sendMessage
(UNI-19: nothing here is triggered over HTTP; the timers are the only trigger).

Bounded flapping: a check alerts once it has been bad for its grace time, then reminds every
REMINDER_S while bad, and sends `recovered` once it has been ok for RECOVER_S; a check that flips
between runs sends nothing new. Container restarts and skiw-deploy alert lines are events: sent on
the run they are seen, kept as owed (at most OWED_MAX) until delivered. Once a week, while a
channel is configured, the `heartbeat` message (`N checks, M bad`) is due until delivered, so a
channel that stopped working is noticed by its silence (amendment 2026-10-24, decision 12). Every
alert goes to the journal; off the host only through the alert channel (skiw_host.alert; none while
SKIW_ALERT_CHANNEL is empty).
Exit 0 every check ok and every due message delivered; 1 a check is bad (its due messages
delivered); 2 refused (not root, bad host env file or alert setting: nothing checked); 3 a due
message was not delivered (no channel, or the channel failed) or the state file was not written.
3 wins over 1. --hardening exits 0 passed, 1 failed, 3 its result not written.
"""

import argparse
import json
import math
import os
import re
import socket
import ssl
import stat
import subprocess
import syslog
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from skiw_host import alert, apply
from skiw_host.alert import Alert, Transport
from skiw_host.bootstrap_db import Failed, run_command, settings
from skiw_host.bootstrap_secrets import Chown, Journal, Refused, say
from skiw_host.deploy import HOSTNAME, Deploy, TimedRunner, run_timed, write_state
from skiw_host.hardening import (
    CONTAINER_ID,
    Bad,
    Owner,
    read_file,
    stat_owner,
)
from skiw_host.secrets import BACKUP_UID

STATE = "var/lib/skiw/health.state"
HARDENING_STATE = "var/lib/skiw/hardening.state"
STATE_MAX = 1 << 16
# Thresholds (UNI-02). Disk: plan §3 M1j. Memory: the G-LOAD headroom (>= 15 % free). Load: the
# 15-minute average per CPU. TLS: Caddy renews 30 days before expiry, so 14 days means it failed.
DISK_PCT = 80  # space or inodes used, any of DISKS
MEM_AVAILABLE_PCT = 15  # MemAvailable below this share of MemTotal
SWAP_USED_PCT = 50
LOAD_PER_CPU = 1.0
TLS_DAYS = 14
DUMP_AGE_H: float | None = None  # predeploy dumps only follow migrations; M6 sets the Q34 cadence
DUMP_TMP_S = 3600  # a dump's temporary file older than this is a leftover
UPDATES_S = 48 * 3600  # unattended-upgrades runs daily: pending this long means it is not working
# apt-daily updates the lists once a day (timer 06:00 and 18:00, up to 12 h random delay), so a
# normal gap is at most about 36 h: no successful update for 48 h means it is not working.
LISTS_S = 48 * 3600
# Touched by apt after an `apt-get update` with no failed source (APT::Update::Post-Invoke-Success,
# Ubuntu's update-notifier-common) [A]: missing, the check fails closed.
LISTS_STAMP = "var/lib/apt/periodic/update-success-stamp"
GRACE_S = 240  # bad on two runs in a row (the timer: every 5 minutes)
RECOVER_S = 240  # ok on two runs in a row
REMINDER_S = 6 * 3600
OWED_MAX = 20
TOOL_S = 30  # each tool call; the unit's TimeoutStartSec bounds the whole run
PROBE_S = 10  # the whole /readyz request
HARDENING_S = 600
HARDENING_AGE_S = 33 * 86400  # the monthly timer: 31 days apart at most, plus its random hour
HEARTBEAT_WEEKDAY = 0  # Monday (amendment decision 12)
HEARTBEAT_HOUR = 0  # 00:00 UTC, 08:00 in Kuala Lumpur
CHECK_HARDENING = "/usr/local/sbin/check-hardening"
DISKS = ("", "var/lib/docker", "srv/skiw", "var/log")
SERVICES = ("caddy", "web", "worker", "db", "clamav")  # compose.yml, no profile (a test keeps it)
PROJECT = "skiw"  # compose.yml `name:`
REQUEST = "GET /readyz HTTP/1.1\r\nHost: {}\r\nUser-Agent: skiw-health\r\nConnection: close\r\n\r\n"
HEAD_MAX = 4096
STATUS = re.compile(rb"HTTP/1\.[01] ([1-5][0-9]{2})[ \r]")
WORD = re.compile(r"[a-z]{1,20}")  # docker state and health words shown in a value
DUMP = re.compile(r"([0-9]{8}T[0-9]{6}Z)\.dump\.age")
DUMP_TEMP = re.compile(r"\.[0-9]{8}T[0-9]{6}Z\.dump\.age\.tmp")
CURSOR = re.compile(r"[A-Za-z0-9=;_-]{1,512}")
FAIL_LINE = re.compile(r"FAIL ([a-z][a-z-]{0,40}):")
NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
WEEK = re.compile(r"[0-9]{4}-W[0-9]{2}")
RESULT = re.compile(r"[A-Za-z0-9 ,:()-]{1,200}")  # check_hardening's values
STATE_KEYS = {"tracks", "restarts", "cursor", "owed", "heartbeat"}
RESULT_KEYS = {"bad", "value", "at"}
TRACK_KEYS = {"bad_since", "ok_since", "announced", "sent"}


@dataclass
class Result:
    bad: bool
    value: str
    event: str = ""  # sent on this run, whatever the condition's state


@dataclass
class Track:
    bad_since: float | None = None
    ok_since: float | None = None
    announced: bool = False  # a bad alert was delivered and no recovery since
    sent: float = 0.0


@dataclass
class State:
    tracks: dict[str, Track] = field(default_factory=dict)
    restarts: dict[str, int] = field(default_factory=dict)  # container id -> RestartCount
    cursor: str = ""  # journal cursor after the last skiw-deploy alert line counted
    owed: list[tuple[str, str]] = field(default_factory=list)  # events not yet delivered
    heartbeat: str = ""  # the week (week()) of the last heartbeat delivered


class Probe:
    """What the checks read, each through an injectable wrapper (tests replace them)."""

    def __init__(self, root: Path, hostname: str, owner: Owner, state: State) -> None:
        self.root, self.hostname, self.owner, self.state = root, hostname, owner, state
        self.timed: TimedRunner = run_timed
        self.now: Callable[[], float] = time.time
        self.statvfs: Callable[[Path], os.statvfs_result] = os.statvfs
        self.cpus: Callable[[], int | None] = os.cpu_count
        self.address = ("127.0.0.1", 443)
        self.context: alert.Context = ssl.create_default_context
        self.request: Callable[[Probe], tuple[int, float]] = request
        self.found: dict[str, tuple[Any, Exception | None]] = {}
        self.restarts: dict[str, int] | None = None  # the next baseline, when docker was read
        self.cursor: str | None = None

    def tool(self, argv: list[str], bound: float = TOOL_S) -> str:
        try:
            done = self.timed(argv, b"", bound)
        except subprocess.TimeoutExpired:
            raise Bad(f"`{argv[0]}` timed out") from None
        if done.returncode != 0:  # the output is never shown
            raise Bad(f"`{' '.join(argv[:2])}` exited {done.returncode}")
        return done.stdout.decode("utf-8")

    def once(self, key: str, read: Callable[["Probe"], Any]) -> Any:
        """One read shared by two checks (docker, the TLS request); its failure fails both."""
        if key not in self.found:
            try:
                self.found[key] = (read(self), None)
            except Exception as exc:  # re-raised to each check that asks
                self.found[key] = (None, exc)
        value, error = self.found[key]
        if error is not None:
            raise error
        return value

    def proc(self, rel: str) -> str:
        with (self.root / rel).open("rb") as handle:
            return handle.read(STATE_MAX).decode("ascii")


def disk(p: Probe) -> Result:
    """Space as df counts it (root's reserve counts as used) and inodes, each file system once."""
    seen, full, worst = set(), [], (0, "")
    for rel in DISKS:
        info = p.statvfs(p.root / rel)  # a missing path raises: fail closed
        if info.f_fsid in seen:
            continue
        seen.add(info.f_fsid)
        used = info.f_blocks - info.f_bfree
        space = math.ceil(100 * used / (used + info.f_bavail)) if used + info.f_bavail else 100
        inodes = (
            math.ceil(100 * (info.f_files - info.f_ffree) / info.f_files) if info.f_files else 0
        )
        for kind, pct in (("space", space), ("inodes", inodes)):
            text = f"/{rel} {kind} {pct}% used"
            worst = max(worst, (pct, text))
            if pct >= DISK_PCT:
                full.append(text)
    return Result(bool(full), ", ".join(full) or worst[1])


def meminfo(p: Probe) -> dict[str, int]:
    found = {}
    for line in p.proc("proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        if number := re.fullmatch(r"\s*([0-9]{1,15}) kB", rest):
            found[key] = int(number[1])
    return found


def memory(p: Probe) -> Result:
    info = meminfo(p)
    available = 100 * info["MemAvailable"] // info["MemTotal"]  # missing or zero: fail closed
    return Result(available < MEM_AVAILABLE_PCT, f"{available}% available")


def swap(p: Probe) -> Result:
    info = meminfo(p)
    total, free = info["SwapTotal"], info["SwapFree"]
    if total == 0:
        return Result(False, "no swap")
    used = math.ceil(100 * (total - free) / total)
    return Result(used >= SWAP_USED_PCT, f"{used}% used")


def load(p: Probe) -> Result:
    average, cpus = float(p.proc("proc/loadavg").split()[2]), p.cpus()
    if not cpus or not math.isfinite(average) or average < 0:
        raise Bad("cannot read the load or count the CPUs")
    per_cpu = average / cpus
    return Result(per_cpu > LOAD_PER_CPU, f"{per_cpu:.2f} per CPU (15 min)")


def docker(p: Probe) -> list[dict[str, Any]]:
    label = f"label=com.docker.compose.project={PROJECT}"
    ids = p.tool(["docker", "ps", "--all", "--quiet", "--no-trunc", "--filter", label]).split()
    if not all(CONTAINER_ID.fullmatch(i) for i in ids):
        raise Bad("cannot read `docker ps`")
    if not ids:
        return []
    found = json.loads(p.tool(["docker", "inspect", "--type", "container", *ids]))
    if not isinstance(found, list) or sorted(c["Id"] for c in found) != sorted(ids):
        raise Bad("cannot read `docker inspect`")
    return found


def containers(p: Probe) -> Result:
    """Each service of the stack running and, with a healthcheck, healthy; restarts since the
    last run are an event (the baseline is kept in the state file)."""
    problems, restarted, seen, counts = [], [], set(), {}
    for c in p.once("docker", docker):
        labels = c["Config"]["Labels"] or {}
        service = labels.get("com.docker.compose.service", "")
        if labels.get("com.docker.compose.oneoff") == "True" or service not in SERVICES:
            continue  # `compose run` jobs (migrate, backup) come and go
        seen.add(service)
        status, checked = c["State"]["Status"], c["State"].get("Health")
        health = "healthy" if checked is None else checked["Status"]  # None: no healthcheck
        if not all(isinstance(x, str) and WORD.fullmatch(x) for x in (status, health)):
            raise Bad("cannot read a container state")
        if status != "running":
            problems.append(f"{service} {status}")
        elif health != "healthy":
            problems.append(f"{service} {health}")
        count = c["RestartCount"]
        if not isinstance(count, int) or count < 0:
            raise Bad("cannot read a restart count")
        counts[c["Id"]] = count
        if (more := count - p.state.restarts.get(c["Id"], 0)) > 0:
            restarted.append(f"{service} {more}x")
    problems += [f"{s} missing" for s in SERVICES if s not in seen]
    p.restarts = counts
    event = f"restarted: {', '.join(sorted(restarted))}" if restarted else ""
    return Result(bool(problems), ", ".join(problems) or f"{len(SERVICES)} services up", event)


def request(p: Probe) -> tuple[int, float]:
    """GET /readyz through Caddy on this host, the certificate verified for SKIW_HOSTNAME; the
    status code and the certificate's notAfter. One deadline bounds it all."""
    with (
        alert.deadline(PROBE_S),
        socket.create_connection(p.address, timeout=PROBE_S) as raw,
        p.context().wrap_socket(raw, server_hostname=p.hostname) as tls,
    ):
        cert = tls.getpeercert()
        tls.sendall(REQUEST.format(p.hostname).encode("ascii"))
        head = b""
        while b"\r\n" not in head and len(head) < HEAD_MAX:
            if not (chunk := tls.recv(HEAD_MAX - len(head))):
                break
            head += chunk
    status = STATUS.match(head)
    if not status or not cert or not isinstance(cert.get("notAfter"), str):
        raise Bad("cannot read the /readyz answer")
    return int(status[1]), ssl.cert_time_to_seconds(str(cert["notAfter"]))


def readyz(p: Probe) -> Result:
    code, _ = p.once("request", p.request)
    return Result(code != 200, f"status {code}")


def certificate(p: Probe) -> Result:
    _, not_after = p.once("request", p.request)  # a certificate that fails verification fails here
    days = math.floor((not_after - p.now()) / 86400)
    return Result(days < TLS_DAYS, f"expires in {days} days")


def dump(p: Probe) -> Result:
    """The pre-migration dumps (M1g): the directory as apply made it, each dump with its checksum,
    no leftover temporary file; the age is judged once M6 sets DUMP_AGE_H."""
    path = p.root / apply.BACKUPS
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or p.owner(path, info) != (BACKUP_UID, BACKUP_UID)
        or stat.S_IMODE(info.st_mode) != apply.BACKUP_DIR_MODE
    ):
        return Result(True, "the dump directory is not 0700 and owned by the backup uid")
    names, problems, stamps = set(os.listdir(path)), [], []
    for name in sorted(names):
        if found := DUMP.fullmatch(name):
            stamps.append(found[1])
            if f"{name}.sha256" not in names:
                problems.append(f"{name} has no checksum")
        elif DUMP.fullmatch(name.removesuffix(".sha256")):
            if name.removesuffix(".sha256") not in names:
                problems.append(f"{name} has no dump")
        elif DUMP_TEMP.fullmatch(name):
            if p.now() - (path / name).lstat().st_mtime > DUMP_TMP_S:
                problems.append(f"{name} is left over")
        else:  # its name is never shown
            problems.append("a file that is not a dump")
    value = "no dump yet"
    if stamps:
        taken = datetime.strptime(max(stamps), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()
        age_h = (p.now() - taken) / 3600
        value = f"newest {math.floor(age_h)} h old"
        if DUMP_AGE_H is not None and age_h > DUMP_AGE_H:
            problems.append(value)
    elif DUMP_AGE_H is not None:
        problems.append(value)
    return Result(bool(problems), ", ".join(problems) or value)


def updates(p: Probe) -> Result:
    """Security updates apt would install; no lock taken and no cache written (simulation). Lists
    not updated for LISTS_S cannot show a new update, so they are bad themselves."""
    stamp = (p.root / LISTS_STAMP).lstat()  # missing: fail closed
    if not stat.S_ISREG(stamp.st_mode):
        raise Bad("cannot read the package list stamp")
    if (age := p.now() - stamp.st_mtime) > LISTS_S:
        return Result(True, f"package lists not updated for {math.floor(age / 3600)} h")
    argv = ["apt-get", "--simulate", "--quiet", "--quiet", "-o", "Debug::NoLocking=true"]
    argv += ["-o", "Dir::Cache::pkgcache=", "-o", "Dir::Cache::srcpkgcache=", "dist-upgrade"]
    count = 0
    for line in p.tool(argv).splitlines():
        if not line.startswith(("Inst ", "Conf ", "Remv ")):
            raise Bad("cannot read `apt-get --simulate`")
        count += line.startswith("Inst ") and "-security" in line.partition("(")[2]
    return Result(count > 0, f"{count} security updates pending")


def reboot(p: Probe) -> Result:
    needed = (p.root / "run/reboot-required").exists()  # G15: production never reboots itself
    return Result(needed, "reboot required" if needed else "no reboot required")


def deploy_alerts(p: Probe) -> Result:
    """skiw-deploy's LOG_ALERT lines (a failed switch, M1g), counted; no message is read."""
    since = f"--after-cursor={p.state.cursor}" if p.state.cursor else "--since=-1h"
    argv = ["journalctl", "--quiet", "--no-pager", "--identifier=skiw-deploy", "--priority=alert"]
    argv += ["--output=json", "--output-fields=PRIORITY", since]
    count, cursor = 0, p.state.cursor
    for line in p.tool(argv).splitlines():
        cursor = json.loads(line)["__CURSOR"]
        if not isinstance(cursor, str) or not CURSOR.fullmatch(cursor):
            raise Bad("cannot read the journal")
        count += 1
    p.cursor = cursor
    event = f"{count} skiw-deploy alert lines in the journal" if count else ""
    return Result(False, "journal read", event)


def check_hardening(p: Probe) -> Result:
    """check-hardening's verdict and the names of its failed checks, never their text."""
    try:
        done = p.timed([CHECK_HARDENING], b"", HARDENING_S)
    except subprocess.TimeoutExpired:
        return Result(True, "timed out")
    if done.returncode == 0:
        return Result(False, "every check passed")
    lines = done.stdout.decode("utf-8", "replace").splitlines()
    names = [m[1] for line in lines if (m := FAIL_LINE.match(line))]
    if done.returncode == 1 and names:
        return Result(True, f"failed: {', '.join(names)}")
    return Result(True, "refused (exit 2)" if done.returncode == 2 else f"exit {done.returncode}")


def hardening_result(p: Probe) -> Result:
    """The monthly run's result in hardening.state (written by --hardening only); older than
    HARDENING_AGE_S, the monthly timer stopped."""
    data = read_state(p.root, HARDENING_STATE, p.owner)
    if data is None:
        return Result(False, "no monthly run yet")
    doc = json.loads(data)
    if (
        not isinstance(doc, dict)
        or set(doc) != RESULT_KEYS
        or not isinstance(doc["bad"], bool)
        or not isinstance(doc["value"], str)
        or not RESULT.fullmatch(doc["value"])
        or not number(doc["at"])
    ):
        raise Bad("cannot read the monthly result")
    if (age := p.now() - doc["at"]) > HARDENING_AGE_S:
        return Result(True, f"the last monthly run is {math.floor(age / 86400)} days old")
    return Result(doc["bad"], doc["value"])


Check = tuple[Callable[[Probe], Result], float, float]  # the check, grace, recover time
CHECKS: dict[str, Check] = {
    "disk": (disk, 0, RECOVER_S),
    "memory": (memory, GRACE_S, RECOVER_S),
    "swap": (swap, GRACE_S, RECOVER_S),
    "load": (load, GRACE_S, RECOVER_S),
    "containers": (containers, GRACE_S, RECOVER_S),
    "readyz": (readyz, GRACE_S, RECOVER_S),
    "tls-certificate": (certificate, 0, RECOVER_S),
    "dump": (dump, 0, RECOVER_S),
    "security-updates": (updates, UPDATES_S, RECOVER_S),
    "reboot": (reboot, 0, RECOVER_S),
    "deploy-alert": (deploy_alerts, 0, RECOVER_S),
    "check-hardening": (hardening_result, 0, RECOVER_S),
}


def number(value: object, none: bool = False) -> bool:
    return (value is None and none) or (
        isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    )


def parse(data: bytes) -> State:
    """The state file, checked field by field; anything else raises."""
    doc = json.loads(data)
    if not isinstance(doc, dict) or set(doc) != STATE_KEYS:
        raise ValueError("state keys")
    tracks = {}
    for name, t in doc["tracks"].items():
        if not alert.CHECK.fullmatch(name) or not isinstance(t, dict) or set(t) != TRACK_KEYS:
            raise ValueError("track")
        if not (
            number(t["bad_since"], True)
            and number(t["ok_since"], True)
            and number(t["sent"])
            and isinstance(t["announced"], bool)
        ):
            raise ValueError("track values")
        tracks[name] = Track(**t)
    restarts = doc["restarts"]
    if not isinstance(restarts, dict) or not all(
        CONTAINER_ID.fullmatch(k) and isinstance(v, int) and not isinstance(v, bool) and v >= 0
        for k, v in restarts.items()
    ):
        raise ValueError("restarts")
    cursor, owed, heartbeat = doc["cursor"], doc["owed"], doc["heartbeat"]
    if not isinstance(cursor, str) or (cursor and not CURSOR.fullmatch(cursor)):
        raise ValueError("cursor")
    if not isinstance(heartbeat, str) or (heartbeat and not WEEK.fullmatch(heartbeat)):
        raise ValueError("heartbeat")
    if not isinstance(owed, list) or len(owed) > OWED_MAX:
        raise ValueError("owed")
    pairs = []
    for item in owed:
        if not (
            isinstance(item, list) and len(item) == 2 and all(isinstance(x, str) for x in item)
        ):
            raise ValueError("owed item")
        if not alert.CHECK.fullmatch(item[0]):
            raise ValueError("owed check")
        pairs.append((item[0], item[1]))
    return State(tracks, restarts, cursor, pairs, heartbeat)


def read_state(root: Path, rel: str, owner: Owner) -> bytes | None:
    """None when there is none yet; Bad when it is not a regular root:root 0644 file with one
    link, reached through no link and no writable directory."""
    try:
        apply.untrusted(root, [rel], lambda q: owner(q, q.lstat()))
    except Refused as exc:
        raise Bad(str(exc)) from None
    path = root / rel
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or owner(path, info) != apply.ROOT
            or stat.S_IMODE(info.st_mode) != apply.CONFIG
            or info.st_nlink != 1
            or info.st_size > STATE_MAX
        ):
            raise Bad(f"/{rel} is not a root:root 0644 file with one link")
        data = os.read(fd, STATE_MAX + 1)
        if len(data) > STATE_MAX:
            raise Bad(f"/{rel} is too large")
        return data
    finally:
        os.close(fd)


def step(
    t: Track, r: Result, now: float, grace: float, recover: float, send: Callable[[str], bool]
) -> None:
    """Bounded flapping: alert after `grace`, remind every REMINDER_S, recover after `recover`."""
    if r.bad:
        t.ok_since = None
        t.bad_since = now if t.bad_since is None else t.bad_since
        first = not t.announced and now - t.bad_since >= grace
        if (first or (t.announced and now - t.sent >= REMINDER_S)) and send(r.value):
            t.announced, t.sent = True, now
        return
    t.bad_since = None
    if not t.announced:
        t.ok_since = None
        return
    t.ok_since = now if t.ok_since is None else t.ok_since
    if now - t.ok_since >= recover and send(f"recovered: {r.value}"):
        t.announced, t.ok_since = False, None


class Down:
    """The channel after its first failure in this run: the rest wait for the next run, so one
    run never waits on a failing channel more than once."""

    def send(self, message: Alert) -> None:
        raise alert.Undelivered


def week(now: float) -> str:
    """The heartbeat week of `now`: the ISO week of the time since the last HEARTBEAT_WEEKDAY,
    HEARTBEAT_HOUR UTC (for Monday 00:00, the ISO week itself)."""
    shifted = datetime.fromtimestamp(now, UTC) - timedelta(
        days=HEARTBEAT_WEEKDAY, hours=HEARTBEAT_HOUR
    )
    year, number, _ = shifted.isocalendar()
    return f"{year}-W{number:02d}"


def judge(p: Probe, check: Callable[[Probe], Result]) -> Result:
    """A check that raises is bad (fail closed), shown by its own message or its type only."""
    try:
        return check(p)
    except Bad as exc:  # value-free by construction
        return Result(True, str(exc))
    except Exception as exc:  # unparsable output, a missing file: the type only
        return Result(True, f"cannot read ({type(exc).__name__})")


def evaluate(
    p: Probe, checks: dict[str, Check], host: str, transport: Transport | None, journal: Journal
) -> tuple[bool, bool]:
    """Runs every check and sends what is due; (any check bad, every due message delivered)."""
    now, state = p.now(), p.state
    channel: list[Transport | None] = [transport]
    undelivered = []

    def send(check: str, value: str) -> bool:
        delivered = alert.deliver(Alert(check, host, value), channel[0], journal)
        if not delivered:
            undelivered.append(check)
            channel[0] = channel[0] and Down()
        return delivered

    owed, state.owed = state.owed, []
    state.owed = [(c, v) for c, v in owed if not send(c, v)]
    bad = 0
    for name, (check, grace, recover) in checks.items():
        result = judge(p, check)
        bad += result.bad
        print(f"{'BAD' if result.bad else 'OK'} {name}: {result.value}")
        if result.event and not send(name, result.event):
            state.owed.append((name, result.event))
        track = state.tracks.setdefault(name, Track())
        step(track, result, now, grace, recover, partial(send, name))
    # Not an owed message: due on every run of a week until delivered, so a week's undelivered
    # heartbeat is replaced by the next week's, never sent twice. Only with a channel configured
    # (owner decision 2026-10-25): with none there is nothing to prove alive.
    has_channel = transport is not None
    due = has_channel and (current := week(now)) != state.heartbeat
    if due and send("heartbeat", f"{len(checks)} checks, {bad} bad"):
        state.heartbeat = current
    state.owed = state.owed[-OWED_MAX:]
    state.tracks = {n: t for n, t in state.tracks.items() if n in checks}
    state.restarts = state.restarts if p.restarts is None else p.restarts
    state.cursor = state.cursor if p.cursor is None else p.cursor
    return bad > 0, not undelivered


def to_alert(message: str) -> None:
    syslog.openlog("skiw-health")
    syslog.syslog(syslog.LOG_ALERT, message)


def encode(state: State) -> bytes:
    doc = {**asdict(state), "owed": [list(x) for x in state.owed]}
    return json.dumps(doc, sort_keys=True).encode("ascii")


def main(
    argv: Sequence[str] | None = None,
    timed: TimedRunner = run_timed,
    owner: Owner = stat_owner,
    chown: Chown = os.chown,
    journal: Journal = to_alert,
    probe: Callable[[Probe], None] = lambda p: None,  # tests: replace the probe's wrappers
    context: alert.Context = ssl.create_default_context,
) -> int:
    parser = argparse.ArgumentParser(prog="skiw-health", description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("/") / apply.ENV)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hardening", action="store_true", help="run check-hardening (monthly)")
    mode.add_argument("--test", action="store_true", help="send one test alert, check nothing")
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    root = args.root
    try:
        if root == Path("/") and os.geteuid() != 0:
            raise Refused("run it as root")
        if not args.env_file.is_relative_to(root):
            raise Refused(f"{args.env_file} is not under {root}")
        rel = str(args.env_file.relative_to(root))
        apply.untrusted(root, [rel], lambda q: owner(q, q.lstat()))
        values = settings(args.env_file, read_file(args.env_file, owner).decode("utf-8"))
        environment, hostname = values.get("SKIW_ENVIRONMENT", ""), values.get("SKIW_HOSTNAME", "")
        if environment not in ("production", "staging") or not HOSTNAME.fullmatch(hostname):
            raise Refused("SKIW_ENVIRONMENT or SKIW_HOSTNAME in the host env file is invalid")
        node = os.uname().nodename
        host = f"{environment}:{node if NODE.fullmatch(node) else 'unknown'}"
        deploy = Deploy(root, run_command, owner, chown)
        transport = alert.channel(values, partial(alert.credential, root, owner), context)
    except (Refused, Bad, OSError, UnicodeError) as exc:
        text = f"{exc.strerror} {exc.filename}" if isinstance(exc, OSError) else str(exc)
        journal(f"refused, nothing checked: {text}")
        say(f"skiw-health: refused, nothing checked: {text}")
        return 2
    if args.test:
        return 0 if alert.deliver(Alert("alert-test", host, "a test"), transport, journal) else 3
    if args.hardening:
        return monthly(deploy, root, hostname, owner, timed, journal, probe)
    state, broken = State(), False
    try:
        if (data := read_state(root, STATE, owner)) is not None:
            state = parse(data)
    except Exception:  # unsafe or unreadable: started fresh, rewritten below, reported
        state, broken = State(), True
    p = Probe(root, hostname, owner, state)
    p.timed = timed
    probe(p)
    any_bad, delivered = evaluate(p, CHECKS, host, transport, journal)
    if broken:
        message = Alert("health-state", host, f"/{STATE} was unreadable or unsafe; started fresh")
        delivered &= alert.deliver(message, transport, journal)
    try:
        write_state(deploy, encode(state), STATE)
    except (Failed, OSError) as exc:
        journal(f"/{STATE} not written ({type(exc).__name__})")
        delivered = False
    return 3 if not delivered else 1 if any_bad else 0


def monthly(
    deploy: Deploy,
    root: Path,
    hostname: str,
    owner: Owner,
    timed: TimedRunner,
    journal: Journal,
    probe: Callable[[Probe], None],
) -> int:
    """--hardening: check-hardening once, its result written for the 5-minute run to alert."""
    p = Probe(root, hostname, owner, State())
    p.timed = timed
    probe(p)
    result = judge(p, check_hardening)
    print(f"{'BAD' if result.bad else 'OK'} check-hardening: {result.value}")
    doc = {"bad": result.bad, "value": result.value[: alert.VALUE_MAX], "at": p.now()}
    try:
        write_state(deploy, json.dumps(doc, sort_keys=True).encode("ascii"), HARDENING_STATE)
    except (Failed, OSError) as exc:
        journal(f"/{HARDENING_STATE} not written ({type(exc).__name__})")
        return 3
    return 1 if result.bad else 0
