"""The systemd units of skiw-health (plan §3 M1j) and UNI-19, read as files.

Each unit is parsed; the services are oneshot, started only by their timers, hardened, and keep
root only where it is needed. UNI-19 (no cron-by-HTTP): no unit, Compose service or image
healthcheck triggers work over HTTP; the only HTTP the host side makes is skiw-health's read-only
GET /readyz, and the image's own healthcheck reads /healthz inside its container.
"""

import configparser
import re
from pathlib import Path

import pytest

from skiw_host import alert, apply, health

HOST = Path(__file__).resolve().parents[1]
UNITS = HOST / "systemd"
REPO = HOST.parents[1]


def unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=True, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment,method-assign]  # systemd keys keep case
    parser.read_string((UNITS / name).read_text())
    return parser


def test_the_unit_files_are_exactly_the_ones_apply_installs_and_enables() -> None:
    assert sorted(p.name for p in UNITS.iterdir()) == sorted(apply.UNIT_FILES)
    assert {apply.VERBATIM[f"systemd/{n}"] for n in apply.UNIT_FILES} == {
        f"etc/systemd/system/{n}" for n in apply.UNIT_FILES
    }
    assert apply.TIMERS == ("skiw-health.timer", "skiw-hardening.timer")


@pytest.mark.parametrize(
    ("name", "calendar", "delay"),
    [("skiw-health.timer", "*:0/5", "30s"), ("skiw-hardening.timer", "monthly", "1h")],
)
def test_each_timer_is_persistent_with_a_random_delay(name: str, calendar: str, delay: str) -> None:
    timer = unit(name)
    assert dict(timer["Timer"]) == {
        "OnCalendar": calendar,
        "Persistent": "true",
        "RandomizedDelaySec": delay,
    }
    assert timer["Install"]["WantedBy"] == "timers.target"


HARDENED = {
    "Type": "oneshot",
    "NoNewPrivileges": "yes",
    "PrivateTmp": "yes",
    "ProtectHome": "read-only",
    "RestrictSUIDSGID": "yes",
    "LockPersonality": "yes",
    "RestrictRealtime": "yes",
    "SystemCallArchitectures": "native",
    "UMask": "0077",
    "Environment": "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}


@pytest.mark.parametrize(
    ("name", "start"),
    [
        ("skiw-health.service", "/usr/local/sbin/skiw-health"),
        ("skiw-hardening.service", "/usr/local/sbin/skiw-health --hardening"),
    ],
)
def test_each_service_is_a_hardened_oneshot_started_only_by_its_timer(
    name: str, start: str
) -> None:
    service = unit(name)
    assert service["Service"]["ExecStart"] == start
    assert {k: service["Service"].get(k) for k in HARDENED} == HARDENED
    assert "Install" not in service  # never enabled itself: its timer starts it
    assert "User" not in service["Service"]  # root: the reasons are in the unit's header


def test_the_five_minute_service_keeps_one_capability_and_writes_one_directory() -> None:
    service = unit("skiw-health.service")["Service"]
    assert service["CapabilityBoundingSet"] == "CAP_DAC_READ_SEARCH"  # the 0700 dump directory
    assert service["ProtectSystem"] == "strict" and service["ReadWritePaths"] == "/var/lib/skiw"
    for key in ("ProtectKernelTunables", "ProtectControlGroups", "RestrictNamespaces"):
        assert service[key] == "yes"
    assert service["RestrictAddressFamilies"] == "AF_UNIX AF_INET AF_INET6"
    timeout = int(service["TimeoutStartSec"])
    assert timeout < 300  # ends before the next run is due
    tools = 4 * health.TOOL_S + health.PROBE_S  # docker ps, inspect, apt-get, journalctl, /readyz
    assert tools + 2 * alert.SEND_S < timeout  # and one failing send, with room to spare


def test_the_monthly_service_outlasts_check_hardening() -> None:
    service = unit("skiw-hardening.service")["Service"]
    assert service["ProtectSystem"] == "full"  # check-hardening needs unshare, docker and nft
    assert int(service["TimeoutStartSec"]) > health.HARDENING_S + 60


def test_uni_19_no_unit_or_service_is_triggered_over_http() -> None:
    assert not [p for p in UNITS.iterdir() if p.suffix in (".socket", ".path")]
    for path in UNITS.iterdir():
        exec_lines = [x for x in path.read_text().splitlines() if x.startswith("Exec")]
        assert not [x for x in exec_lines if re.search(r"curl|wget|http", x)], path.name
    compose = (HOST / "compose.yml").read_text()
    assert "http" not in compose.lower()  # no healthcheck or command calls a URL
    dockerfile = (REPO / "Dockerfile").read_text()
    urls = re.findall(r"https?://[^'\"\s)]+", dockerfile)
    assert urls == ["http://127.0.0.1:8000/healthz"]  # the image's own read-only liveness probe
    assert health.REQUEST.split("\r\n")[0] == "GET /readyz HTTP/1.1"
    assert health.REQUEST.endswith("\r\n\r\n")  # no body: nothing is asked to change
