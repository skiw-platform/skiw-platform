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
from secrets import token_urlsafe
from string import Template

import pytest

from skiw_host import apply, hardening
from skiw_host.bootstrap_db import HBA, HBA_MODE, render_hba
from skiw_host.bootstrap_secrets import DIR_MODE
from skiw_host.secrets import INVENTORY, OWNER, Kind

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
SSHD_CONFIG = "Include /etc/ssh/sshd_config.d/*.conf\n# ordinary Ubuntu settings\nUsePAM yes\n"
DOCKER_INFO = {
    "LiveRestoreEnabled": True,
    "LoggingDriver": "journald",
    "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns", "name=no-new-privileges"],
}
EXEC_START = (
    "{ path=/usr/bin/dockerd ; argv[]=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/"
    "containerd.sock ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null)"
    " ; status=0/0 }\n"
)
SS = """LISTEN 0      4096         0.0.0.0:80        0.0.0.0:* users:(("docker-proxy",pid=901,fd=7))
LISTEN 0      4096            [::]:443          [::]:* users:(("docker-proxy",pid=915,fd=7))
LISTEN 0      128                *:2222            *:* users:(("sshd",pid=700,fd=3))
LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:* users:(("systemd-resolve",pid=500,fd=15))
LISTEN 0      128            [::1]:6000         [::]:* users:(("python3",pid=3722,fd=4))
"""


# psql -A -t output of ROLES_QUERY on Postgres 17.11 after roles.sql (captured from the pinned
# image): the predefined pg_* roles, postgres, the six roles, their setting and memberships.
ROLES = (HOST / "tests/fixtures/roles-pg17.txt").read_text()
WEB, DB = "1" * 64, "2" * 64  # `docker ps --no-trunc` ids
COMPOSE = "srv/skiw/compose.yml"


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
        self.put("etc/ssh/sshd_config", SSHD_CONFIG)
        self.put("etc/docker/daemon.json", (HOST / "docker/daemon.json").read_text())
        for rule in ("skiw-ops", "skiw-deploy"):
            self.put(f"etc/sudoers.d/{rule}", (HOST / f"sudoers.d/{rule}").read_text())
        self.put("etc/ssh/sshd_config.d/00-skiw.conf", "Port 2222\n")
        self.put("etc/ssh/sshd_config.d/50-cloud-init.conf", "PasswordAuthentication yes\n")
        self.put(HBA, render_hba(CI_ENV), HBA_MODE)
        self.put(COMPOSE, "services: {}\n")
        self.put(apply.STATE, f"SKIW_IMAGE=ghcr.io/skiw-platform/skiw-platform@sha256:{'3' * 64}\n")
        self.values = []  # generated per run; must never be printed
        for secret in INVENTORY:
            value = token_urlsafe(32)
            line = f"v1:{value}" if secret.kind is Kind.APP_KEY else value
            self.put(f"{hardening.SECRETS}/{secret.name}", f"{line}\n", hardening.SECRET_MODE)
            self.owners[f"{hardening.SECRETS}/{secret.name}"] = (OWNER[secret.name], 0)
            self.values.append(value)
        os.chmod(self.root / hardening.SECRETS, DIR_MODE)
        self.out = {
            "sshd -T": (0, SSHD),
            "nft -j": (0, live_table()),
            "unshare --net": (0, json.dumps(NFT)),
            "systemctl is-enabled": (0, "enabled\n"),
            "apt-config dump": (0, APT),
            "docker info": (0, json.dumps(DOCKER_INFO)),
            "systemctl show": (0, EXEC_START),
            "ss -H": (0, SS),
            "id skiw-deploy": (0, "skiw-deploy\n"),
            "id skiw-ops": (0, "skiw-ops sudo\n"),
            "docker ps": (0, f"{WEB}\n{DB}\n"),
            "docker inspect": (0, self.inspect({"PATH": "/usr/bin", "SKIW_HOSTNAME": "skiw.test"})),
            "psql": (0, ROLES),
        }
        self.stdin: dict[str, bytes] = {}
        self.argv: dict[str, list[str]] = {}

    def put(self, rel: str, text: str, mode: int = apply.CONFIG) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)  # it may be read-only
        path.write_text(text)
        os.chmod(path, mode)

    @staticmethod
    def inspect(env: dict[str, str]) -> str:
        web = {
            "Id": WEB,
            "Name": "/skiw-web-1",
            "Config": {"Env": [f"{k}={v}" for k, v in env.items()]},
        }
        return json.dumps([web, {"Id": DB, "Name": "/skiw-db-1", "Config": {"Env": None}}])

    def owner(self, path: Path, info: os.stat_result) -> tuple[int, int]:
        inside = path.is_relative_to(self.root)
        return self.owners.get(str(path.relative_to(self.root)), (0, 0)) if inside else (0, 0)

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        key = f"id {argv[2]}" if argv[0] == "id" else " ".join(argv[:2])
        key = "psql" if argv[:2] == ["docker", "compose"] else key
        self.stdin[key] = stdin
        self.argv[key] = argv
        code, out = self.out.get(key, (127, ""))
        return subprocess.CompletedProcess(argv, code, out.encode(), b"")

    def run(self, capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, dict[str, str]]:
        argv = ["--env-file", str(self.root / apply.ENV), "--root", str(self.root), *extra]
        argv = (
            argv
            if "--compose-file" in extra
            else [*argv, "--compose-file", str(self.root / COMPOSE)]
        )
        code = hardening.main(argv, self.runner, self.owner)
        out = capsys.readouterr()
        assert not any(value in out.out + out.err for value in self.values)  # UNI-09, always
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
    assert rig.stdin["psql"] == hardening.ROLES_QUERY


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


