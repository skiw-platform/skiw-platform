"""Compose config tests for infra/host/compose.yml (spec §8.4 H1, H2, H4, H6; §9 M1).

They parse `docker compose config --format json`, so they need the Compose CLI but no daemon.
Without docker they skip locally and fail when CI=true. Each check returns its violations; the
planted cases below prove every check catches what it is for.
"""

import copy
import json
import os
import re
import secrets as token
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from skiw_host import health
from skiw_host.secrets import INVENTORY, OWNER

HOST = Path(__file__).resolve().parents[1]
COMPOSE = HOST / "compose.yml"
ENV = HOST / "env"
PINNED = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")
SECRET_NAME = re.compile(r"SECRET|PASSWORD|TOKEN|KEY|KEK", re.IGNORECASE)
URL_PASSWORD = re.compile(r"://[^/@:]*:[^/@]*@")
BACKUPS = "/srv/skiw/backups"
HBA_TARGET = "/etc/skiw/pg_hba.conf"
PLANTED = token.token_urlsafe(24)  # generated per run; no fake secret is committed
MIGRATE_KEY = "lookup_decoy_key"  # a planted case drops it from migrate (M4c-3)
FILES_READ_ONLY = {"web": False, "worker": False, "backup": True}  # FILE-03 M1 part, UNI-04

# H4 inventory (skiw_host.secrets, used by bootstrap-secrets): the only services that may hold
# each secret (TEN-02: skiw_backup only in backup) and the uid that owns each file.
SECRETS: dict[str, set[str]] = {}
for item in INVENTORY:
    for reader in item.readers:
        SECRETS.setdefault(reader, set()).add(item.name)

# UNI-01 escape hatch: `Any` types the JSON that docker compose prints; its values are mixed
# (strings, numbers, lists, nested maps) and belong to an external tool.
Config = dict[str, Any]

