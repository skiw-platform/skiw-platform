"""`apply --env-file <env>` (spec §8.4 H1, H2, H4, H7; runbook host-rebuild.md "Host").

Installs this host's files from the repository. Every host value is checked and each rendered
file that has a checker (nftables, sshd, sudoers) is checked as a scratch copy first: a refusal
exits 2 with nothing installed. Then only the files that differ are installed, root-owned with
fixed modes. A second run changes nothing. Exit 0 done, 1 failed, 2 refused.
Users, packages, units and reloads are M1f-1b.
"""

import argparse
import ipaddress
import os
import re
import stat
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from string import Template

from skiw_host.bootstrap_db import Runner, run_command, settings
from skiw_host.bootstrap_secrets import Chown, Refused

HOST = Path(__file__).resolve().parents[1]
LIB = "usr/local/lib/skiw"  # skiw_host, db/ and the templates; the executables put it on sys.path
ENV = "etc/skiw/host.env"  # the env file the sudoers rule names
CONFIG = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH  # 0644
PROGRAM = CONFIG | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH  # 0755
SUDOERS = stat.S_IRUSR | stat.S_IRGRP  # 0440, as visudo requires
TEMPLATES = {  # rendered from host config: source under infra/host -> destination
    "nftables.conf": "etc/nftables.conf",
    "sshd/00-skiw.conf": "etc/ssh/sshd_config.d/00-skiw.conf",  # 00: before 50-cloud-init.conf
    "sudoers.d/skiw-ops": "etc/sudoers.d/skiw-ops",
    "docker/daemon.json": "etc/docker/daemon.json",
    "journald/skiw.conf": "etc/systemd/journald.conf.d/skiw.conf",
    "apt/52skiw-unattended": "etc/apt/apt.conf.d/52skiw-unattended",
}
FAIL2BAN = {"fail2ban/jail.local": "etc/fail2ban/jail.d/skiw.local"}  # G7 (b) only
CHECKERS = {  # run on each candidate before anything is installed
    "etc/nftables.conf": ("nft", "-c", "-f"),
    "etc/ssh/sshd_config.d/00-skiw.conf": ("sshd", "-t", "-f"),
    "etc/sudoers.d/skiw-ops": ("visudo", "-c", "-f"),
}
PORT = re.compile(r"[1-9][0-9]{0,4}")
RATE = re.compile(r"[1-9][0-9]*/(second|minute)")
CHECKS = {
    "SKIW_SSH_POLICY": re.compile("allowlist|fail2ban"),
    "SKIW_SSH_RATE": RATE,
    "SKIW_WEB_RATE": RATE,
    "SKIW_AUTO_REBOOT": re.compile("true|false"),
    "SKIW_JOURNAL_MAX_USE": re.compile(r"[1-9][0-9]*[MG]"),
}
Item = tuple[str, bytes, int]  # destination under the root, content, mode
Owner = Callable[[Path], tuple[int, int]]
ROOT = (0, 0)  # uid, gid every installed file and directory must have


def lstat_owner(path: Path) -> tuple[int, int]:
    info = path.lstat()  # a link is judged itself, never through its target
    return info.st_uid, info.st_gid


def host_values(env_file: Path) -> tuple[dict[str, str], bool]:
    """Template values and whether fail2ban is used (G7 (b)); an empty or bad value refuses."""
    values = settings(env_file)
    port = values.get("SKIW_SSH_PORT", "")
    if not PORT.fullmatch(port) or int(port) > 65535 or port in ("22", "80", "443"):
        raise Refused(f"SKIW_SSH_PORT in {env_file} is empty, 22, 80, 443 or not a port (G7)")
    if bad := [name for name, check in CHECKS.items() if not check.fullmatch(values.get(name, ""))]:
        raise Refused(f"{', '.join(bad)} in {env_file}: empty or invalid")
    try:
        allow = [ipaddress.ip_network(x) for x in values.get("SKIW_SSH_ALLOW", "").split()]
    except ValueError:
        raise Refused(f"SKIW_SSH_ALLOW in {env_file} holds a value that is not a CIDR") from None
    ban = values["SKIW_SSH_POLICY"] == "fail2ban"
    if ban == bool(allow):
        raise Refused(f"SKIW_SSH_ALLOW in {env_file} must be set for allowlist, empty for fail2ban")
    accept = [
        f"\t\ttcp dport {port} {family} saddr {{ {', '.join(nets)} }} accept"
        for family, version in (("ip", 4), ("ip6", 6))
        if (nets := [str(n) for n in allow if n.version == version])
    ] or [f"\t\ttcp dport {port} accept"]
    names = ("ssh_rate", "web_rate", "auto_reboot", "journal_max_use")
    rendered = {name: values[f"SKIW_{name.upper()}"] for name in names}
    return {"ssh_port": port, "ssh_accept": "\n".join(accept), **rendered}, ban