def apt_with(extra: str) -> tuple[int, str]:
    return 0, APT + extra


@pytest.mark.parametrize(
    ("check", "key", "answer"),
    [
        # named children of the origin lists are origins too (apt-config dump prints them so)
        (
            "unattended-upgrades",
            "apt-config dump",
            apt_with('Unattended-Upgrade::Allowed-Origins::extra "Ubuntu:noble-updates";\n'),
        ),
        (
            "unattended-upgrades",
            "apt-config dump",
            apt_with('Unattended-Upgrade::Origins-Pattern::extra "site=x";\n'),
        ),
        (
            "unattended-upgrades",
            "apt-config dump",
            apt_with('Unattended-Upgrade::Allowed-Origins::1 "x:y";\n'),
        ),
        (
            "unattended-upgrades",
            "apt-config dump",
            apt_with('Unattended-Upgrade::Allowed-Origins "x";\n'),
        ),
        (
            "unattended-upgrades",
            "apt-config dump",
            apt_with("Unattended-Upgrade::Allowed-Origins::broken\n"),
        ),
        # the running daemon, not only daemon.json
        (
            "docker-daemon",
            "docker info",
            (0, json.dumps({**DOCKER_INFO, "SecurityOptions": ["name=cgroupns"]})),
        ),
        (
            "docker-daemon",
            "docker info",
            (0, json.dumps({k: v for k, v in DOCKER_INFO.items() if k != "SecurityOptions"})),
        ),
        (
            "docker-daemon",
            "systemctl show",
            (0, EXEC_START.replace("-H fd://", "-H fd:// -H tcp://127.0.0.1:2375")),
        ),
        (
            "docker-daemon",
            "systemctl show",
            (0, EXEC_START.replace("-H fd://", "--host=tcp://0.0.0.0:2375")),
        ),
        (
            "docker-daemon",
            "systemctl show",
            (0, EXEC_START.replace("-H fd://", "-H fd:// --config-file=/etc/other.json")),
        ),
        ("docker-daemon", "systemctl show", (0, "")),
        ("docker-daemon", "systemctl show", (1, "")),
        (
            "listening-sockets",
            "ss -H",
            (0, SS + 'LISTEN 0 4096 127.0.0.1:2375 0.0.0.0:* users:(("dockerd",pid=800,fd=9))\n'),
        ),
    ],
)
def test_the_running_state_and_the_whole_origin_lists_are_checked(
    rig: Rig, capsys: pytest.CaptureFixture[str], check: str, key: str, answer: tuple[int, str]
) -> None:
    rig.out[key] = answer
    code, results = rig.run(capsys)
    assert code == 1 and results.pop(check).startswith("FAIL")
    assert set(results.values()) == {"PASS"}


SAFE_MATCH = (
    "Match User backup\n    ForceCommand /usr/local/bin/backup-only\n    AllowTcpForwarding no\n"
)


