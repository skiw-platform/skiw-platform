"""`check-hardening` (spec §8.4 H2, H4, H6, H7; runbook host-rebuild.md "Host").

Read-only: it never changes the host. One line per check, `PASS name` or `FAIL name: what`; a check
whose tool is missing, exits non-zero or prints what cannot be parsed fails, never passes. Files are
read without following links, with the owner and mode checked on the open file. No secret value
is ever printed: the container check names the container and the variable only. Each check is
one entry in CHECKS. role-set reads /srv/skiw/compose.yml (or --compose-file) and the deploy state.
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
from skiw_host.bootstrap_db import (
    DB,
    HBA,
    HBA_MODE,
    Runner,
    psql_script,
    render_hba,
    run_command,
    settings,
)
from skiw_host.bootstrap_secrets import DIR_MODE, MARKER, Refused
from skiw_host.secrets import ALERT_CHANNEL, ALERT_CREDENTIAL, OWNER, STATUS_KEY, held

APT_LINE = re.compile(r'(\S+) "(.*)";')
ORIGINS = ("Unattended-Upgrade::Allowed-Origins", "Unattended-Upgrade::Origins-Pattern")
SSHD_DROP_INS = "etc/ssh/sshd_config.d"
# sshd_config keywords that name the same setting as a checked key (sshd -T prints the first name)
SSHD_ALIASES = {"challengeresponseauthentication": "kbdinteractiveauthentication"}
# sshd strips quotes from a keyword; this scan does not, so it refuses any line that has them
SSHD_QUOTES = "\"'\\"
SECRETS = "etc/skiw/secrets"
SECRET_MODE = stat.S_IRUSR  # 0400 (bootstrap-secrets, bootstrap-db)
MIN_SECRET = 16  # shorter strings are not looked for in container environments (owner, M1f-2b)
KEY_LINE = re.compile(r"v[1-9][0-9]*:(.+)")  # app keys; the payload is searched too
CONTAINER_ID = re.compile(r"[0-9a-f]{64}")  # `docker ps --no-trunc`
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")  # container and variable names shown
# The whole role inventory (no name filter), every role setting, every membership.
ROLES_QUERY = rb"""\pset format unaligned
\pset tuples_only on
SELECT concat_ws('|', 'role', oid, rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
  rolcreaterole, rolreplication, rolconnlimit) FROM pg_roles;
SELECT concat_ws('|', 'setting', r.rolname, s.setdatabase, c)
FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole, unnest(s.setconfig) c;
SELECT concat_ws('|', 'member', u.rolname, g.rolname, m.admin_option, m.inherit_option,
  m.set_option)