def plan(env_file: Path, values: dict[str, str], ban: bool) -> list[Item]:
    items: list[Item] = [
        (dest, Template((HOST / src).read_text("utf-8")).substitute(values).encode(), mode(dest))
        for src, dest in (TEMPLATES | (FAIL2BAN if ban else {})).items()
    ]
    items.append((ENV, env_file.read_bytes(), CONFIG))
    for name in ("bootstrap-secrets", "bootstrap-db"):
        items.append((f"usr/local/sbin/{name}", (HOST / name).read_bytes(), PROGRAM))
    library = [*(HOST / "skiw_host").glob("*.py"), *(HOST / "db").iterdir()]
    for path in sorted([*library, *(HOST / src for src in TEMPLATES | FAIL2BAN)]):
        items.append((f"{LIB}/{path.relative_to(HOST)}", path.read_bytes(), CONFIG))
    return items


def mode(dest: str) -> int:
    return SUDOERS if dest.startswith("etc/sudoers.d/") else CONFIG


def untrusted(root: Path, items: list[Item], owner: Owner) -> None:
    """Refuse a link or a directory not owned by root:root on the way to any destination: its
    owner could swap root-executed files later."""
    for dest, _, _ in items:
        path = root
        for part in Path(dest).parent.parts:
            path /= part
            if path.is_symlink() or (path.exists() and owner(path) != ROOT):
                raise Refused(f"/{path.relative_to(root)} is a link or not owned by root:root")


def precheck(items: list[Item], run: Runner, chown: Chown) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        for dest, data, file_mode in items:
            if check := CHECKERS.get(dest):
                candidate = Path(scratch) / Path(dest).name
                candidate.write_bytes(data)
                os.chmod(candidate, file_mode)
                chown(str(candidate), *ROOT)  # visudo refuses a file root does not own
                if (done := run([*check, str(candidate)], b"")).returncode != 0:
                    detail = done.stderr.decode("utf-8", "replace")[-500:]
                    raise Refused(f"/{dest} fails `{check[0]}`: {detail}")


def install(root: Path, items: list[Item], chown: Chown, owner: Owner) -> list[str]:
    changed = []
    for dest_name, data, file_mode in items:
        dest = root / dest_name
        same = dest.is_file() and not dest.is_symlink() and dest.read_bytes() == data
        if same and stat.S_IMODE(dest.stat().st_mode) == file_mode and owner(dest) == ROOT:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.skiw-new")  # a dot: sudo ignores it in sudoers.d
        tmp.write_bytes(data)
        os.chmod(tmp, file_mode)
        chown(str(tmp), *ROOT)
        os.replace(tmp, dest)
        changed.append(dest_name)
    return changed


def main(
    argv: Sequence[str] | None = None,
    run: Runner = run_command,
    chown: Chown = os.chown,
    owner: Owner = lstat_owner,
) -> int:
    parser = argparse.ArgumentParser(prog="apply", description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True, help="host env/<env>.env")
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    try:
        values, ban = host_values(args.env_file)
        items = plan(args.env_file, values, ban)
        untrusted(args.root, items, owner)
        precheck(items, run, chown)
        changed = install(args.root, items, chown, owner)
    except Refused as exc:
        print(f"apply: refused, nothing installed: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"apply: failed: {exc.strerror} {exc.filename}", file=sys.stderr)
        return 1
    print(f"apply: done; {len(changed)} files changed: {' '.join(changed)}", file=sys.stderr)
    return 0