@pytest.mark.parametrize(
    "weak",
    [
        "Match User root\n    PasswordAuthentication yes\n    PermitRootLogin yes\n",
        "Match Address 10.0.0.0/8\n    KbdInteractiveAuthentication yes\n",
        "Match Group staff\n    maxauthtries = 20\n",
        "Match all\nPermitRootLogin prohibit-password\n",  # case and spacing do not hide a key
        # the old name of KbdInteractiveAuthentication: sshd -T still prints no globally while the
        # matching user gets yes (the global answer in the rig stays no, as on a real host)
        "Match User ops\n    ChallengeResponseAuthentication yes\n",
        "Match Address 192.0.2.0/24\nchallengeresponseauthentication=yes\n",
        "Match Group staff\n\tCHALLENGERESPONSEAUTHENTICATION  no\n",
    ],
)
@pytest.mark.parametrize("where", ["etc/ssh/sshd_config.d/90-local.conf", "etc/ssh/sshd_config"])
def test_a_match_block_that_weakens_a_checked_sshd_key_fails_wherever_it_is(
    rig: Rig, capsys: pytest.CaptureFixture[str], weak: str, where: str
) -> None:
    base = SSHD_CONFIG if where.endswith("sshd_config") else ""
    rig.put(where, base + weak)
    code, results = rig.run(capsys)
    assert code == 1 and results["sshd"].startswith("FAIL") and "Match" in results["sshd"] + "Match"


@pytest.mark.parametrize(
    "quoted",
    [
        'Match User ops\n    "PasswordAuthentication" yes\n',
        '"Match" User ops\n    PasswordAuthentication yes\n',
        '"Include" /etc/ssh/unchecked.conf\n',
        'Include "/etc/ssh/unchecked.conf"\n',
        'Match User ops\n    "ChallengeResponseAuthentication" yes\n',
        'Match User ops\n    "KbdInteractiveAuthentication"=yes\n',
        "Match User ops\n    'PasswordAuthentication' yes\n",
        "Match User ops\n    Password\\Authentication yes\n",
    ],
)
@pytest.mark.parametrize("where", ["etc/ssh/sshd_config.d/90-local.conf", "etc/ssh/sshd_config"])
def test_a_quoted_sshd_keyword_fails_wherever_it_is(
    rig: Rig, capsys: pytest.CaptureFixture[str], quoted: str, where: str
) -> None:
    base = SSHD_CONFIG if where.endswith("sshd_config") else ""
    rig.put(where, base + quoted)
    code, results = rig.run(capsys)
    assert code == 1 and results["sshd"].startswith("FAIL")