FROM pg_auth_members m JOIN pg_roles u ON u.oid = m.member JOIN pg_roles g ON g.oid = m.roleid;
"""
BOOTSTRAP, BOOTSTRAP_OID = (
    "postgres",
    10,
)  # initdb's superuser (POSTGRES_USER), BOOTSTRAP_SUPERUSERID
FIRST_NORMAL_OID = (
    16384  # below it: made by initdb, so pg_* there are PostgreSQL's predefined roles
)
LABELS = (
    "login",
    "superuser",
    "bypassrls",
    "createdb",
    "createrole",
    "replication",
    "connection limit",
)
ATTRIBUTES = ("LOGIN", "SUPERUSER", "BYPASSRLS", "CREATEDB", "CREATEROLE", "REPLICATION")
Owner = Callable[[Path, os.stat_result], tuple[int, int]]
Settings = set[tuple[str, str, str]]  # role, database oid (0: every database), name=value
# (member, group) -> admin, inherit, set option ('t'/'f'); () when the pair is granted twice
Members = dict[tuple[str, str], tuple[str, ...]]
MEMBER_OPTIONS = ("admin", "inherit", "set")
# PostgreSQL 17.11's own memberships right after initdb, with their options (native run, the
# fixture roles-pg17.txt). Exactly these and roles.sql's grants are allowed; nothing else.
BASELINE_MEMBERS: Members = {
    ("pg_monitor", "pg_read_all_settings"): ("f", "t", "t"),
    ("pg_monitor", "pg_read_all_stats"): ("f", "t", "t"),
    ("pg_monitor", "pg_stat_scan_tables"): ("f", "t", "t"),
}


class Bad(Exception):
    """A failed check; the message names paths, keys and non-secret values only."""


class Host:
    def __init__(self, args: argparse.Namespace, run: Runner, owner: Owner, env_text: str) -> None:
        self.root, self.env_file, self.run, self.owner = args.root, args.env_file, run, owner
        self.compose: Path | None = args.compose_file or args.root / apply.COMPOSE
        self.env_text = env_text
        self.values, self.ban = apply.host_values(self.env_file, env_text)
        found = settings(self.env_file, env_text)
        self.environment = found.get("SKIW_ENVIRONMENT", "")
        self.channel = found.get("SKIW_ALERT_CHANNEL", "")  # the alert token is held only with it
        if self.environment not in ("production", "staging"):
            raise Refused(f"SKIW_ENVIRONMENT in {self.env_file} is not production or staging")

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
    problems = [
        f"{k} is {' '.join(seen.get(k, ['unset']))}, want {v[0]}"
        for k, v in want.items()
        if seen.get(k) != v
    ]
    return problems + sshd_matches(host, set(want))


def sshd_matches(host: Host, protected: set[str]) -> list[str]:
    """`sshd -T` shows only the global values, so a later `Match` block could weaken a checked key
    unseen. Closed policy: no Match block may set one, and no Include other than the drop-in
    directory is followed (so none can hide one)."""
    names = sorted(n for n in os.listdir(host.root / SSHD_DROP_INS) if n.endswith(".conf"))
    problems = []
    for rel in ["etc/ssh/sshd_config", *(f"{SSHD_DROP_INS}/{n}" for n in names)]:
        in_match = False
        for raw in host.read(rel).decode("utf-8").splitlines():
            words = re.split(r"[\s=]+", raw.strip(), maxsplit=1)
            key, arg = words[0].lower(), (words[1].strip() if len(words) > 1 else "")
            key = SSHD_ALIASES.get(key, key)
            if not key or key.startswith("#"):
                continue
            if any(c in key for c in SSHD_QUOTES):
                problems.append(f"/{rel} has a quoted or escaped keyword, which is not checked")
            elif key == "include" and arg != f"/{SSHD_DROP_INS}/*.conf":
                problems.append(f"/{rel} includes {arg}, which is not checked")
            elif key == "match":
                in_match = True
            elif in_match and key in protected:
                problems.append(f"/{rel} sets {key} inside a Match block")
    return problems


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
        elif line.startswith(ORIGINS):
            raise Bad("cannot read an origins line of apt-config dump")
    want = {
        "APT::Periodic::Update-Package-Lists": ["1"],
        "APT::Periodic::Unattended-Upgrade": ["1"],
        "APT::Periodic::Enable": dump.get("APT::Periodic::Enable") and ["1"],  # unset means on
        "Unattended-Upgrade::Allowed-Origins::": ["${distro_id}:${distro_codename}-security"],
        "Unattended-Upgrade::Origins-Pattern::": None,
        "Unattended-Upgrade::Automatic-Reboot": [host.values["auto_reboot"]],
    }
    problems = [f"{k} is {dump.get(k)}, want {v}" for k, v in want.items() if dump.get(k) != v]
    for key, values in dump.items():  # the whole subtrees: named children count as origins too
        if key.startswith(ORIGINS) and key not in [*want, *ORIGINS]:
            problems.append(f"{key} is set (every origin must be the security one)")
        if key in ORIGINS and values != [""]:
            problems.append(f"{key} has the value {values}")
    return problems + ([] if enabled == "enabled" else [f"unattended-upgrades is {enabled}"])


def docker_daemon(host: Host) -> list[str]:
    info = json.loads(host.tool(["docker", "info", "--format", "{{json .}}"]))
    config = json.loads(host.read("etc/docker/daemon.json"))
    live_options = info["SecurityOptions"]  # what the running daemon applies, not the file
    tcp = [h for h in config.get("hosts", []) if not str(h).startswith(("unix://", "fd://"))]
    problems = {
        "live-restore is off": info["LiveRestoreEnabled"] is not True,
        f"log driver is {info['LoggingDriver']}": info["LoggingDriver"] != "journald",
        "no-new-privileges is not set": config.get("no-new-privileges") is not True,
        "the running daemon lacks no-new-privileges": "name=no-new-privileges" not in live_options,
        f"daemon hosts {tcp}": bool(tcp),
    }
    return [problem for problem, failed in problems.items() if failed] + docker_start(host)


def docker_start(host: Host) -> list[str]:
    """How the daemon is started (systemd unit and drop-ins): only unix or fd hosts, and no other
    config file, whatever daemon.json says."""
    shown = host.tool(["systemctl", "show", "docker", "--property=ExecStart", "--value"])
    if not (found := re.search(r"argv\[\]=([^;]*);", shown)):
        raise Bad("cannot read the ExecStart of the docker unit")
    argv, problems, hosts = found[1].split(), [], []
    for i, arg in enumerate(argv):
        if arg in ("-H", "--host") and i + 1 < len(argv):
            hosts.append(argv[i + 1])
        elif arg.startswith(("--host=", "-H=")):
            hosts.append(arg.partition("=")[2])
        elif arg.startswith("-H") and len(arg) > 2:
            hosts.append(arg[2:])
        if arg == "--config-file" or arg.startswith("--config-file="):
            problems.append("dockerd is started with another --config-file")
    problems += [
        f"dockerd is started with host {h}" for h in hosts if not h.startswith(("fd://", "unix://"))
    ]
    return problems


def sockets(host: Host) -> list[str]:
    allowed = {"80", "443", host.values["ssh_port"]}
    problems = []
    for line in host.tool(["ss", "-H", "-tlnp"]).splitlines():
        fields = line.split()
        address, _, port = fields[3].rpartition(":")
        name = address.strip("[]").partition("%")[0]
        if fields[0] != "LISTEN" or not port.isdigit():
            raise Bad(f"cannot read `ss` line: {line.strip()}")
        if '(("dockerd",' in line:  # the Docker API belongs on its unix socket, loopback or not
            problems.append(f"dockerd listens on {fields[3]}")
            continue
        public = name == "*" or not ipaddress.ip_address(name).is_loopback  # "*": any address
        if public and port not in allowed:
            problems.append(f"{fields[3]} {' '.join(fields[5:])}".strip())
    return problems


def docker_group(host: Host) -> list[str]:
    users = apply.USERS
    return [
        f"{u} is in group docker" for u in users if "docker" in host.tool(["id", "-nG", u]).split()
    ]


def secret_store(host: Host) -> list[str]:
    try:
        apply.untrusted(host.root, [f"{SECRETS}/x"], lambda p: host.owner(p, p.lstat()))
    except Refused as exc:
        raise Bad(str(exc)) from None
    info = (host.root / SECRETS).lstat()  # the directory itself, never a link's target
    mode = stat.S_IMODE(info.st_mode)
    if not stat.S_ISDIR(info.st_mode) or host.owner(host.root / SECRETS, info) != (0, 0):
        return [f"/{SECRETS} is not a directory owned by root:root"]  # never listed through a link
    problems = [] if mode == DIR_MODE else [f"/{SECRETS} has mode {mode:04o}, want 0700"]
    names = sorted(os.listdir(host.root / SECRETS))
    wanted = held(host.environment, host.channel)
    problems += [f"{name} is missing" for name in sorted(wanted.keys() - set(names))]
    for name in names:
        if name not in OWNER and name != MARKER:
            problems.append(f"{name} is not in the inventory")
            continue
        if name == ALERT_CREDENTIAL and name not in wanted:  # decision 13 of the alert amendment
            problems.append(f"{name} is present, but SKIW_ALERT_CHANNEL is not {ALERT_CHANNEL}")
        elif name in OWNER and name not in wanted:
            problems.append(f"{name} is not held on {host.environment}")
        try:
            host.read(f"{SECRETS}/{name}", OWNER.get(name, 0), SECRET_MODE)
        except (Bad, OSError) as exc:
            problems.append(str(exc) if isinstance(exc, Bad) else f"{name}: {exc.strerror}")
    return problems


def secret_lines(host: Host) -> tuple[list[str], set[str], set[str]]:
    """Problems, the strings searched as substrings (16+ characters: a whole line, or the part
    after `v<n>:`) and the shorter ones, only compared whole; named by file, never shown."""
    problems, long, short = [], set(), set()
    for name, uid in sorted(held(host.environment, host.channel).items()):
        text = host.read(f"{SECRETS}/{name}", uid, SECRET_MODE).decode()
        lines = [line for line in text.splitlines() if line]
        if name == STATUS_KEY:  # the key body as one string; the armour lines are not secret
            body = [x for x in lines if not x.startswith("-----")]
            long |= {x for x in body if len(x) >= MIN_SECRET}  # one leaked body line is found too
            lines = ["".join(body)]
        if not lines:
            problems.append(f"{name} is empty")
        for line in lines:
            payload = m[1] if (m := KEY_LINE.fullmatch(line)) else line
            if len(payload) < MIN_SECRET:
                problems.append(
                    f"{name} is shorter than {MIN_SECRET} characters, so it cannot be searched"
                )
                short |= {line, payload}
            long |= {v for v in (line, payload) if len(v) >= MIN_SECRET}
    return problems, long, short


def environments(host: Host) -> list[tuple[str, list[str]]]:
    """(name, Env) of every running container, each requested id described exactly once."""
    ids = host.tool(["docker", "ps", "-q", "--no-trunc"]).split()
    if not all(CONTAINER_ID.fullmatch(i) for i in ids) or len(set(ids)) != len(ids):
        raise Bad("cannot read the container ids from docker ps")
    items = json.loads(host.tool(["docker", "inspect", *ids])) if ids else []
    if not isinstance(items, list) or sorted(
        str(item.get("Id")) if isinstance(item, dict) else "" for item in items
    ) != sorted(ids):
        raise Bad("docker inspect did not describe each running container exactly once")
    found = []
    for item in items:
        config, env = item.get("Config"), (item.get("Config") or {}).get("Env", 0)
        if not isinstance(config, dict) or not isinstance(item.get("Name"), str):
            raise Bad("docker inspect gave a container without Config or Name")
        if env is not None and not (isinstance(env, list) and all(isinstance(e, str) for e in env)):
            raise Bad("docker inspect gave an Env that is not null or a list of strings")
        found.append((item["Name"].lstrip("/"), env or []))
    return found


def container_env(host: Host) -> list[str]:
    problems, long, short = secret_lines(host)
    found = []
    for container, env in environments(host):
        for entry in env:
            variable, _, value = entry.partition("=")
            if any(v in value for v in long) or value in short:
                name = container if SAFE_NAME.fullmatch(container) else "a container"
                found.append(
                    f"{name} {variable if SAFE_NAME.fullmatch(variable) else 'a variable'}"
                )
    return problems + ([f"a secret value is in {', '.join(found)}"] if found else [])


def expected_roles() -> tuple[dict[str, tuple[str, ...]], Settings, Members]:
    """roles.sql read as data: each role's attributes and limit, its settings, its memberships."""
    lines = (DB / "roles.sql").read_text("utf-8").splitlines()
    sql = " ".join(line for line in lines if not line.lstrip().startswith("--"))
    settings = {
        (m[1], "0", f"{m[2]}={m[3]}")
        for m in re.finditer(r"ALTER ROLE (\w+) SET (\w+) = (\w+);", sql)
    }
    members: Members = {}
    for m in re.finditer(r"GRANT (\w+) TO (\w+)(?: WITH ([\w ,]+))?;", sql):
        # PostgreSQL 16+ defaults: no ADMIN, SET, INHERIT as the member role's own (INHERIT)
        noinherit = re.search(rf"ALTER ROLE {m[2]} [^;]*\bNOINHERIT\b", sql)
        options = {"ADMIN": "f", "INHERIT": "f" if noinherit else "t", "SET": "t"}
        for item in filter(None, (m[3] or "").split(",")):
            name, value = item.split()
            if name not in options or value not in ("TRUE", "FALSE", "OPTION"):
                raise ValueError(item)
            options[name] = "f" if value == "FALSE" else "t"
        members[(m[2], m[1])] = (options["ADMIN"], options["INHERIT"], options["SET"])
    attributes = {}
    for role, rest in re.findall(r"ALTER ROLE (\w+) ((?:NO)?LOGIN[^;]*);", sql):
        words = rest.split()
        limit = words[words.index("LIMIT") + 1] if "LIMIT" in words else "-1"
        attributes[role] = (*("t" if a in words else "f" for a in ATTRIBUTES), limit)
    return attributes, settings, members


