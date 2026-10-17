"""`apply --env-file <env>` (spec §8.4 H1, H2, H4, H7; runbook host-rebuild.md "Host").

Installs this host's files from the repository. Every host value, Docker's apt key and each
rendered file that has a checker (nftables, sshd, sudoers) is checked first: a refusal exits 2 with
nothing changed. Then only the files that differ are installed, root-owned with fixed modes; the
users are made (never in group `docker`), the pinned packages installed, the units enabled and the
services of changed files reloaded. Reloads still owed are kept in a root-owned pending file until
they succeed, so a run that failed (exit 1) can simply be repeated. A second run changes nothing.
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

from skiw_host.bootstrap_db import Failed, Runner, run_command, settings
from skiw_host.bootstrap_secrets import Chown, Refused

HOST = Path(__file__).resolve().parents[1]
LIB = "usr/local/lib/skiw"  # skiw_host, db/ and the templates; the executables put it on sys.path
ENV = "etc/skiw/host.env"  # the env file the sudoers rule names
CONFIG = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH  # 0644
DIRECTORY = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH  # 0755
OTHERS_WRITE = stat.S_IWGRP | stat.S_IWOTH
PROGRAM = CONFIG | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH  # 0755
SUDOERS = stat.S_IRUSR | stat.S_IRGRP  # 0440, as visudo requires
TEMPLATES = {  # rendered from host config: source under infra/host -> destination
    "nftables.conf": "etc/nftables.conf",
    "sshd/00-skiw.conf": "etc/ssh/sshd_config.d/00-skiw.conf",  # 00: before 50-cloud-init.conf
    "sudoers.d/skiw-ops": "etc/sudoers.d/skiw-ops",
    "docker/daemon.json": "etc/docker/daemon.json",
    "journald/skiw.conf": "etc/systemd/journald.conf.d/skiw.conf",
    "apt/52skiw-unattended": "etc/apt/apt.conf.d/52skiw-unattended",
    "apt/docker.sources": "etc/apt/sources.list.d/docker.sources",
    "apt/skiw-docker.pref": "etc/apt/preferences.d/skiw-docker",
}
FAIL2BAN = {"fail2ban/jail.local": "etc/fail2ban/jail.d/skiw.local"}  # G7 (b) only
CHECKERS = {  # run on each candidate before anything is installed
    "etc/nftables.conf": ("nft", "-c", "-f"),
    "etc/ssh/sshd_config.d/00-skiw.conf": ("sshd", "-t", "-f"),
    "etc/sudoers.d/skiw-ops": ("visudo", "-c", "-f"),
}
# Run once the file changed (or was removed). nftables: `nft -f` replaces only table inet skiw; the
# unit's reload and stop flush the whole ruleset, Docker's rules too.
RELOADS = {
    "etc/nftables.conf": ("nft", "-f", "/etc/nftables.conf"),
    "etc/ssh/sshd_config.d/00-skiw.conf": ("systemctl", "restart", "ssh.service"),
    "etc/docker/daemon.json": ("systemctl", "restart", "docker"),
    "etc/systemd/journald.conf.d/skiw.conf": ("systemctl", "restart", "systemd-journald"),
    "etc/fail2ban/jail.d/skiw.local": ("systemctl", "try-restart", "fail2ban"),
}
PENDING = "var/lib/skiw/apply.pending"  # destinations whose reload is still owed
DOCKER_KEY = "etc/apt/keyrings/docker.asc"  # placed by the operator (runbook)
DOCKER_FINGERPRINT = "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"  # "Docker Release (CE deb)"
USERS = {"skiw-deploy": (), "skiw-ops": ("sudo",)}  # ops: the operator, password sudo (H2)
PACKAGES = ("nftables", "unattended-upgrades")
UNITS = ("nftables", "unattended-upgrades", "docker", "ssh.service")
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


def untrusted(root: Path, dests: list[str], owner: Owner) -> None:
    """Refuse a link, a directory not owned by root:root or one that group or others can write, on
    the way to any destination: they could swap root-executed files later."""
    for dest in dests:
        path = root
        for part in Path(dest).parent.parts:
            path /= part
            if path.is_symlink() or (
                path.exists() and (owner(path) != ROOT or path.stat().st_mode & OTHERS_WRITE)
            ):
                raise Refused(
                    f"/{path.relative_to(root)} is a link, not owned by root:root or writable "
                    "by group or others"
                )


def trusted_file(root: Path, dest: str, owner: Owner, required: bool) -> None:
    path = root / dest
    if not path.exists() and not path.is_symlink():
        if required:
            raise Refused(f"/{dest} is missing: see the runbook")
        return
    if path.is_symlink() or owner(path) != ROOT or path.stat().st_mode & OTHERS_WRITE:
        raise Refused(f"/{dest} is a link, not owned by root:root or writable by group or others")


def docker_key(root: Path, run: Runner, owner: Owner) -> None:
    """Exactly one primary key, Docker's: apt trusts every key in a Signed-By file."""
    trusted_file(root, DOCKER_KEY, owner, required=True)
    shown = run(["gpg", "--show-keys", "--with-colons", str(root / DOCKER_KEY)], b"")
    lines = shown.stdout.decode("utf-8", "replace").splitlines()
    primary = [i for i, line in enumerate(lines) if line.startswith("pub:")]
    if len(primary) != 1 or lines[primary[0] + 1 :][:1] != [f"fpr:::::::::{DOCKER_FINGERPRINT}:"]:
        raise Refused(f"/{DOCKER_KEY} is not exactly Docker's release key {DOCKER_FINGERPRINT}")


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