def test_a_match_block_with_a_forced_command_policy_passes(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.put("etc/ssh/sshd_config.d/90-backup.conf", SAFE_MATCH)
    code, results = rig.run(capsys)
    assert code == 0 and results["sshd"] == "PASS"


@pytest.mark.parametrize(
    "change",
    [
        lambda rig: rig.put("etc/ssh/sshd_config", "Include /etc/ssh/other/*.conf\n"),
        lambda rig: (rig.root / "etc/ssh/sshd_config").unlink(),  # cannot read it: fail closed
        lambda rig: chmod("etc/ssh/sshd_config.d/50-cloud-init.conf", 0o666)(rig),
        lambda rig: rig.owners.update({"etc/ssh/sshd_config": (1000, 0)}),
    ],
)
def test_an_unreadable_or_unchecked_sshd_config_fails_closed(
    rig: Rig, capsys: pytest.CaptureFixture[str], change: Callable[[Rig], None]
) -> None:
    change(rig)
    code, results = rig.run(capsys)
    assert code == 1 and results["sshd"].startswith("FAIL")


KEY = f"{hardening.SECRETS}/field_kek"


@pytest.mark.parametrize(
    ("check", "change"),
    [
        ("secret-store", chmod(KEY, 0o440)),
        ("secret-store", chmod(hardening.SECRETS, 0o755)),
        ("secret-store", lambda rig: rig.owners.update({KEY: (10003, 0)})),
        ("secret-store", lambda rig: rig.owners.update({hardening.SECRETS: (1000, 0)})),
        (
            "secret-store",
            lambda rig: rig.put(f"{hardening.SECRETS}/old_key", "x\n", hardening.SECRET_MODE),
        ),
        ("secret-store", lambda rig: (rig.root / f"{hardening.SECRETS}/ghcr_read_token").unlink()),
        ("secret-store", link(KEY)),
        ("secret-store", link(hardening.SECRETS)),
        ("container-env", link(KEY)),  # never read through a link
        (
            "pg-hba",
            lambda rig: rig.put(HBA, render_hba(CI_ENV) + "host all all all trust\n", HBA_MODE),
        ),
        ("pg-hba", chmod(HBA, 0o666)),
        ("pg-hba", link(HBA)),
        ("role-set", link(COMPOSE)),
        ("role-set", lambda rig: rig.owners.update({COMPOSE: (1000, 0)})),
    ],
)
def test_each_data_check_fails_on_a_bad_file(
    rig: Rig, capsys: pytest.CaptureFixture[str], check: str, change: Callable[[Rig], None]
) -> None:
    change(rig)
    code, results = rig.run(capsys)
    assert code == 1 and results[check].startswith("FAIL")


@pytest.mark.parametrize(
    ("check", "key", "answer"),
    [
        ("container-env", "docker inspect", (0, "[{}]")),
        ("container-env", "docker inspect", (0, "{}")),
        ("container-env", "docker inspect", (1, "")),  # a container stopped after `docker ps`
        ("container-env", "docker inspect", (0, '[{"Name": "/a", "Config": {"Env": null}}]')),
        ("container-env", "docker ps", (1, "")),
        ("container-env", "docker ps", (127, "")),  # no docker CLI
        ("role-set", "psql", (0, ROLES.replace("skiw_app|t|f|f", "skiw_app|t|f|t"))),
        ("role-set", "psql", (0, ROLES + "member|skiw_app|pg_read_all_data|f|t|t\n")),
        ("role-set", "psql", (0, ROLES + "role|16400|skiw_extra|t|f|f|f|f|f|-1\n")),
        ("role-set", "psql", (0, ROLES.replace("f|f|f|2\n", "f|f|f|-1\n"))),
        ("role-set", "psql", (0, "")),
        ("role-set", "psql", (2, "")),
    ],
)
def test_each_data_check_fails_on_a_bad_or_unreadable_answer(
    rig: Rig, capsys: pytest.CaptureFixture[str], check: str, key: str, answer: tuple[int, str]
) -> None:
    rig.out[key] = answer
    code, results = rig.run(capsys)
    assert code == 1 and results.pop(check).startswith("FAIL")
    assert set(results.values()) == {"PASS"}


def test_no_running_container_has_nothing_to_leak(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.out["docker ps"] = (0, "")
    rig.out.pop("docker inspect")  # not called: `docker inspect` with no id exits 1
    assert rig.run(capsys)[1]["container-env"] == "PASS"


def test_a_secret_in_a_container_environment_is_named_never_shown(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    for value in (rig.values[0], f"prefix-{rig.values[-1]}"):  # an app key's base64, a password
        rig.out["docker inspect"] = (0, rig.inspect({"PATH": "/usr/bin", "LEAK": value}))
        code, results = rig.run(capsys)  # run() asserts no value reached stdout or stderr
        assert code == 1 and results["container-env"] == "FAIL a secret value is in skiw-web-1 LEAK"


def test_role_set_fails_without_a_compose_file_under_the_root(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["--env-file", str(rig.root / apply.ENV), "--root", str(rig.root)]
    assert hardening.main(argv, rig.runner, rig.owner) == 0  # default: /srv/skiw/compose.yml
    assert "/srv/skiw/compose.yml" in " ".join(rig.argv["psql"])
    assert str(rig.root / apply.STATE) in rig.argv["psql"]  # SKIW_IMAGE from skiw-deploy
    rig.stdin.clear()
    assert hardening.main(
        [*argv, "--compose-file", "/elsewhere/compose.yml"], rig.runner, rig.owner
    )
    assert "FAIL role-set: needs --compose-file" in capsys.readouterr().out
    (rig.root / apply.STATE).unlink()  # before the first deploy: Compose cannot resolve the image
    assert hardening.main(argv, rig.runner, rig.owner) == 1 and "psql" not in rig.stdin


def test_expected_roles_are_read_from_roles_sql() -> None:
    roles, settings, members, bad = hardening.parse_roles(ROLES)
    want, want_settings, want_members = hardening.expected_roles()
    assert {name: roles[name][1] for name in want} == want and len(want) == 6 and bad == 0
    assert want_settings == settings and want_members == {
        ("skiw_backup", "pg_read_all_data"): ("f", "t", "t")  # PG16+ GRANT defaults
    }
    assert members == {**hardening.BASELINE_MEMBERS, **want_members}  # the native run, exactly


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (  # (a) GRANT pg_write_all_data TO pg_read_all_data (native row)
            "member|pg_monitor|pg_read_all_settings|f|t|t\n",
            "member|pg_monitor|pg_read_all_settings|f|t|t\n"
            "member|pg_read_all_data|pg_write_all_data|f|t|t\n",
            "unexpected membership: pg_read_all_data in pg_write_all_data",
        ),
        (  # (b, c) ... WITH INHERIT FALSE, SET FALSE: backup loses its read access
            "member|skiw_backup|pg_read_all_data|f|t|t",
            "member|skiw_backup|pg_read_all_data|f|f|f",
            "skiw_backup in pg_read_all_data: options differ from the allowed grant: inherit, set",
        ),
        (  # (b) INHERIT FALSE alone
            "member|skiw_backup|pg_read_all_data|f|t|t",
            "member|skiw_backup|pg_read_all_data|f|f|t",
            "skiw_backup in pg_read_all_data: options differ from the allowed grant: inherit",
        ),
        (  # (c) SET FALSE alone
            "member|skiw_backup|pg_read_all_data|f|t|t",
            "member|skiw_backup|pg_read_all_data|f|t|f",
            "skiw_backup in pg_read_all_data: options differ from the allowed grant: set",
        ),
        (  # (d) WITH ADMIN OPTION: backup could delegate its read access
            "member|skiw_backup|pg_read_all_data|f|t|t",
            "member|skiw_backup|pg_read_all_data|t|t|t",
            "skiw_backup in pg_read_all_data: options differ from the allowed grant: admin",
        ),
        (  # (e) a baseline edge with changed options
            "member|pg_monitor|pg_read_all_stats|f|t|t",
            "member|pg_monitor|pg_read_all_stats|f|f|t",
            "pg_monitor in pg_read_all_stats: options differ from the allowed grant: inherit",
        ),
        (  # a baseline edge revoked
            "member|pg_monitor|pg_stat_scan_tables|f|t|t\n",
            "",
            "pg_monitor is not a member of pg_stat_scan_tables",
        ),
        (  # a second grant of the same pair (another grantor)
            "member|skiw_backup|pg_read_all_data|f|t|t\n",
            "member|skiw_backup|pg_read_all_data|f|t|t\nmember|skiw_backup|pg_read_all_data|f|t|t\n",
            "skiw_backup in pg_read_all_data: granted more than once",
        ),
    ],
)
def test_memberships_are_exactly_roles_sql_and_the_baseline_with_their_options(
    rig: Rig, capsys: pytest.CaptureFixture[str], old: str, new: str, problem: str
) -> None:
    assert old in ROLES
    rig.out["psql"] = (0, ROLES.replace(old, new))
    code, results = rig.run(capsys)
    assert code == 1 and results.pop("role-set") == f"FAIL {problem}"
    assert set(results.values()) == {"PASS"}


@pytest.mark.parametrize(
    "rows",
    [
        "role|16400|review_unexpected|t|t|f|f|f|f|-1\n",  # any prefix, LOGIN SUPERUSER
        "role|16401|reports|f|f|f|f|f|f|-1\n",  # NOLOGIN too
        "role|16402|pg_fake|f|f|f|f|f|f|-1\n",  # pg_ but not one of initdb's
        "member|skiw_app|pg_write_all_data|f|t|t\n",
        "member|postgres|skiw_app|f|t|t\n",
        "member|skiw_app|skiw_migrator|f|t|t\n",
        "member|skiw_app|pg_read_all_data\n",  # the pre-PG16 shape, no options: unparsable
        "setting|skiw_app|16384|search_path=other\n",  # per database too
    ],
)
def test_the_whole_role_inventory_is_checked(
    rig: Rig, capsys: pytest.CaptureFixture[str], rows: str
) -> None:
    rig.out["psql"] = (0, ROLES + rows)
    code, results = rig.run(capsys)
    assert code == 1 and results.pop("role-set").startswith("FAIL")
    assert set(results.values()) == {"PASS"}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("role|16385|skiw_app|t|f", "role|16385|skiw_app|t|t"),  # an app role made superuser
        ("role|10|postgres|t|t", "role|10|postgres|t|f"),
        ("role|4200|pg_signal_backend|f", "role|4200|pg_signal_backend|t"),
        ("default_transaction_read_only=on", "default_transaction_read_only=off"),
        ("setting|skiw_backup|0|default_transaction_read_only=on\n", ""),
    ],
)
def test_privilege_and_setting_drift_fails(
    rig: Rig, capsys: pytest.CaptureFixture[str], old: str, new: str
) -> None:
    assert old in ROLES
    rig.out["psql"] = (0, ROLES.replace(old, new))
    assert rig.run(capsys)[1]["role-set"].startswith("FAIL")


