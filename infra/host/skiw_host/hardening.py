"""`check-hardening` (spec §8.4 H2, H7; runbook host-rebuild.md "Host").

Read-only: it never changes the host. One line per check, `PASS name` or `FAIL name: what`; a check
whose tool is missing, exits non-zero or prints what cannot be parsed fails, never passes. Files are
read without following links, with the owner and mode checked on the open file. No secret value
is ever printed. Each check is one entry in CHECKS; the secret-store, container-env, role-set and
pg-hba checks are added in M1f-2b.
Exit 0 all passed, 1 a check failed, 2 refused (not root, or a bad env file).
"""

import argparse
import ipaddress
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from string import Template
from typing import Any

from skiw_host import apply
from skiw_host.bootstrap_db import Runner, run_command
from skiw_host.bootstrap_secrets import Refused

APT_LINE = re.compile(r'(\S+) "(.*)";')
Owner = Callable[[Path, os.stat_result], tuple[int, int]]


class Bad(Exception):
    """A failed check; the message names paths, keys and non-secret values only."""


class Host:
    def __init__(self, args: argparse.Namespace, run: Runner, owner: Owner, env_text: str) -> None:
        self.root, self.env_file, self.run, self.owner = args.root, args.env_file, run, owner
        self.values, self.ban = apply.host_values(self.env_file, env_text)

    def tool(self, argv: list[str], stdin: bytes = b"") -> str:
        done = self.run(argv, stdin)
        if done.returncode != 0:
            raise Bad(f"`{' '.join(argv[:3])}` exited {done.returncode}")
        return done.stdout.decode("utf-8")  # strict: undecodable output fails the check

    def render(self, source: str) -> str:
        return Template((apply.HOST / source).read_text("utf-8")).substitute(self.values)

    def read(self, rel: str, uid: int = 0, mode: int | None = None) -> bytes:
        try:
            apply.untrusted(self.root, [rel], lambda p: self.owner(p, p.lstat()))
        except Refused as exc:
            raise Bad(str(exc)) from None
        return read_file(self.root / rel, self.owner, uid, mode)


def stat_owner(path: Path, info: os.stat_result) -> tuple[int, int]:
    return info.st_uid, info.st_gid