def parse_roles(out: str) -> tuple[dict[str, tuple[int, tuple[str, ...]]], Settings, Members, int]:
    """The query's rows; a row of any other shape is only counted, never kept or shown."""
    roles: dict[str, tuple[int, tuple[str, ...]]] = {}
    settings: Settings = set()
    members: Members = {}
    bad = 0
    for line in filter(None, out.splitlines()):
        f = line.split("|")
        if (
            f[0] == "role"
            and len(f) == 10
            and f[1].isdigit()
            and f[2] not in roles
            and all(x in ("t", "f") for x in f[3:9])
            and re.fullmatch(r"-?[0-9]+", f[9])
        ):
            roles[f[2]] = (int(f[1]), tuple(f[3:10]))
        elif f[0] == "setting" and len(f) >= 4 and f[2].isdigit() and "=" in f[3]:
            settings.add((f[1], f[2], "|".join(f[3:])))
        elif f[0] == "member" and len(f) == 6 and all(x in ("t", "f") for x in f[3:6]):
            members[(f[1], f[2])] = () if (f[1], f[2]) in members else tuple(f[3:6])
        else:
            bad += 1
    return roles, settings, members, bad


def role_set(host: Host) -> list[str]:
    """The whole role inventory, as the database reports it through the socket as postgres
    (bootstrap-db's password-file wrapper), against roles.sql, `postgres` and PostgreSQL's own
    predefined roles. Messages carry only names that cannot hold database content: those of
    roles.sql, `postgres`, the predefined roles and roles.sql's setting names."""
    if host.compose is None or not host.compose.is_relative_to(host.root):
        raise Bad("needs --compose-file under the root (default /srv/skiw/compose.yml)")
    host.read(str(host.compose.relative_to(host.root)))  # root-owned, not a link: docker reads it
    compose = ["docker", "compose", "-f", str(host.compose), "--env-file", str(host.env_file)]
    host.read(apply.STATE, mode=apply.CONFIG)  # SKIW_IMAGE, written by skiw-deploy
    compose += ["--env-file", str(host.root / apply.STATE)]
    psql = [*compose, "exec", "-T", "db", "sh", "-c", psql_script()]
    roles, settings, members, bad = parse_roles(host.tool(psql, ROLES_QUERY))
    want, want_settings, want_members = expected_roles()
    system = {n for n, (oid, _) in roles.items() if n.startswith("pg_") and oid < FIRST_NORMAL_OID}
    known = {*want, BOOTSTRAP, *system}
    problems = [f"{bad} unparsable role rows"] if bad else []
    if extra := [n for n in roles if n not in known]:
        supers = sum(roles[n][1][1] == "t" for n in extra)
        problems.append(
            f"{len(extra)} roles not in roles.sql ({supers} superuser); list them with \\du"
        )
    oid, attributes = roles.get(BOOTSTRAP, (0, ()))
    if oid != BOOTSTRAP_OID or attributes[1:2] != ("t",):
        problems.append(f"{BOOTSTRAP} is not the bootstrap superuser")
    for name, wanted in want.items():
        if name not in roles:
            problems.append(f"{name} is missing")
        elif diff := [
            label for label, a, w in zip(LABELS, roles[name][1], wanted, strict=True) if a != w
        ]:
            problems.append(f"{name}: {', '.join(diff)} differ from roles.sql")
    for name in sorted(system):
        if roles[name][1][:3] != ("f", "f", "f"):
            problems.append(f"{name} can log in, is a superuser or bypasses RLS")
    named = {(role, conf.partition("=")[0]) for role, _, conf in want_settings}
    for role, _db, conf in sorted(settings - want_settings):
        setting = conf.partition("=")[0]
        label = role if role in known else "a role not in roles.sql"
        shown = setting if (role, setting) in named else "a setting"
        problems.append(f"{label}: {shown} is not as roles.sql sets it")
    present = {(role, conf.partition("=")[0]) for role, _, conf in settings}
    problems += [f"{role}: {name} is not set" for role, name in sorted(named - present)]
    allowed = {**BASELINE_MEMBERS, **want_members}
    for (member, group), options in sorted(members.items()):
        pair = f"{member} in {group}" if {member, group} <= known else "a role not in roles.sql"
        if (member, group) not in allowed:
            problems.append(f"unexpected membership: {pair}")
        elif not options:
            problems.append(f"{pair}: granted more than once")
        elif diff := [
            o
            for o, a, w in zip(MEMBER_OPTIONS, options, allowed[member, group], strict=True)
            if a != w
        ]:
            problems.append(f"{pair}: options differ from the allowed grant: {', '.join(diff)}")
    problems += [f"{m} is not a member of {g}" for m, g in sorted(allowed.keys() - members.keys())]
    return problems