def make_directories(root: Path, relative: Path, chown: Chown) -> None:
    """Create each missing directory 0755 from the start (a umask can only remove bits, so it is
    never writable by others, not even for an instant), then fix the final mode and owner."""
    path = root
    for part in relative.parts:
        path /= part
        try:
            path.mkdir(mode=DIRECTORY)
        except FileExistsError:
            if path.is_symlink():  # planted after the check: never write through it
                raise Refused(f"/{path.relative_to(root)} is a link") from None
            continue
        os.chmod(path, DIRECTORY)  # exact 0755 under a restrictive umask
        chown(str(path), *ROOT)


def stale(root: Path, items: list[Item], owner: Owner) -> list[Item]:
    """The items whose file differs in content, mode, owner or group, or is a link."""
    todo = []
    for dest_name, data, file_mode in items:
        dest = root / dest_name
        same = dest.is_file() and not dest.is_symlink() and dest.read_bytes() == data
        if not (same and stat.S_IMODE(dest.stat().st_mode) == file_mode and owner(dest) == ROOT):
            todo.append((dest_name, data, file_mode))
    return todo


def install(root: Path, items: list[Item], chown: Chown) -> None:
    for dest_name, data, file_mode in items:
        dest = root / dest_name
        make_directories(root, Path(dest_name).parent, chown)
        tmp = dest.with_name(f".{dest.name}.skiw-new")  # a dot: sudo ignores it in sudoers.d
        tmp.write_bytes(data)
        os.chmod(tmp, file_mode)
        chown(str(tmp), *ROOT)
        os.replace(tmp, dest)


def ok(run: Runner, argv: list[str]) -> str:
    done = run(argv, b"")
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace")[-500:]
        raise Failed(f"`{' '.join(argv[:4])}` exited {done.returncode}: {detail}")
    return done.stdout.decode("utf-8", "replace")


def pins() -> list[str]:
    """`package=version` for each package in apt/skiw-docker.pref, the one place they are set."""
    text = (HOST / "apt/skiw-docker.pref").read_text(encoding="utf-8")
    stanzas = [
        dict(line.split(": ", 1) for line in s.splitlines() if not line.startswith("#"))
        for s in text.split("\n\n")
    ]
    return [
        f"{p}={s['Pin'].removeprefix('version ')}" for s in stanzas for p in s["Package"].split()
    ]