@pytest.mark.parametrize(
    "row",
    [
        "setting|skiw_app|0|app.review_secret={}\n",  # native rolconfig shape
        "role|16400|{}|t|f|f|f|f|f|-1\n",
        "member|{}|pg_read_all_data|f|t|t\n",
        "{}\n",  # a malformed row
        "role|16400|x|{}|f\n",
    ],
)
def test_database_content_never_reaches_a_diagnostic(
    rig: Rig, capsys: pytest.CaptureFixture[str], row: str
) -> None:
    value = token_urlsafe(24)
    rig.values.append(value)  # run() asserts it is in neither stdout nor stderr
    rig.out["psql"] = (0, ROLES + row.format(value))
    assert rig.run(capsys)[1]["role-set"].startswith("FAIL")


SHORT = "skiw_app_password"


@pytest.mark.parametrize("leaked", [True, False])
def test_a_short_credential_fails_and_is_still_compared_whole(
    rig: Rig, capsys: pytest.CaptureFixture[str], leaked: bool
) -> None:
    value = token_urlsafe(8)  # 11 characters: below the substring-search minimum
    rig.values.append(value)
    rig.put(f"{hardening.SECRETS}/{SHORT}", f"{value}\n", hardening.SECRET_MODE)
    env = {"PATH": "/usr/bin", "DATABASE_PASSWORD": value if leaked else "other"}
    rig.out["docker inspect"] = (0, rig.inspect(env))
    result = rig.run(capsys)[1]["container-env"]
    assert result.startswith(
        f"FAIL {SHORT} is shorter than 16 characters, so it cannot be searched"
    )
    assert ("skiw-web-1 DATABASE_PASSWORD" in result) is leaked


