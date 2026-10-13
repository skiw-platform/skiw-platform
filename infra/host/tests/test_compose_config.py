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

HOST = Path(__file__).resolve().parents[1]
COMPOSE = HOST / "compose.yml"
ENV = HOST / "env"
PINNED = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")
SECRET_NAME = re.compile(r"SECRET|PASSWORD|TOKEN|KEY|KEK", re.IGNORECASE)
URL_PASSWORD = re.compile(r"://[^/@:]*:[^/@]*@")
BACKUPS = "/srv/skiw/backups"
PLANTED = token.token_urlsafe(24)  # generated per run; no fake secret is committed
FILES_READ_ONLY = {"web": False, "worker": False, "backup": True}  # FILE-03 M1 part, UNI-04

# H4 inventory: the only services that may hold each secret (TEN-02: skiw_backup only in backup).
APP_KEYS = {"tenant_token_key", "approval_mac_key", "tenant_source_key", "login_blob_key"}
APP_KEYS |= {"audit_mac_key", "field_kek", "blind_index_key", "crm_jar_kek"}
APP_SECRETS = APP_KEYS | {"django_secret_key", "skiw_app_password"}
SECRETS = {
    "web": APP_SECRETS,
    "worker": APP_SECRETS,
    "migrate": {"django_secret_key", "skiw_migrator_password", "tenant_token_key"}
    | {"approval_mac_key", "lookup_decoy_key"},
    "db": {"postgres_password"},
    "backup": {"skiw_backup_password"},
}

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
EXCEPTIONS = {
    ("caddy", "cap_add"): "H1 says NET_BIND_SERVICE; the daemon's no-new-privileges blocks the "
    "file capability for a non-root user (G13 open, plan §0)",
    ("clamav", "user"): "the image entrypoint starts as root, then runs clamd/freshclam as clamav",
    ("clamav", "read_only"): "the entrypoint edits /etc/clamav from CLAMD_CONF_* (H1 [A], M1i)",
    (
        "clamav",
        "cap_add",
    ): "CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID: the minimum it starts with",
    ("migrate", "restart"): "one-off, started only by skiw-deploy; a restart policy re-runs it",
    ("backup", "restart"): "one-off pre-migration dump in M1; M6 makes it the ops worker",
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
    return [
        f"{n}: {check}"
        for n, s in services(config)
        for check, ok in HARDENING.items()
        if not ok(s) and (n, check) not in EXCEPTIONS
    ]


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


def services(config: Config) -> list[tuple[str, Config]]:
    return sorted(config["services"].items())


CHECKS = [ports, egress, unpinned, unhardened, mounts, secrets, environment]


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
    (mounts, lambda c: c["services"]["web"]["volumes"].append({"source": BACKUPS})),
    (mounts, lambda c: c["services"]["migrate"].update(volumes=[{"source": "skiw-files"}])),
    (
        secrets,
        lambda c: c["services"]["worker"]["secrets"].append({"source": "skiw_backup_password"}),
    ),
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
]


@pytest.mark.parametrize(("check", "plant"), PLANTS)
def test_planted_violation_is_caught(
    config: Config, check: Callable[[Config], list[str]], plant: Callable[[Config], None]
) -> None:
    planted = copy.deepcopy(config)
    plant(planted)
    assert check(planted) != []


def test_worker_runs_runworker_with_the_declared_stop_grace(config: Config) -> None:
    values = declared("ci.env")
    worker = config["services"]["worker"]
    assert worker["command"] == ["python", "app/manage.py", "runworker"]
    assert worker["stop_grace_period"] == f"{values['SKIW_WORKER_STOP_GRACE_S']}s"
    assert int(values["SKIW_WORKER_STOP_GRACE_S"]) >= int(values["SKIW_WORKER_HARD_EXIT_S"])  # D5


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
    tagged = load(ENV / "ci.env", SKIW_IMAGE="ghcr.io/charliekhc/skiw-platform:latest")
    assert [problem.split(":")[0] for problem in unpinned(tagged)] == ["migrate", "web", "worker"]


@pytest.mark.parametrize("name", ["staging.env", "production.env"])
def test_host_env_files_refuse_to_render_until_complete(name: str) -> None:
    assert declared(name).keys() == declared("ci.env").keys() - {"SKIW_IMAGE"}
    assert render(ENV / name, SKIW_IMAGE=declared("ci.env")["SKIW_IMAGE"]).returncode != 0
    gaps = {k: declared("ci.env")[k] for k in ("SKIW_IMAGE", "SKIW_HOSTNAME")}  # set by deploy, G9
    gaps |= {
        k: declared("ci.env")[k] for k in ("SKIW_WORKER_HARD_EXIT_S", "SKIW_WORKER_STOP_GRACE_S")
    }
    filled = load(ENV / name, **gaps)  # M4 plan sets the worker values
    assert [problem for check in CHECKS for problem in check(filled)] == []