def pg_hba(host: Host) -> list[str]:
    data = host.read(HBA, mode=HBA_MODE).decode("utf-8")
    rendered = render_hba(host.env_file, host.env_text)  # the env text read safely at start
    return [] if data == rendered else [f"/{HBA} differs from the file rendered from the env file"]


def stale_files(host: Host) -> list[str]:
    """Files apply would not install now, and owed reloads; reported, never removed."""
    problems = []
    for dest in apply.FAIL2BAN.values():
        if not host.ban and ((host.root / dest).exists() or (host.root / dest).is_symlink()):
            problems.append(f"/{dest} is present under the allowlist policy")
    for name in sorted(os.listdir(host.root / "etc/sudoers.d")):
        if name.startswith("skiw") and name not in ("skiw-ops", "skiw-deploy"):
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


def health_timers(host: Host) -> list[str]:
    """skiw-health's two timers (M1j) enabled and waiting; a stopped timer alerts nothing."""
    problems = []
    for timer in apply.TIMERS:
        for verb, want in (("is-enabled", "enabled"), ("is-active", "active")):
            done = host.run(["systemctl", verb, timer], b"")
            if (state := done.stdout.decode("utf-8", "replace").strip()) != want:
                problems.append(f"{timer} is {state if SAFE_NAME.fullmatch(state) else 'unknown'}")
    return problems


CHECKS: dict[str, Callable[[Host], list[str]]] = {
    "sshd": sshd,
    "nftables": nftables,
    "unattended-upgrades": unattended,
    "docker-daemon": docker_daemon,
    "listening-sockets": sockets,
    "docker-group": docker_group,
    "stale-files": stale_files,
    "secret-store": secret_store,
    "container-env": container_env,
    "role-set": role_set,
    "pg-hba": pg_hba,
    "health-timers": health_timers,
}


def main(
    argv: Sequence[str] | None = None, run: Runner = run_command, owner: Owner = stat_owner
) -> int:
    parser = argparse.ArgumentParser(prog="check-hardening", description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("/") / apply.ENV)
    parser.add_argument("--compose-file", type=Path, help=f"role-set; default /{apply.COMPOSE}")
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