def test_an_empty_secret_file_fails(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    rig.put(f"{hardening.SECRETS}/{SHORT}", "", hardening.SECRET_MODE)
    assert rig.run(capsys)[1]["container-env"] == f"FAIL {SHORT} is empty"


BAD_ENVS: tuple[object, ...] = (0, False, {}, [1], ["A=1", 2], "A=1")


def item(**fields: object) -> dict[str, object]:
    return {"Id": WEB, "Name": "/skiw-web-1", "Config": {"Env": ["PATH=/usr/bin"]}, **fields}


def db_item(**fields: object) -> dict[str, object]:
    return {**item(Id=DB, Name="/skiw-db-1"), **fields}


@pytest.mark.parametrize(
    "items",
    [
        [item(), item()],  # one id twice, the other missing
        [item(), db_item(Id="3" * 64)],  # a container that was not asked for
        [item()],
        [item(), db_item(Config=None)],
        [item(), db_item(Config=[])],
        [item(), db_item(Name=None)],
        *([item(), db_item(Config={"Env": env})] for env in BAD_ENVS),
        [item(), db_item(Config={})],  # no Env key at all
    ],
)
def test_container_evidence_of_the_wrong_shape_fails(
    rig: Rig, capsys: pytest.CaptureFixture[str], items: list[dict[str, object]]
) -> None:
    rig.out["docker inspect"] = (0, json.dumps(items))
    code, results = rig.run(capsys)
    assert code == 1 and results.pop("container-env").startswith("FAIL")
    assert set(results.values()) == {"PASS"}


@pytest.mark.parametrize("ids", ["a1\nb2\n", f"{WEB}\n{WEB}\n"])
def test_unreadable_container_ids_fail(
    rig: Rig, capsys: pytest.CaptureFixture[str], ids: str
) -> None:
    rig.out["docker ps"] = (0, ids)
    assert rig.run(capsys)[1]["container-env"].startswith("FAIL")


@pytest.mark.parametrize("env", [None, [], ["PATH=/usr/bin", "LANG=C.UTF-8"]])
def test_clean_container_environments_pass(
    rig: Rig, capsys: pytest.CaptureFixture[str], env: list[str] | None
) -> None:
    rig.out["docker inspect"] = (0, json.dumps([item(), db_item(Config={"Env": env})]))
    assert rig.run(capsys)[1]["container-env"] == "PASS"
