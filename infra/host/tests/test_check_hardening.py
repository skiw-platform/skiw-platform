"""`check-hardening` (spec §8.4 H2, H7; plan §3 M1f).

A fake runner answers like the real tools do on Ubuntu 24.04, including how they fail: `sshd -T`
prints one line per value (two `port` lines when a second file adds one), `nft -j` listings carry
handles and dynamic set elements (fixture: real nft 1.0.9 output for env/ci.env), `ss` prints
wildcard, scoped and IPv6 addresses, `systemctl is-enabled` exits 1 when disabled, and an unknown
command exits 127 like a missing tool. A temporary root and a recording owner stand in for the host.
"""

import copy
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from string import Template

import pytest

from skiw_host import apply, hardening

HOST = Path(__file__).resolve().parents[1]
CI_ENV = HOST / "env" / "ci.env"
NFT = json.loads((HOST / "tests/fixtures/nft-ci.json").read_text())
SSHD = (
    "port 2222\nlistenaddress [::]:2222\nlistenaddress 0.0.0.0:2222\nusepam yes\nmaxauthtries 3\n"
    "permitrootlogin no\npasswordauthentication no\nkbdinteractiveauthentication no\n"
)
APT = """APT::Periodic "";
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade "";
Unattended-Upgrade::Allowed-Origins "";
Unattended-Upgrade::Allowed-Origins:: "${distro_id}:${distro_codename}-security";
Unattended-Upgrade::DevRelease "auto";
Unattended-Upgrade::Automatic-Reboot "false";
"""
SS = """LISTEN 0      4096         0.0.0.0:80        0.0.0.0:* users:(("docker-proxy",pid=901,fd=7))
LISTEN 0      4096            [::]:443          [::]:* users:(("docker-proxy",pid=915,fd=7))
LISTEN 0      128                *:2222            *:* users:(("sshd",pid=700,fd=3))
LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:* users:(("systemd-resolve",pid=500,fd=15))
LISTEN 0      128            [::1]:6000         [::]:* users:(("python3",pid=3722,fd=4))
"""