HARDENING: dict[str, Callable[[Config], bool]] = {
    "user": lambda s: str(s.get("user", "root")).split(":")[0] not in {"", "0", "root"},
    "read_only": lambda s: s.get("read_only") is True,
    "cap_drop": lambda s: s.get("cap_drop") == ["ALL"],
    "cap_add": lambda s: not s.get("cap_add"),
    "no_new_privileges": lambda s: "no-new-privileges:true" in s.get("security_opt", []),
    "privileged": lambda s: not s.get("privileged"),
    "mem_limit": lambda s: bool(s.get("mem_limit")),
    "pids_limit": lambda s: isinstance(s.get("pids_limit"), int) and s["pids_limit"] > 0,
    "restart": lambda s: s.get("restart") == "unless-stopped",
    "journald": lambda s: s.get("logging", {}).get("driver") == "journald",
}
CLAMAV_CAPS = {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"}
# A named exception is bounded: the check may fail only with the documented value, so a wider
# capability set or an automatic restart of a one-off job is still a violation.
EXCEPTIONS: dict[tuple[str, str], tuple[str, Callable[[Config], bool]]] = {
    ("caddy", "cap_add"): (
        "H1 says NET_BIND_SERVICE; the daemon's no-new-privileges blocks the file capability for "
        "a non-root user (G13 open, plan §0)",
        lambda s: set(s.get("cap_add") or []) == {"NET_BIND_SERVICE"},
    ),
    ("clamav", "user"): (
        "the image entrypoint starts as root, then runs clamd/freshclam as clamav",
        lambda s: True,
    ),
    ("clamav", "read_only"): (
        "the entrypoint edits /etc/clamav from CLAMD_CONF_* (H1 [A], M1i)",
        lambda s: True,
    ),
    ("clamav", "cap_add"): (
        "CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID: the minimum it starts with",
        lambda s: set(s.get("cap_add") or []) <= CLAMAV_CAPS,
    ),
    ("migrate", "restart"): (
        "one-off, started only by skiw-deploy; a restart policy re-runs it",
        lambda s: s.get("restart") == "no",
    ),
    ("backup", "restart"): (
        "one-off pre-migration dump in M1; M6 makes it the ops worker",
        lambda s: s.get("restart") == "no",
    ),
}


def docker() -> str:
    path = shutil.which("docker")
    if path is not None:
        version = subprocess.run([path, "compose", "version"], capture_output=True, check=False)
        if version.returncode == 0:
            return path
    if os.environ.get("CI") == "true":
        pytest.fail("docker compose is not available in CI: the Compose tests must run, not skip")
    pytest.skip("docker compose is not installed locally; CI runs these tests")


def render(env_file: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/nonexistent"), **overrides}
    profiles = ["--profile", "deploy", "--profile", "ops"]
    command = ["compose", "-f", str(COMPOSE), "--env-file", str(env_file), *profiles, "config"]
    return subprocess.run(
        [docker(), *command, "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def load(env_file: Path, **overrides: str) -> Config:
    result = render(env_file, **overrides)
    assert result.returncode == 0, result.stderr
    config: Config = json.loads(result.stdout)
    return config


def declared(name: str) -> dict[str, str]:
    lines = (ENV / name).read_text().splitlines()
    pairs = (line.partition("=") for line in lines if line and not line.startswith("#"))
    return {key: value for key, _, value in pairs}


@pytest.fixture(scope="module")
def config() -> Config:
    return load(ENV / "ci.env")


def ports(config: Config) -> list[str]:
    expected = {"caddy": ["443", "80"]}
    found = {
        n: sorted(str(p["published"]) for p in s.get("ports", [])) for n, s in services(config)
    }
    return [f"{n} publishes {p}" for n, p in found.items() if p != expected.get(n, [])]


def egress(config: Config) -> list[str]:
    networks = config["networks"]
    return [
        f"{name} is on {net}"
        for name in ("db", "backup")
        for net in config["services"][name].get("networks", {})
        if not networks[net].get("internal")
    ]


def unpinned(config: Config) -> list[str]:
    return [
        f"{n}: {s.get('image')}"
        for n, s in services(config)
        if "build" in s or not PINNED.fullmatch(s.get("image", ""))
    ]


def unhardened(config: Config) -> list[str]:
    problems = []
    for n, s in services(config):
        for check, ok in HARDENING.items():
            if ok(s):
                continue
            exception = EXCEPTIONS.get((n, check))
            if exception is None:
                problems.append(f"{n}: {check}")
            elif not exception[1](s):
                problems.append(f"{n}: {check} is outside its named exception")
    return problems


def mounts(config: Config) -> list[str]:
    problems = []
    for n, s in services(config):
        for volume in s.get("volumes", []):
            if str(volume.get("source", "")).startswith(BACKUPS) and n != "backup":
                problems.append(f"{n} mounts {BACKUPS}")
            read_only = bool(volume.get("read_only"))
            if volume.get("source") == "skiw-files" and FILES_READ_ONLY.get(n) != read_only:
                problems.append(f"{n} mounts skiw-files read_only={volume.get('read_only')}")
    return problems


def secrets(config: Config) -> list[str]:
    held = {n: {x["source"] for x in s.get("secrets", [])} for n, s in services(config)}
    files = {n: x.get("file") for n, x in config.get("secrets", {}).items()}
    return [f"{n} holds {sorted(h)}" for n, h in held.items() if h != SECRETS.get(n, set())] + [
        f"secret {n} from {f}" for n, f in files.items() if f != f"/etc/skiw/secrets/{n}"
    ]


def owners(config: Config) -> list[str]:
    """Each secret file's inventory owner is the uid of every service that mounts it (H4)."""
    return [
        f"{n} runs as {s.get('user')}, {x['source']} is owned by {OWNER.get(x['source'])}"
        for n, s in services(config)
        for x in s.get("secrets", [])
        if str(s.get("user", "")).split(":")[0] != str(OWNER.get(x["source"]))
    ]


def environment(config: Config) -> list[str]:
    problems = []
    for n, s in services(config):
        for key, value in (s.get("environment") or {}).items():
            if key.endswith("_FILE"):
                if not str(value).startswith("/run/secrets/"):
                    problems.append(f"{n}: {key} is not a /run/secrets path")
            elif SECRET_NAME.search(key) or URL_PASSWORD.search(str(value)):
                problems.append(f"{n}: {key} carries a secret value")  # never print the value
    return problems


def file_secrets(config: Config) -> list[str]:
    """Every *_FILE names a secret the same service mounts (plan M4c-3): a path to a secret it does
    not hold would fail only at run time, in the one service that reads it."""
    return [
        f"{n}: {key} names a secret it does not mount"
        for n, s in services(config)
        for key, value in (s.get("environment") or {}).items()
        if key.endswith("_FILE")
        and str(value).removeprefix("/run/secrets/")
        not in {x["source"] for x in s.get("secrets", [])}
    ]


def hba(config: Config) -> list[str]:
    """`db` reads the pg_hba.conf that `bootstrap-db prepare` renders (H6), as a Compose config."""
    expected = {"db": [{"source": "pg_hba", "target": HBA_TARGET}]}
    problems = [
        f"{n} has configs {s.get('configs')}"
        for n, s in services(config)
        if s.get("configs") != expected.get(n)
    ]
    if f"hba_file={HBA_TARGET}" not in config["services"]["db"].get("command", []):
        problems.append("db does not start with the mounted hba_file")
    if config.get("configs", {}).get("pg_hba", {}).get("file") != "/etc/skiw/db/pg_hba.conf":
        problems.append("pg_hba is not read from /etc/skiw/db/pg_hba.conf")
    return problems


def services(config: Config) -> list[tuple[str, Config]]:
    return sorted(config["services"].items())


CHECKS = [
    ports,
    egress,
    unpinned,
    unhardened,
    mounts,
    secrets,
    owners,
    environment,
    file_secrets,
    hba,
]


@pytest.mark.parametrize("check", CHECKS)
def test_ci_config_passes(config: Config, check: Callable[[Config], list[str]]) -> None:
    assert check(config) == []


def test_every_exception_is_still_needed(config: Config) -> None:
    stale = [key for key in EXCEPTIONS if HARDENING[key[1]](config["services"][key[0]])]
    assert stale == []


PLANTS: list[tuple[Callable[[Config], list[str]], Callable[[Config], None]]] = [
    (ports, lambda c: c["services"]["web"].update(ports=[{"published": "8000", "target": 8000}])),
    (ports, lambda c: c["services"]["caddy"]["ports"][0].update(published="8080")),
    (egress, lambda c: c["services"]["db"]["networks"].update(egress=None)),
    (unpinned, lambda c: c["services"]["clamav"].update(image="clamav/clamav:1.5.4")),
    (unhardened, lambda c: c["services"]["web"].update(read_only=False)),
    (unhardened, lambda c: c["services"]["db"].update(user="0")),
    (unhardened, lambda c: c["services"]["caddy"]["cap_add"].append("SYS_ADMIN")),
    (unhardened, lambda c: c["services"]["clamav"]["cap_add"].append("SYS_ADMIN")),
    (unhardened, lambda c: c["services"]["migrate"].update(restart="always")),
    (unhardened, lambda c: c["services"]["backup"].update(restart="always")),
    (mounts, lambda c: c["services"]["web"]["volumes"].append({"source": BACKUPS})),
    (mounts, lambda c: c["services"]["migrate"].update(volumes=[{"source": "skiw-files"}])),
    (
        secrets,
        lambda c: c["services"]["worker"]["secrets"].append({"source": "skiw_backup_password"}),
    ),
    (owners, lambda c: c["services"]["backup"].update(user="10001:10001")),
    (
        environment,
        lambda c: c["services"]["web"]["environment"].update(
            DATABASE_URL=f"postgres://skiw_app:{PLANTED}@db/skiw"
        ),
    ),
    (
        environment,
        lambda c: c["services"]["worker"]["environment"].update(DJANGO_SECRET_KEY=PLANTED),
    ),
    (
        file_secrets,
        lambda c: c["services"]["migrate"]["environment"].update(
            TENANT_SOURCE_KEY_FILE="/run/secrets/tenant_source_key"
        ),
    ),
    (
        file_secrets,
        lambda c: c["services"]["migrate"].update(
            secrets=[x for x in c["services"]["migrate"]["secrets"] if x["source"] != MIGRATE_KEY]
        ),
    ),
    (hba, lambda c: c["services"]["db"].update(command=["postgres"])),
    (hba, lambda c: c["configs"]["pg_hba"].update(file="./db/pg_hba.conf")),
]


@pytest.mark.parametrize(("check", "plant"), PLANTS)
def test_planted_violation_is_caught(
    config: Config, check: Callable[[Config], list[str]], plant: Callable[[Config], None]
) -> None:
    planted = copy.deepcopy(config)
    plant(planted)
    assert check(planted) != []


def test_clamav_reports_a_scan_cut_short_by_a_limit(config: Config) -> None:
    """Without AlertExceedsMax clamd answers `stream: OK` for a file it stopped scanning at a limit
    (spec H5 step 3, FILE-01; DECISIONS 2026-10-23 M1i)."""
    environment = config["services"]["clamav"]["environment"]
    assert environment["CLAMD_CONF_AlertExceedsMax"] == "yes"
    limits = ("MaxFileSize", "MaxScanSize", "MaxRecursion", "MaxFiles")
    assert not [key for key in environment if key.removeprefix("CLAMD_CONF_") in limits]


def test_worker_runs_runworker_with_the_declared_stop_grace(config: Config) -> None:
    values = declared("ci.env")
    worker = config["services"]["worker"]
    assert worker["command"] == ["python", "app/manage.py", "runworker"]
    assert worker["stop_grace_period"] == f"{values['SKIW_WORKER_STOP_GRACE_S']}s"
    assert int(values["SKIW_WORKER_STOP_GRACE_S"]) >= int(values["SKIW_WORKER_HARD_EXIT_S"])  # D5


SESSION_LIFETIME = ("SKIW_SESSION_ABSOLUTE_H", "SKIW_SESSION_IDLE_MIN")  # D6, §8.1 (M2b)
# Interim auth values (owner Q6 (a), plan M3b): T5, Flow 5.1, T18, §8.1.
AUTH_VALUES = (
    *(f"SKIW_ARGON2_{n}" for n in ("MEMORY_KIB", "TIME_COST", "PARALLELISM")),
    *(f"SKIW_AUTH_{n}" for n in ("FAILS_PER_ACCOUNT", "FAILS_PER_IP", "WINDOW_MIN")),
    *(f"SKIW_AUTH_{n}" for n in ("LOCK_AFTER", "LOCK_MIN")),
    "SKIW_STEPUP_MAX_AGE_MIN",
    "SKIW_TOTP_SKEW_STEPS",
    "SKIW_LOGIN_PENDING_MIN",
    "SKIW_ENROL_LINK_MIN",
    "SKIW_PW_MIN_LENGTH",
)
# The one deployment agency (plan M4c-5): migrate seeds it, web's /readyz binds to it.
AGENCY_VALUES = ("SKIW_DEPLOYMENT_AGENCY_ID", "SKIW_DEPLOYMENT_AGENCY_NAME")
SETTINGS_VALUES = SESSION_LIFETIME + AUTH_VALUES + AGENCY_VALUES
DB_ROLE = {"web": "skiw_app", "worker": "skiw_app", "migrate": "skiw_migrator"}


def test_every_settings_importer_gets_the_bounded_values_and_keeps_its_role(
    config: Config,
) -> None:
    values = declared("ci.env")
    for name, role in DB_ROLE.items():
        env = config["services"][name]["environment"]
        assert {k: env[k] for k in SETTINGS_VALUES} == {k: values[k] for k in SETTINGS_VALUES}
        assert env["DATABASE_URL"] == f"postgres://{role}@db:5432/{values['SKIW_POSTGRES_DB']}"
        assert env["DATABASE_PASSWORD_FILE"] == f"/run/secrets/{role}_password"


def test_each_environment_has_its_own_single_agency_id() -> None:
    """One canonical uuid per environment (PROJECT §9 gate), never shared between them, so a
    staging id cannot reach production; the owner gave the staging and production names."""
    files = ("ci.env", "staging.env", "production.env")
    ids = [declared(name)["SKIW_DEPLOYMENT_AGENCY_ID"] for name in files]
    assert all(re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", i) for i in ids)
    assert len(set(ids)) == len(ids)
    names = {name: declared(name)["SKIW_DEPLOYMENT_AGENCY_NAME"] for name in files}
    assert names == {
        "ci.env": "CI agency",
        "staging.env": "SK iWealth (staging)",
        "production.env": "SK iWealth Sdn. Bhd.",
    }


@pytest.mark.parametrize("name", SETTINGS_VALUES)
def test_a_missing_bounded_value_refuses_to_render(name: str) -> None:
    assert render(ENV / "ci.env", **{name: ""}).returncode != 0


@pytest.mark.parametrize("key", ["tenant_source_key", "login_blob_key"])
def test_only_web_and_worker_read_the_app_key_from_its_secret_file(
    config: Config, key: str
) -> None:
    """Plans M2c, M3b: <KEY>_FILE is a secret-file path on web and worker only; migrate imports
    settings without it (spec §8.4 H4)."""
    variable = key.upper()
    holders = {
        name: service["environment"][f"{variable}_FILE"]
        for name, service in services(config)
        if f"{variable}_FILE" in (service.get("environment") or {})
    }
    assert holders == dict.fromkeys(("web", "worker"), f"/run/secrets/{key}")
    for name in holders:
        assert key in {s["source"] for s in config["services"][name]["secrets"]}
    for _, service in services(config):
        assert variable not in (service.get("environment") or {})


def test_web_worker_and_migrate_read_the_tenant_token_key_from_its_secret_file(
    config: Config,
) -> None:
    """Plan M4c-4b: web and worker mint under it (with_agency()); migrate writes it into
    guard.tenant_mac_key (M4c-3). No service takes the key value from the environment."""
    holders = {
        name: service["environment"]["TENANT_TOKEN_KEY_FILE"]
        for name, service in services(config)
        if "TENANT_TOKEN_KEY_FILE" in (service.get("environment") or {})
    }
    assert holders == dict.fromkeys(("web", "worker", "migrate"), "/run/secrets/tenant_token_key")
    for name in holders:
        assert "tenant_token_key" in {s["source"] for s in config["services"][name]["secrets"]}
    for _, service in services(config):
        assert "TENANT_TOKEN_KEY" not in (service.get("environment") or {})


def test_migrate_reads_both_guard_keys_from_their_secret_files(config: Config) -> None:
    """Plan M4c-3: the key writes after `migrate` (tenancy.keys) read these two files; migrate is
    the only reader of lookup_decoy_key (H4)."""
    env = config["services"]["migrate"]["environment"]
    keys = {k: v for k, v in env.items() if k.endswith("_FILE") and "KEY" in k}
    names = ("tenant_token_key", "lookup_decoy_key", "django_secret_key")
    assert keys == {f"{name.upper()}_FILE": f"/run/secrets/{name}" for name in names}
    assert not [
        k
        for k in env
        if k.removesuffix("_FILE") in {n.upper() for n in names[:2]} and not k.endswith("_FILE")
    ]


def test_profiles_and_networks(config: Config) -> None:
    values = declared("ci.env")
    profiles = {n: s.get("profiles") for n, s in services(config) if s.get("profiles")}
    assert profiles == {"migrate": ["deploy"], "backup": ["ops"]}  # TEN-01: only skiw-deploy
    networks = config["networks"]
    assert sorted(n for n, net in networks.items() if net.get("internal")) == ["app", "ops"]
    subnets = {n: net["ipam"]["config"][0]["subnet"] for n, net in networks.items()}
    assert subnets == {n: values[f"SKIW_NET_{n.upper()}"] for n in ("edge", "app", "ops", "egress")}


def test_app_image_must_be_set_and_pinned() -> None:
    assert render(ENV / "ci.env", SKIW_IMAGE="").returncode != 0
    tagged = load(ENV / "ci.env", SKIW_IMAGE="ghcr.io/skiw-dev1/skiw-platform:latest")
    assert [problem.split(":")[0] for problem in unpinned(tagged)] == ["migrate", "web", "worker"]
    assert render(ENV / "ci.env", SKIW_BACKUP_IMAGE="").returncode != 0
    tagged = load(ENV / "ci.env", SKIW_BACKUP_IMAGE="ghcr.io/skiw-dev1/skiw-predeploy:latest")
    assert [problem.split(":")[0] for problem in unpinned(tagged)] == ["backup"]


@pytest.mark.parametrize("name", ["staging.env", "production.env"])
def test_host_env_files_refuse_to_render_until_complete(name: str) -> None:
    assert declared(name).keys() == declared("ci.env").keys() - {"SKIW_IMAGE"}
    assert render(ENV / name, SKIW_IMAGE=declared("ci.env")["SKIW_IMAGE"]).returncode != 0
    gaps = {k: declared("ci.env")[k] for k in ("SKIW_IMAGE", "SKIW_HOSTNAME")}  # set by deploy, G9
    gaps["SKIW_BACKUP_IMAGE"] = declared("ci.env")["SKIW_BACKUP_IMAGE"]  # published by CI (M1h)
    gaps |= {
        k: declared("ci.env")[k] for k in ("SKIW_WORKER_HARD_EXIT_S", "SKIW_WORKER_STOP_GRACE_S")
    }
    filled = load(ENV / name, **gaps)  # M4 plan sets the worker values
    assert [problem for check in CHECKS for problem in check(filled)] == []


# RAM rule (amendment 2026-10-25 decision 3): the caps without the one-off `migrate` fit the plan's
# RAM minus 1 GiB for the host. Plans: production Hostinger KVM 2, staging KVM 1 (owner 2026-10-26).
PLAN_MIB = {"production.env": 8192, "staging.env": 4096}
HOST_MIB = 1024
CLAMAV_MIB = 1280  # ClamAV needs it to load its signatures [A]
MEMORY = re.compile(r"([1-9][0-9]*)([mg])")


def mebibytes(value: str) -> int:
    match = MEMORY.fullmatch(value)
    if match is None:
        raise ValueError(f"not a memory cap in m or g: {value!r}")
    return int(match[1]) * (1024 if match[2] == "g" else 1)


def caps(name: str) -> dict[str, int]:
    return {k: mebibytes(v) for k, v in declared(name).items() if k.startswith("SKIW_MEM_")}


@pytest.mark.parametrize("name", sorted(PLAN_MIB))
def test_memory_caps_fit_the_plan(name: str) -> None:
    found = caps(name)
    total = sum(v for k, v in found.items() if k != "SKIW_MEM_MIGRATE")
    assert total <= PLAN_MIB[name] - HOST_MIB, f"{name}: {total} MiB of caps without migrate"
    assert found["SKIW_MEM_CLAMAV"] >= CLAMAV_MIB


@pytest.mark.parametrize("value", ["512", "512k", "512M", "1.5g", "0m", "", " 512m"])
def test_memory_cap_parse_refuses_other_forms(value: str) -> None:
    with pytest.raises(ValueError):
        mebibytes(value)


def test_skiw_health_watches_every_service_that_always_runs(config: Config) -> None:
    always = sorted(n for n, s in services(config) if not s.get("profiles"))
    assert always == sorted(health.SERVICES) and config["name"] == health.PROJECT  # plan §3 M1j
