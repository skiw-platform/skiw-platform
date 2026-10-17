"""`apply` (spec §8.4 H1, H2, H4, H7; plan §3 M1f, first part).

A fake runner stands in for every system command (checkers, gpg, users, apt, systemctl) and keeps
the users and packages it "made"; a temporary root, a recording chown and owner stand in for the
host.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from skiw_host import apply
from skiw_host.apply import main
from skiw_host.bootstrap_secrets import Refused

HOST = Path(__file__).resolve().parents[1]
CI_ENV = HOST / "env" / "ci.env"
DAEMON = {"live-restore": True, "no-new-privileges": True, "log-driver": "journald"}
PINNED = {
    "docker-ce=5:29.9.1-1~ubuntu.24.04~noble",
    "docker-ce-cli=5:29.9.1-1~ubuntu.24.04~noble",
    "docker-compose-plugin=5.6.0-1~ubuntu.24.04~noble",
}
KEY = (
    f"pub:-:4096:1:8D81803C0EBFCD88:::\nfpr:::::::::{apply.DOCKER_FINGERPRINT}:\nsub:-:4096:1::::\n"
)
RULE = "/usr/local/sbin/bootstrap-secrets restore --env-file /etc/skiw/host.env"


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.root = tmp / "root"
        (self.root / "etc/apt/keyrings").mkdir(parents=True)
        (self.root / apply.DOCKER_KEY).write_text("Docker's public key\n")
        self.gpg = KEY
        self.users: dict[str, list[str]] = {}
        self.packages: set[str] = set()
        self.calls: list[list[str]] = []
        self.chowns: dict[str, tuple[int, int]] = {}
        self.owners: dict[str, tuple[int, int]] = {}  # destination -> uid, gid; absent is root
        self.fail = ""  # the start of the command line that fails
        self.modes: dict[str, int] = {}  # checker -> mode of the candidate it was given

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        code, out = int(bool(self.fail) and " ".join(argv).startswith(self.fail)), ""
        if tuple(argv[:-1]) in apply.CHECKERS.values():
            self.modes[argv[0]] = Path(argv[-1]).stat().st_mode & 0o777
        elif argv[0] == "gpg":
            out = self.gpg
        elif argv[:2] == ["id", "-u"]:
            code = int(argv[2] not in self.users)
        elif argv[:2] == ["id", "-nG"]:
            out = " ".join([argv[2], *self.users[argv[2]]])
        elif code:
            pass
        elif argv[0] == "useradd":
            self.users[argv[-1]] = []
        elif argv[0] == "usermod":
            self.users[argv[-1]] += argv[3].split(",")
        elif argv[0] == "gpasswd":
            self.users[argv[2]].remove(argv[3])
        elif argv[0] == "dpkg-query":
            out = "".join(f"ii {package}\n" for package in sorted(self.packages))
        elif argv[2:4] == ["apt-get", "install"]:
            self.packages |= {p if "=" in p else f"{p}=1" for p in argv[6:]}
        return subprocess.CompletedProcess(argv, code, out.encode(), b"bad line 1")

    def chown(self, path: str, uid: int, gid: int) -> None:
        name = Path(path).name.removeprefix(".").removesuffix(".skiw-new")
        self.chowns[name] = (uid, gid)
        if Path(path).is_relative_to(self.root):  # not the scratch copies the checkers read
            self.owners[str(Path(path).with_name(name).relative_to(self.root))] = (uid, gid)

    def owner(self, path: Path) -> tuple[int, int]:
        return self.owners.get(str(path.relative_to(self.root)), (0, 0))

    def run(self, env: Path = CI_ENV, /, **values: str) -> int:
        if values:  # appended lines win: settings() keeps the last value of a key
            text = env.read_text() + "".join(f"{k}={v}\n" for k, v in values.items())
            env = self.tmp / "host.env"
            env.write_text(text)
        return main(
            ["--env-file", str(env), "--root", str(self.root)], self.runner, self.chown, self.owner
        )

    def read(self, dest: str) -> str:
        return (self.root / dest).read_text()

    def tree(self) -> dict[str, tuple[bytes, int, int]]:
        return {
            str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file() and p != self.root / apply.DOCKER_KEY
        }

    def reloads(self) -> list[str]:
        restarts = [a for a in self.calls if a[:2] == ["nft", "-f"] or "restart" in a[1]]
        return [" ".join(a) for a in restarts]


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_installs_rendered_files_root_owned_with_their_modes(rig: Rig) -> None:
    assert rig.run() == 0
    nft = rig.read("etc/nftables.conf")
    assert "policy drop;" in nft and "flush ruleset" not in nft  # Docker's tables stay
    assert "tcp dport 2222 ip saddr { 192.0.2.0/24 } accept" in nft  # the port from host config
    assert "tcp dport 2222 ip6 saddr { 2001:db8::/32 } accept" in nft
    assert "tcp dport 2222 accept" not in nft and "dport 22 " not in nft
    assert "update @ssh4 { ip saddr limit rate over 10/minute } drop" in nft
    forward = nft[nft.index("chain forward") :]  # Caddy's 80/443 arrive through Docker's DNAT
    assert "{ 80, 443 } ct state new update @web4 { ip saddr limit rate over 30/second }" in forward
    sshd = "Port 2222\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n"
    assert rig.read("etc/ssh/sshd_config.d/00-skiw.conf").endswith(
        f"{sshd}PermitRootLogin no\nMaxAuthTries 3\n"
    )
    assert json.loads(rig.read("etc/docker/daemon.json")) == DAEMON  # so no "hosts": no TCP socket
    unattended = rig.read("etc/apt/apt.conf.d/52skiw-unattended")
    assert '{ "${distro_id}:${distro_codename}-security"; };' in unattended
    assert 'Automatic-Reboot "false";' in unattended
    journal = "Storage=persistent\nMaxRetentionSec=90day\nSystemMaxUse=2G\n"
    assert rig.read("etc/systemd/journald.conf.d/skiw.conf").endswith(journal)
    assert rig.read(apply.ENV) == CI_ENV.read_text()
    assert not (rig.root / "etc/fail2ban").exists()  # allowlist: no fail2ban jail
    items = apply.plan(CI_ENV, *apply.host_values(CI_ENV))
    modes = {dest: (rig.root / dest).stat().st_mode & 0o777 for dest, _, _ in items}
    assert modes["etc/sudoers.d/skiw-ops"] == 0o440
    assert {modes[f"usr/local/sbin/{n}"] for n in ("bootstrap-secrets", "bootstrap-db")} == {0o755}
    assert list(modes.values()).count(0o644) == len(modes) - 3  # all others: 0644
    assert {Path(dest).name for dest in modes} <= rig.chowns.keys()
    assert set(rig.chowns.values()) == {(0, 0)}  # root:root, the checked candidates too
    assert {f"{apply.LIB}/db/roles.sql", f"{apply.LIB}/nftables.conf"} <= modes.keys()


def test_the_fail2ban_policy_opens_ssh_to_all_and_installs_the_jail(rig: Rig) -> None:
    assert rig.run(SKIW_SSH_POLICY="fail2ban", SKIW_SSH_ALLOW="", SKIW_SSH_PORT="2200") == 0
    assert "\t\ttcp dport 2200 accept\n" in rig.read("etc/nftables.conf")
    assert "port = 2200" in rig.read("etc/fail2ban/jail.d/skiw.local")


def test_a_second_run_changes_nothing(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    assert rig.run() == 0
    before = rig.tree()
    assert rig.run() == 0
    assert rig.tree() == before
    assert capsys.readouterr().err.splitlines()[-1] == "apply: done; 0 files changed: "


def test_a_drifted_file_is_put_back_and_only_it(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.run() == 0
    (rig.root / "etc/docker/daemon.json").write_text("{}")
    assert rig.run() == 0
    assert capsys.readouterr().err.endswith("1 files changed: etc/docker/daemon.json\n")
    assert json.loads(rig.read("etc/docker/daemon.json"))["live-restore"] is True


@pytest.mark.parametrize(
    "values",
    [
        {"SKIW_SSH_PORT": ""},
        {"SKIW_SSH_PORT": "22"},
        {"SKIW_SSH_PORT": "70000"},
        {"SKIW_SSH_PORT": "2222; drop"},
        {"SKIW_SSH_POLICY": ""},
        {"SKIW_SSH_POLICY": "allowlist", "SKIW_SSH_ALLOW": ""},  # never silently fail2ban
        {"SKIW_SSH_POLICY": "fail2ban"},  # with the CI allow-list still set
        {"SKIW_SSH_ALLOW": "192.0.2.1/24"},
        {"SKIW_SSH_ALLOW": "any"},
        {"SKIW_SSH_RATE": "fast"},
        {"SKIW_AUTO_REBOOT": ""},
        {"SKIW_AUTO_REBOOT": "yes"},
        {"SKIW_JOURNAL_MAX_USE": "all"},
    ],
)
def test_a_bad_host_value_refuses_before_any_check(rig: Rig, values: dict[str, str]) -> None:
    assert rig.run(**values) == 2
    assert rig.calls == [] and rig.tree() == {}


@pytest.mark.parametrize("name", ["staging.env", "production.env"])
def test_host_env_files_refuse_until_the_owner_answers_g7_and_g15(rig: Rig, name: str) -> None:
    assert rig.run(HOST / "env" / name) == 2 and rig.calls == []


@pytest.mark.parametrize("checker", ["nft", "sshd", "visudo"])
def test_a_failed_check_refuses_and_installs_nothing(
    rig: Rig, checker: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.fail = checker
    assert rig.run() == 2
    assert rig.tree() == {}
    assert "refused, nothing installed" in capsys.readouterr().err
    assert {argv[0] for argv in rig.calls} <= {"gpg", "nft", "sshd", "visudo"}  # no install step


def test_each_candidate_is_checked_with_its_final_mode(rig: Rig) -> None:
    assert rig.run() == 0
    checked = [tuple(argv[:-1]) for argv in rig.calls if argv[1] in ("-c", "-t")]
    assert checked == list(apply.CHECKERS.values())
    assert rig.modes == {"nft": 0o644, "sshd": 0o644, "visudo": 0o440}


def sudo_allows(rule: str, argv: list[str]) -> bool:
    """sudoers semantics for a command with arguments and no wildcard: an exact match only."""
    return rule.split() == argv


def test_the_sudoers_rule_pins_the_whole_restore_command() -> None:
    text = (HOST / "sudoers.d/skiw-ops").read_text()
    rules = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert rules == [f"skiw-ops ALL=(root) NOPASSWD: {RULE}"]
    assert not set("*?[]\\!") & set(rules[0]) and "ALL" not in rules[0].split(":", 1)[1]
    assert sudo_allows(RULE, RULE.split())
    for extra in (
        ["--root", "/srv/x"],
        ["--age", "/srv/age"],
        ["--allow-new-key-version", "field_kek"],
        ["--env-file", "/srv/other.env"],
    ):
        assert not sudo_allows(RULE, [*RULE.split(), *extra])
    assert not sudo_allows(RULE, RULE.replace("restore", "init").split())
    assert not sudo_allows(RULE, RULE.split()[:-1])


def test_installed_bootstrap_db_finds_its_db_directory(rig: Rig) -> None:
    assert rig.run() == 0
    lib = rig.root / apply.LIB
    probe = "from skiw_host import bootstrap_db as m; print(m.DB, (m.DB / 'roles.sql').is_file())"
    out = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path[:0] = [{str(lib)!r}]; {probe}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    assert out == f"{lib / 'db'} True\n"


def test_a_matching_file_with_the_wrong_owner_or_group_is_repaired(rig: Rig) -> None:
    assert rig.run() == 0
    module = "usr/local/lib/skiw/skiw_host/escrow.py"  # imported by the root bootstrap-secrets
    for drift in ((1000, 0), (0, 1000)):
        rig.owners[module] = drift  # bytes and mode still match
        assert rig.run() == 0
        assert rig.owners[module] == (0, 0)
    before = rig.tree()
    assert rig.run() == 0 and rig.tree() == before  # a compliant run changes nothing
    assert all(owner == (0, 0) for owner in rig.owners.values())


def test_a_link_at_a_destination_is_replaced_not_followed(rig: Rig) -> None:
    assert rig.run() == 0
    target = rig.tmp / "elsewhere"
    target.write_bytes(rig.read("etc/nftables.conf").encode())
    (rig.root / "etc/nftables.conf").unlink()
    (rig.root / "etc/nftables.conf").symlink_to(target)
    assert rig.run() == 0
    assert not (rig.root / "etc/nftables.conf").is_symlink()
    assert target.read_text() == rig.read("etc/nftables.conf")  # the target is left as it was


@pytest.mark.parametrize("kind", ["owner", "link"])
def test_a_directory_not_owned_by_root_or_a_link_refuses_before_any_install(
    rig: Rig, kind: str
) -> None:
    lib = rig.root / "usr/local/lib"
    lib.mkdir(parents=True)
    if kind == "owner":
        (lib / "skiw").mkdir()
        rig.owners["usr/local/lib/skiw"] = (1000, 0)
    else:
        (lib / "skiw").symlink_to(rig.tmp)
    assert rig.run() == 2
    assert rig.tree() == {} and rig.calls == []


@pytest.mark.parametrize("unsafe", [0o777, 0o775, 0o757])
def test_a_directory_others_can_write_refuses_before_any_install(rig: Rig, unsafe: int) -> None:
    module_dir = rig.root / "usr/local/lib/skiw/skiw_host"
    module_dir.mkdir(parents=True)
    module_dir.chmod(unsafe)  # root-owned (the rig says so) but replaceable by another user
    assert rig.run() == 2
    assert rig.tree() == {} and rig.calls == []


@pytest.mark.parametrize("umask", [0o000, 0o077])
def test_new_directories_get_a_fixed_mode_whatever_the_umask(rig: Rig, umask: int) -> None:
    old = os.umask(umask)
    try:
        assert rig.run() == 0
        directories = [p for p in rig.root.rglob("*") if p.is_dir()]
        assert directories and all(p.stat().st_mode & 0o777 == 0o755 for p in directories)
        before = rig.tree()
        assert rig.run() == 0 and rig.tree() == before  # the safe tree it made is accepted again
    finally:
        os.umask(old)


def test_a_new_directory_is_never_writable_by_others_even_before_its_chmod(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial: dict[str, int] = {}
    real_chmod = os.chmod

    def spy(path: str | os.PathLike[str], mode: int) -> None:
        if os.path.isdir(path):  # the mode the directory had when mkdir returned
            initial[str(path)] = stat.S_IMODE(os.stat(path).st_mode)
        real_chmod(path, mode)

    monkeypatch.setattr(os, "chmod", spy)
    old = os.umask(0o000)
    try:
        assert rig.run() == 0
    finally:
        os.umask(old)
    assert initial and all(mode & 0o022 == 0 for mode in initial.values())


def test_a_link_planted_where_a_directory_was_to_be_created_is_refused(rig: Rig) -> None:
    (rig.root / "usr").symlink_to(rig.tmp)  # appears after the earlier check in a real race
    with pytest.raises(Refused):
        apply.make_directories(rig.root, Path("usr/local"), rig.chown)
    assert not (rig.tmp / "local").exists()


def test_users_are_made_outside_group_docker_and_the_operator_is_in_sudo(rig: Rig) -> None:
    rig.users["skiw-deploy"] = ["docker"]  # made by hand before: apply takes it out of docker
    assert rig.run() == 0
    assert ["gpasswd", "--delete", "skiw-deploy", "docker"] in rig.calls
    assert rig.users == {"skiw-deploy": [], "skiw-ops": ["sudo"]}
    assert not any("docker" in argv for argv in rig.calls if argv[0] in ("useradd", "usermod"))


def test_docker_is_installed_at_its_pins_only_when_missing_or_wrong(rig: Rig) -> None:
    rig.packages = {"docker-ce=5:29.8.0-1~ubuntu.24.04~noble", "nftables=1"}
    assert rig.run() == 0
    install = next(argv for argv in rig.calls if argv[2:4] == ["apt-get", "install"])
    assert set(install[6:]) == PINNED | {"unattended-upgrades"}  # nftables was there
    assert rig.read("etc/apt/preferences.d/skiw-docker").count("Pin-Priority: 1001") == 2
    assert "Signed-By: /etc/apt/keyrings/docker.asc" in rig.read(
        "etc/apt/sources.list.d/docker.sources"
    )
    rig.calls = []
    assert rig.run() == 0
    assert not any("apt-get" in argv for argv in rig.calls)


def test_units_are_enabled_and_only_changed_files_reload(rig: Rig) -> None:
    assert rig.run() == 0
    assert rig.reloads() == [
        "nft -f /etc/nftables.conf",
        "systemctl restart ssh.service",
        "systemctl restart docker",
        "systemctl restart systemd-journald",
    ]
    assert ["systemctl", "disable", "--now", "ssh.socket"] in rig.calls
    assert ["systemctl", "enable", *apply.UNITS] in rig.calls  # allowlist: no fail2ban
    rig.calls = []
    assert rig.run() == 0 and rig.reloads() == []  # a second run reloads nothing
    (rig.root / "etc/docker/daemon.json").write_text("{}")
    assert rig.run() == 0 and rig.reloads() == ["systemctl restart docker"]


def test_a_reload_that_failed_is_owed_until_a_run_succeeds(rig: Rig) -> None:
    rig.fail = "systemctl restart docker"
    assert rig.run() == 1
    pending = rig.root / apply.PENDING
    assert pending.read_text().split() == list(apply.RELOADS)[:4]
    assert pending.stat().st_mode & 0o777 == 0o644 and rig.owners[apply.PENDING] == (0, 0)
    rig.fail, rig.calls = "", []
    assert rig.run() == 0  # no file changed now, yet every owed reload runs once
    assert len(rig.reloads()) == 4 and not pending.exists()
    rig.calls = []
    assert rig.run() == 0 and rig.reloads() == []


def test_a_stale_fail2ban_jail_is_removed_under_the_allowlist_policy(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rig.run(SKIW_SSH_POLICY="fail2ban", SKIW_SSH_ALLOW="") == 0
    assert ["systemctl", "enable", *apply.UNITS, "fail2ban"] in rig.calls
    assert "fail2ban=1" in rig.packages
    rig.calls = []
    assert rig.run() == 0  # the CI env file: allowlist
    assert not (rig.root / "etc/fail2ban/jail.d/skiw.local").exists()
    assert "systemctl try-restart fail2ban" in rig.reloads()
    assert "removed etc/fail2ban/jail.d/skiw.local (policy allowlist)" in capsys.readouterr().err


@pytest.mark.parametrize("problem", ["missing", "other key", "two keys", "owner", "link"])
def test_the_docker_key_must_be_exactly_dockers_or_nothing_changes(rig: Rig, problem: str) -> None:
    key = rig.root / apply.DOCKER_KEY
    if problem == "missing":
        key.unlink()
    elif problem == "other key":
        rig.gpg = KEY.replace("9DC8", "0000")
    elif problem == "two keys":  # apt would trust both
        rig.gpg = KEY + KEY.replace("9DC8", "0000")
    elif problem == "owner":
        rig.owners[apply.DOCKER_KEY] = (1000, 0)
    else:
        key.unlink()
        key.symlink_to(rig.tmp / "key")
    assert rig.run() == 2
    assert rig.tree() == {} and {argv[0] for argv in rig.calls} <= {"gpg"}


def test_a_pending_file_not_owned_by_root_refuses(rig: Rig) -> None:
    (rig.root / "var/lib/skiw").mkdir(parents=True)
    (rig.root / apply.PENDING).write_text("etc/docker/daemon.json\n")
    rig.owners[apply.PENDING] = (1000, 0)
    assert rig.run() == 2 and rig.calls == []