def converge(run: Runner, ban: bool) -> None:
    """Users, packages and units; each step checks first, so a repeat changes nothing."""
    for user, groups in USERS.items():
        if run(["id", "-u", user], b"").returncode != 0:
            ok(run, ["useradd", "--create-home", "--shell", "/bin/bash", user])
        member = ok(run, ["id", "-nG", user]).split()
        if missing := [g for g in groups if g not in member]:
            ok(run, ["usermod", "--append", "--groups", ",".join(missing), user])
        if "docker" in member:  # root-equivalent (H2)
            ok(run, ["gpasswd", "--delete", user, "docker"])
    fail2ban = ["fail2ban"] if ban else []
    wanted = [*pins(), *PACKAGES, *fail2ban]
    names = [w.partition("=")[0] for w in wanted]
    query = run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}${Package}=${Version}\\n", *names], b"")
    have = {line[3:] for line in query.stdout.decode().splitlines() if line.startswith("ii ")}
    have |= {h.partition("=")[0] for h in have}  # an unpinned name matches any version
    if missing_packages := [w for w in wanted if w not in have]:
        ok(run, ["apt-get", "update"])
        install_argv = ["apt-get", "install", "-y", "--no-install-recommends", *missing_packages]
        ok(run, ["env", "DEBIAN_FRONTEND=noninteractive", *install_argv])
    ok(run, ["systemctl", "enable", *UNITS, *fail2ban])
    ok(run, ["systemctl", "disable", "--now", "ssh.socket"])  # 24.04: sshd then binds Port itself
    ok(run, ["systemctl", "start", "ssh.service"])


def write_pending(root: Path, owed: list[str], chown: Chown) -> None:
    make_directories(root, Path(PENDING).parent, chown)
    tmp = root / f"{PENDING}.skiw-new"
    tmp.write_text("".join(f"{dest}\n" for dest in owed), encoding="utf-8")
    os.chmod(tmp, CONFIG)
    chown(str(tmp), *ROOT)
    os.replace(tmp, root / PENDING)


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
    root = args.root
    try:
        values, ban = host_values(args.env_file)
        items = plan(args.env_file, values, ban)
        jail = [*FAIL2BAN.values()]
        untrusted(root, [*(dest for dest, _, _ in items), DOCKER_KEY, PENDING, *jail], owner)
        trusted_file(root, PENDING, owner, required=False)
        docker_key(root, run, owner)
        precheck(items, run, chown)
        todo = stale(root, items, owner)
        retired = [d for d in jail if not ban and ((root / d).exists() or (root / d).is_symlink())]
        before = (root / PENDING).read_text("utf-8").split() if (root / PENDING).exists() else []
        changed = [dest for dest, _, _ in todo]
        owed = [d for d in dict.fromkeys([*before, *changed, *retired]) if d in RELOADS]
        if owed:  # first, so a run that stops below still owes these reloads next time
            write_pending(root, owed, chown)
        install(root, todo, chown)
        for dest in retired:  # allowlist now: the fail2ban jail must not stay enabled
            (root / dest).unlink()
        converge(run, ban)
        for command in dict.fromkeys(RELOADS[dest] for dest in owed):
            ok(run, list(command))
        (root / PENDING).unlink(missing_ok=True)
    except Refused as exc:
        print(f"apply: refused, nothing installed: {exc}", file=sys.stderr)
        return 2
    except Failed as exc:
        print(f"apply: failed: {exc}; fix it and run apply again", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"apply: failed: {exc.strerror} {exc.filename}; run apply again", file=sys.stderr)
        return 1
    removed = "".join(f"; removed {dest} (policy allowlist)" for dest in retired)
    print(
        f"apply: done; {len(changed)} files changed: {' '.join(changed)}{removed}", file=sys.stderr
    )
    return 0
