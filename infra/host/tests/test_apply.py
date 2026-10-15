"""`apply` (spec §8.4 H1, H2, H4, H7; plan §3 M1f, first part).

A fake runner stands in for the checkers (`nft -c`, `sshd -t`, `visudo -c`); a temporary root and
a recording chown stand in for the host.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skiw_host import apply
from skiw_host.apply import main

HOST = Path(__file__).resolve().parents[1]
CI_ENV = HOST / "env" / "ci.env"
DAEMON = {"live-restore": True, "no-new-privileges": True, "log-driver": "journald"}
RULE = "/usr/local/sbin/bootstrap-secrets restore --env-file /etc/skiw/host.env"


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.root = tmp / "root"
        self.root.mkdir()
        self.calls: list[list[str]] = []
        self.chowns: dict[str, tuple[int, int]] = {}
        self.fail = ""  # argv[0] of the checker that fails
        self.modes: dict[str, int] = {}  # checker -> mode of the candidate it was given

    def runner(self, argv: list[str], stdin: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        self.modes[argv[0]] = Path(argv[-1]).stat().st_mode & 0o777
        return subprocess.CompletedProcess(argv, int(argv[0] == self.fail), b"", b"bad line 1")

    def chown(self, path: str, uid: int, gid: int) -> None:
        self.chowns[Path(path).name.removeprefix(".").removesuffix(".skiw-new")] = (uid, gid)

    def run(self, env: Path = CI_ENV, /, **values: str) -> int:
        if values:  # appended lines win: settings() keeps the last value of a key
            text = env.read_text() + "".join(f"{k}={v}\n" for k, v in values.items())
            env = self.tmp / "host.env"
            env.write_text(text)
        return main(["--env-file", str(env), "--root", str(self.root)], self.runner, self.chown)

    def read(self, dest: str) -> str:
        return (self.root / dest).read_text()

    def tree(self) -> dict[str, tuple[bytes, int, int]]:
        return {
            str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file()
        }


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
    assert {argv[0] for argv in rig.calls} <= {"nft", "sshd", "visudo"}  # no install step ran


def test_each_candidate_is_checked_with_its_final_mode(rig: Rig) -> None:
    assert rig.run() == 0
    assert [tuple(argv[:-1]) for argv in rig.calls] == list(apply.CHECKERS.values())
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