def live_table(
    change: Callable[[list[dict[str, dict[str, object]]]], None] = lambda _: None,
) -> str:
    """The table as the host lists it later: new handles, a set element; `change` alters a rule."""
    listing = copy.deepcopy(NFT)
    for item in listing["nftables"]:
        for body in item.values():
            if "handle" in body:
                body["handle"] += 40
            if body.get("name") == "ssh4":
                body["elem"] = [{"elem": {"val": "192.0.2.9", "expires": 599}}]
    change(listing["nftables"])
    return json.dumps(listing)


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "root"
        self.owners: dict[str, tuple[int, int]] = {}  # path under the root -> uid, gid; else root
        self.put(apply.ENV, CI_ENV.read_text())
        self.put("etc/docker/daemon.json", (HOST / "docker/daemon.json").read_text())
        self.put("etc/sudoers.d/skiw-ops", (HOST / "sudoers.d/skiw-ops").read_text())
        self.put("etc/ssh/sshd_config.d/00-skiw.conf", "Port 2222\n")
        self.put("etc/ssh/sshd_config.d/50-cloud-init.conf", "PasswordAuthentication yes\n")
        self.out = {
            "sshd -T": (0, SSHD),
            "nft -j": (0, live_table()),
            "unshare --net": (0, json.dumps(NFT)),
            "systemctl is-enabled": (0, "enabled\n"),
            "apt-config dump": (0, APT),
            "docker info": (0, '{"LiveRestoreEnabled": true, "LoggingDriver": "journald"}'),
            "ss -H": (0, SS),
            "id skiw-deploy": (0, "skiw-deploy\n"),
            "id skiw-ops": (0, "skiw-ops sudo\n"),
        }
        self.stdin: dict[str, bytes] = {}

    def put(self, rel: str, text: str, mode: int = apply.CONFIG) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)  # it may be read-only
        path.write_text(text)
        os.chmod(path, mode)

    def owner(self, path: Path, info: os.stat_result) -> tuple[int, int]:
        inside = path.is_relative_to(self.root)
        return self.owners.get(str(path.relative_to(self.root)), (0, 0)) if inside else (0, 0)

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        key = f"id {argv[2]}" if argv[0] == "id" else " ".join(argv[:2])
        self.stdin[key] = stdin
        code, out = self.out.get(key, (127, ""))
        return subprocess.CompletedProcess(argv, code, out.encode(), b"")

    def run(self, capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, dict[str, str]]:
        argv = ["--env-file", str(self.root / apply.ENV), "--root", str(self.root), *extra]
        code = hardening.main(argv, self.runner, self.owner)
        out = capsys.readouterr()
        lines = [line.split(" ", 2) for line in out.out.splitlines()]
        return code, {
            name.rstrip(":"): f"{status} {rest[0] if rest else ''}".strip()
            for status, name, *rest in lines
        }


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_a_hardened_host_passes_every_check(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    code, results = rig.run(capsys)
    assert results == dict.fromkeys(hardening.CHECKS, "PASS") and code == 0
    rendered = (HOST / "nftables.conf").read_text()  # the rendered file goes on stdin, unchanged
    assert (
        rig.stdin["unshare --net"]
        == Template(rendered).substitute(apply.host_values(CI_ENV)[0]).encode()
    )


def drop_rule(tables: list[dict[str, dict[str, object]]]) -> None:
    tables.pop()  # the last rule of the forward chain is gone


@pytest.mark.parametrize(
    ("check", "key", "answer"),
    [
        ("sshd", "sshd -T", (0, SSHD + "port 2200\n")),  # a later file adds a second port
        ("sshd", "sshd -T", (0, "port 2200\n" + SSHD)),  # in either order
        (
            "sshd",
            "sshd -T",
            (0, SSHD.replace("passwordauthentication no", "passwordauthentication yes")),
        ),
        ("sshd", "sshd -T", (255, "")),
        ("nftables", "nft -j", (0, live_table(drop_rule))),
        ("nftables", "nft -j", (1, "")),  # no such table
        ("nftables", "nft -j", (0, '{"nftables": [{"metainfo": {}}]}')),
        ("nftables", "unshare --net", (1, "")),
        ("unattended-upgrades", "systemctl is-enabled", (1, "disabled\n")),
        ("unattended-upgrades", "apt-config dump", (0, APT + 'APT::Periodic::Enable "0";\n')),
        ("unattended-upgrades", "apt-config dump", (0, APT.replace('"false"', '"true"'))),
        ("unattended-upgrades", "apt-config dump", (0, "")),
        (
            "docker-daemon",
            "docker info",
            (0, '{"LiveRestoreEnabled": false, "LoggingDriver": "journald"}'),
        ),
        ("docker-daemon", "docker info", (0, '{"LoggingDriver": "journald"}')),
        ("docker-daemon", "docker info", (127, "")),  # no docker CLI
        ("listening-sockets", "ss -H", (0, SS + "LISTEN 0 4096 0.0.0.0:2375 0.0.0.0:*\n")),
        ("listening-sockets", "ss -H", (0, SS + "LISTEN 0 4096 [fe80::1%eth0]:8080 [::]:*\n")),
        ("listening-sockets", "ss -H", (0, SS + "LISTEN 0 4096 garbage\n")),
        ("docker-group", "id skiw-ops", (0, "skiw-ops sudo docker\n")),
        ("docker-group", "id skiw-deploy", (1, "")),  # no such user
    ],
)
def test_each_check_fails_on_a_bad_or_unreadable_answer(
    rig: Rig, capsys: pytest.CaptureFixture[str], check: str, key: str, answer: tuple[int, str]
) -> None:
    rig.out[key] = answer
    code, results = rig.run(capsys)
    assert code == 1 and results.pop(check).startswith("FAIL")
    assert set(results.values()) == {"PASS"}  # only that one


def chmod(rel: str, mode: int) -> Callable[[Rig], None]:
    return lambda rig: os.chmod(rig.root / rel, mode)


def link(rel: str) -> Callable[[Rig], None]:
    def plant(rig: Rig) -> None:
        (rig.root / rel).rename(rig.root / "elsewhere")
        (rig.root / rel).symlink_to(rig.root / "elsewhere")

    return plant


DAEMON = "etc/docker/daemon.json"
EARLY = "etc/ssh/sshd_config.d/0-early.conf"


@pytest.mark.parametrize(
    ("check", "change"),
    [
        (
            "docker-daemon",
            lambda rig: rig.put("etc/docker/daemon.json", '{"hosts": ["tcp://0.0.0.0:2375"]}'),
        ),
        ("stale-files", lambda rig: rig.put("etc/fail2ban/jail.d/skiw.local", "[sshd]\n")),
        (
            "stale-files",
            lambda rig: rig.put("etc/sudoers.d/skiw-old", "skiw-ops ALL=(ALL) NOPASSWD: ALL\n"),
        ),
        (
            "stale-files",
            lambda rig: rig.put(
                "etc/ssh/sshd_config.d/0-early.conf", "PasswordAuthentication yes\n"
            ),
        ),
        ("stale-files", lambda rig: rig.put(apply.PENDING, "etc/nftables.conf\n")),
        (
            "stale-files",
            lambda rig: (rig.put(EARLY, "Port 22\n"), link(EARLY)(rig)),
        ),  # not followed
        ("docker-daemon", link(DAEMON)),
        ("docker-daemon", link("etc/docker")),  # a link on the way to the file
        ("docker-daemon", chmod(DAEMON, 0o666)),
        ("docker-daemon", lambda rig: rig.owners.update({DAEMON: (1000, 0)})),
        ("docker-daemon", lambda rig: rig.put(DAEMON, '{"no-new-privileges": false}')),
    ],
)
def test_each_file_check_fails_on_a_bad_file(
    rig: Rig, capsys: pytest.CaptureFixture[str], check: str, change: Callable[[Rig], None]
) -> None:
    change(rig)
    code, results = rig.run(capsys)
    assert code == 1 and results[check].startswith("FAIL")


@pytest.mark.parametrize("problem", ["port", "owner", "not root"])
def test_it_refuses_a_bad_env_file_or_a_non_root_user(
    rig: Rig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    env = tmp_path / "host.env"
    env.write_text(CI_ENV.read_text() + ("SKIW_SSH_PORT=\n" if problem == "port" else ""))
    argv = ["--env-file", str(env), "--root", str(rig.root)]
    if problem == "owner":

        def owner(path: Path, info: os.stat_result) -> tuple[int, int]:
            return (1000, 0) if path == env else rig.owner(path, info)
    else:
        owner = rig.owner
    if problem == "not root":
        monkeypatch.setattr(os, "geteuid", lambda: 1000)
        argv = argv[:2]
    assert hardening.main(argv, rig.runner, owner) == 2
    assert rig.stdin == {}  # refused before any tool ran


@pytest.mark.parametrize("unsafe", ["link", "writable", "outside"])
def test_an_env_file_in_an_unsafe_place_is_refused_before_any_check_runs(
    rig: Rig, capsys: pytest.CaptureFixture[str], unsafe: str
) -> None:
    env_dir = rig.root / "etc/skiw"
    if unsafe == "link":
        moved = rig.root / "elsewhere"
        env_dir.rename(moved)
        env_dir.symlink_to(moved)
    elif unsafe == "writable":
        env_dir.chmod(0o777)
    argv = ["--env-file", str(rig.root / apply.ENV), "--root", str(rig.root)]
    if unsafe == "outside":
        argv[1] = str(CI_ENV)  # a path that is not under the root it checks
    assert hardening.main(argv, rig.runner, rig.owner) == 2
    assert "refused" in capsys.readouterr().err and not rig.stdin  # no tool was run