def read_file(path: Path, owner: Owner, uid: int = 0, mode: int | None = None) -> bytes:
    """Never through a link; owner, group and mode judged on the open file itself."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)  # NONBLOCK: a FIFO cannot hang
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise Bad(f"{path} is not a regular file")
        if owner(path, info) != (uid, 0):
            raise Bad(f"{path} is owned by {':'.join(map(str, owner(path, info)))}, not {uid}:0")
        actual = stat.S_IMODE(info.st_mode)
        if (mode is not None and actual != mode) or actual & apply.OTHERS_WRITE:
            raise Bad(f"{path} has mode {actual:04o}")
        chunks = []
        while chunk := os.read(fd, 65536):
            chunks.append(chunk)
        data = b"".join(chunks)
        if len(data) != os.fstat(fd).st_size:
            raise Bad(f"{path} changed while it was read")
        return data
    finally:
        os.close(fd)


def sshd(host: Host) -> list[str]:
    seen: dict[str, list[str]] = {}
    for line in host.tool(["sshd", "-T"]).splitlines():
        key, _, value = line.partition(" ")
        seen.setdefault(key.lower(), []).append(value)
    want = {k.lower(): [v] for k, v in settings_lines(host.render("sshd/00-skiw.conf"))}
    return [
        f"{k} is {' '.join(seen.get(k, ['unset']))}, want {v[0]}"
        for k, v in want.items()
        if seen.get(k) != v
    ]


def settings_lines(text: str) -> list[tuple[str, str]]:
    lines = [line.split(None, 1) for line in text.splitlines()]
    return [(words[0], words[1]) for words in lines if len(words) == 2 and words[0][0] != "#"]


def canonical(listing: str) -> list[Any]:
    """`nft -j` without what changes on its own: handles, metainfo, dynamic set elements."""

    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k != "handle"}
        return [strip(v) for v in node] if isinstance(node, list) else node

    objects = [
        {kind: {k: v for k, v in strip(body).items() if k != "elem"}}
        for item in json.loads(listing)["nftables"]
        for kind, body in item.items()
        if kind != "metainfo"
    ]
    if not any("table" in item for item in objects):
        raise Bad("no table inet skiw in the listing")
    return objects


def nftables(host: Host) -> list[str]:
    live = canonical(host.tool(["nft", "-j", "list", "table", "inet", "skiw"]))
    # The rendered file, loaded in a throwaway network namespace, printed by the same nft.
    load = "nft -f /dev/stdin && nft -j list table inet skiw"
    rendered = host.render("nftables.conf").encode()
    want = canonical(host.tool(["unshare", "--net", "sh", "-c", load], rendered))
    return [] if live == want else ["the live table inet skiw differs from the rendered file"]


def unattended(host: Host) -> list[str]:
    enabled = host.tool(["systemctl", "is-enabled", "unattended-upgrades"]).strip()
    dump: dict[str, list[str]] = {}
    for line in host.tool(["apt-config", "dump"]).splitlines():
        if match := APT_LINE.fullmatch(line):
            dump.setdefault(match[1], []).append(match[2])
    want = {
        "APT::Periodic::Update-Package-Lists": ["1"],
        "APT::Periodic::Unattended-Upgrade": ["1"],
        "APT::Periodic::Enable": dump.get("APT::Periodic::Enable") and ["1"],  # unset means on
        "Unattended-Upgrade::Allowed-Origins::": ["${distro_id}:${distro_codename}-security"],
        "Unattended-Upgrade::Origins-Pattern::": None,
        "Unattended-Upgrade::Automatic-Reboot": [host.values["auto_reboot"]],
    }
    problems = [f"{k} is {dump.get(k)}, want {v}" for k, v in want.items() if dump.get(k) != v]
    return problems + ([] if enabled == "enabled" else [f"unattended-upgrades is {enabled}"])


def docker_daemon(host: Host) -> list[str]:
    info = json.loads(host.tool(["docker", "info", "--format", "{{json .}}"]))
    config = json.loads(host.read("etc/docker/daemon.json"))
    tcp = [h for h in config.get("hosts", []) if not str(h).startswith(("unix://", "fd://"))]
    problems = {
        "live-restore is off": info["LiveRestoreEnabled"] is not True,
        f"log driver is {info['LoggingDriver']}": info["LoggingDriver"] != "journald",
        "no-new-privileges is not set": config.get("no-new-privileges") is not True,
        f"daemon hosts {tcp}": bool(tcp),
    }
    return [problem for problem, failed in problems.items() if failed]


def sockets(host: Host) -> list[str]:
    allowed = {"80", "443", host.values["ssh_port"]}
    problems = []
    for line in host.tool(["ss", "-H", "-tlnp"]).splitlines():
        fields = line.split()
        address, _, port = fields[3].rpartition(":")
        name = address.strip("[]").partition("%")[0]
        if fields[0] != "LISTEN" or not port.isdigit():
            raise Bad(f"cannot read `ss` line: {line.strip()}")
        public = name == "*" or not ipaddress.ip_address(name).is_loopback  # "*": any address
        if public and port not in allowed:
            problems.append(f"{fields[3]} {' '.join(fields[5:])}".strip())
    return problems


def docker_group(host: Host) -> list[str]:
    users = apply.USERS
    return [
        f"{u} is in group docker" for u in users if "docker" in host.tool(["id", "-nG", u]).split()
    ]


def stale_files(host: Host) -> list[str]:
    """Files apply would not install now, and owed reloads; reported, never removed."""
    problems = []
    for dest in apply.FAIL2BAN.values():
        if not host.ban and ((host.root / dest).exists() or (host.root / dest).is_symlink()):
            problems.append(f"/{dest} is present under the allowlist policy")
    for name in sorted(os.listdir(host.root / "etc/sudoers.d")):
        if name.startswith("skiw") and name != "skiw-ops":
            problems.append(f"/etc/sudoers.d/{name} is not installed by apply")
    checked = {key.lower() for key, _ in settings_lines(host.render("sshd/00-skiw.conf"))}
    drop_ins = "etc/ssh/sshd_config.d"
    for name in sorted(os.listdir(host.root / drop_ins)):
        if name.endswith(".conf") and name < "00-skiw.conf":
            text = host.read(f"{drop_ins}/{name}").decode("utf-8")
            if keys := sorted(checked & {k.lower() for k, _ in settings_lines(text)}):
                problems.append(f"/{drop_ins}/{name} sorts first and sets {', '.join(keys)}")
    if (host.root / apply.PENDING).exists() or (host.root / apply.PENDING).is_symlink():
        problems.append(f"/{apply.PENDING} exists: apply still owes reloads, run apply")
    return problems


CHECKS: dict[str, Callable[[Host], list[str]]] = {
    "sshd": sshd,
    "nftables": nftables,
    "unattended-upgrades": unattended,
    "docker-daemon": docker_daemon,
    "listening-sockets": sockets,
    "docker-group": docker_group,
    "stale-files": stale_files,
}


def main(
    argv: Sequence[str] | None = None, run: Runner = run_command, owner: Owner = stat_owner
) -> int:
    parser = argparse.ArgumentParser(prog="check-hardening", description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("/") / apply.ENV)
    parser.add_argument("--root", type=Path, default=Path("/"), help=argparse.SUPPRESS)  # tests
    args = parser.parse_args(argv)
    try:
        if args.root == Path("/") and os.geteuid() != 0:
            raise Refused("run it as root")
        if not args.env_file.is_relative_to(args.root):
            raise Refused(f"{args.env_file} is not under {args.root}")
        relative = str(args.env_file.relative_to(args.root))
        apply.untrusted(args.root, [relative], lambda p: owner(p, p.lstat()))  # chain: no links
        env_text = read_file(args.env_file, owner).decode("utf-8")  # read once, parsed from this
        host = Host(args, run, owner, env_text)
    except (Refused, Bad, OSError) as exc:
        print(f"check-hardening: refused: {exc}", file=sys.stderr)
        return 2
    failed = 0
    for name, check in CHECKS.items():
        try:
            problems = check(host)
        except (Bad, OSError) as exc:  # value-free by construction
            problems = [str(exc) if isinstance(exc, Bad) else f"{exc.strerror} {exc.filename}"]
        except (
            Exception
        ) as exc:  # unparsable output: the type only, never text that may hold a value
            problems = [f"cannot read the output ({type(exc).__name__})"]
        failed += bool(problems)
        print(f"FAIL {name}: {'; '.join(problems)}" if problems else f"PASS {name}")
    return 1 if failed else 0
