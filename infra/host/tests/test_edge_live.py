"""Edge tests through Caddy (spec §8.4 H1, UNI-17, FILE-02; plan §3 M1c).

The `host_live` tests run only under `make host-test-live`. They build the app image, start caddy,
web and db from compose.yml with env/ci.env plus tests/edge/compose.edge.yml (ci.Caddyfile with
`tls internal`, loopback ports, the probe settings, the stub upstream), and point every secret at
values generated per run in a temp dir. Without a Docker daemon they skip locally and fail in CI.
"""

import base64
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

import pytest

from skiw_host.bootstrap_db import render_hba

HOST = Path(__file__).resolve().parents[1]
REPO = HOST.parents[1]
COMPOSE = HOST / "compose.yml"
EDGE = HOST / "tests" / "edge" / "compose.edge.yml"
HOSTNAME = "skiw.test"  # SKIW_HOSTNAME in env/ci.env
HSTS = "max-age=31536000"
CSP = re.compile(  # set by Django (app/shell/csp.py); host tooling imports no app code (UNI-04)
    r"default-src 'self'; script-src 'nonce-[A-Za-z0-9_-]{22}' 'strict-dynamic'; "
    r"object-src 'none'; frame-ancestors 'none'"
)
SPOOFED_IP = "203.0.113.9"  # TEST-NET-3
ROOT_CA = "/data/caddy/pki/authorities/local/root.crt"
live = pytest.mark.host_live


@dataclass
class Reply:
    status: int
    headers: Message
    body: bytes


@dataclass
class Stack:
    command: list[str]
    env: dict[str, str]
    tls: ssl.SSLContext | None = None

    def run(self, *args: str) -> str:
        result = subprocess.run(
            [*self.command, *args], env=self.env, capture_output=True, text=True, timeout=600
        )
        assert result.returncode == 0, f"compose {args[0]} failed:\n{result.stderr[-3000:]}"
        return result.stdout

    def port(self, target: int) -> int:
        return int(self.run("port", "caddy", str(target)).strip().rsplit(":", 1)[1])

    def fetch(
        self,
        path: str,
        *,
        https: bool = True,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: float = 10.0,
    ) -> Reply:
        tls = self.tls if https else None
        return fetch(
            self.port(443 if https else 80),
            path,
            tls,
            method=method,
            headers=headers,
            body=body,
            timeout=timeout,
        )

    def serving(self, upstream: str | None) -> None:
        """Make `web`, the stub (network alias `web`) or nothing answer behind Caddy."""
        self.run("stop", *(s for s in ("web", "stub") if s != upstream))
        if upstream is not None:
            self.run("up", "-d", "--wait", upstream)


def fetch(
    port: int,
    path: str,
    tls: ssl.SSLContext | None,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 10.0,
) -> Reply:
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    if tls is not None:
        sock = tls.wrap_socket(sock, server_hostname=HOSTNAME)
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    connection.sock = sock
    try:
        connection.request(method, path, body=body, headers={"Host": HOSTNAME, **(headers or {})})
        response = connection.getresponse()
        return Reply(response.status, response.headers, response.read())
    finally:
        connection.close()


def write_secrets(command: list[str], env: dict[str, str], directory: Path) -> dict[str, str]:
    """One random value per secret that compose.yml declares; never committed, never printed."""
    rendered = subprocess.run(
        [*command, "config", "--format", "json"], env=env, capture_output=True, text=True
    )
    assert rendered.returncode == 0, rendered.stderr
    directory.mkdir()
    files = {}
    for name in json.loads(rendered.stdout)["secrets"]:
        value = secrets.token_urlsafe(24)
        if not name.endswith("_password"):
            value = "v1:" + base64.b64encode(secrets.token_bytes(32)).decode()
        path = directory / name
        path.write_text(value + "\n")
        path.chmod(0o644)  # read by container uids 999 and 10001
        files[name] = str(path)
    return files


def build_image(path: str, *extra: str) -> str:
    """The local image ID is the sha256 digest of the image config: content-addressed like the
    registry digest compose.yml requires on hosts, without pushing anything."""
    built = subprocess.run([path, "build", "-q", *extra, str(REPO)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr[-3000:]
    return built.stdout.strip()


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory, docker_cli: str) -> Iterator[Stack]:
    """One throwaway Compose project per test module (test_session_live.py reuses it)."""
    path = docker_cli
    env = {**os.environ, "SKIW_IMAGE": build_image(path)}
    env_file = ["--env-file", str(HOST / "env" / "ci.env")]
    tmp = tmp_path_factory.mktemp("edge")
    every = ["--profile", "deploy", "--profile", "ops"]
    files = write_secrets([path, "compose", "-f", str(COMPOSE), *env_file, *every], env, tmp / "s")
    for role in ("app", "migrator"):
        password = Path(files[f"skiw_{role}_password"]).read_text().strip()
        env[f"EDGE_{role.upper()}_PASSWORD"] = password
    hba = tmp / "pg_hba.conf"
    hba.write_text(render_hba(HOST / "env" / "ci.env"))
    override = tmp / "secrets.json"
    override.write_text(
        json.dumps(
            {
                "secrets": {n: {"file": f} for n, f in files.items()},
                "configs": {"pg_hba": {"file": str(hba)}},
            }
        )
    )
    files_args = ["-f", str(COMPOSE), "-f", str(EDGE), "-f", str(override), *env_file]
    project = ["-p", f"skiw-edge-{secrets.token_hex(4)}", "--profile", "deploy"]
    stack = Stack([path, "compose", *files_args, *project, "--profile", "stub"], env)
    try:
        stack.run("up", "-d", "--wait", "db")
        stack.run("run", "--rm", "migrate")
        stack.run("up", "-d", "--wait", "web", "caddy")
        stack.tls = wait_for_tls(stack)
        yield stack
    finally:
        stack.run("down", "-v", "--remove-orphans")


def wait_for_tls(stack: Stack) -> ssl.SSLContext:
    for _ in range(30):
        try:
            tls = ssl.create_default_context(
                cadata=stack.run("exec", "-T", "caddy", "cat", ROOT_CA)
            )
            if fetch(stack.port(443), "/healthz", tls).status == 200:
                return tls
        except (AssertionError, OSError, ssl.SSLError):
            pass
        time.sleep(1)
    pytest.fail("Caddy did not serve /healthz over TLS within 30 s")


def test_host_caddy_config_carries_no_test_override() -> None:
    def rules(name: str) -> str:
        lines = (HOST / "caddy" / name).read_text().splitlines()
        return "\n".join(line for line in lines if not line.lstrip().startswith("#"))

    production = rules("Caddyfile") + rules("edge.caddy")
    for marker in ("tls internal", "local_certs", "skip_install_trust", "trusted_proxies"):
        assert marker not in production
    assert "admin off" in rules("Caddyfile")
    assert "ci.Caddyfile" not in (HOST / "compose.yml").read_text()


@live
def test_production_caddyfile_adapts(stack: Stack) -> None:
    adapt = ["caddy", "adapt", "--config", "/etc/caddy/Caddyfile"]
    adapted = stack.run("run", "--rm", "--no-deps", "caddy", *adapt)
    assert json.loads(adapted)["admin"] == {"disabled": True}
    assert '"internal"' not in adapted and "trusted_proxies" not in adapted


@live
def test_plain_http_redirect_carries_hsts_and_ignores_forwarded_headers(stack: Stack) -> None:
    spoofed = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "evil.example"}
    reply = stack.fetch("/a?b=1", https=False, headers=spoofed)
    assert reply.status == 308
    assert reply.headers["Location"] == f"https://{HOSTNAME}/a?b=1"
    assert reply.headers.get_all("Strict-Transport-Security") == [HSTS]
    assert reply.headers["Server"] == "Caddy"  # answered by Caddy; never reached Django


@live
def test_app_page_carries_hsts_and_csp_once(stack: Stack) -> None:
    stack.serving("web")
    reply = stack.fetch("/")
    assert reply.status == 200
    assert reply.headers.get_all("Strict-Transport-Security") == [HSTS]  # Caddy's and Django's
    policies = reply.headers.get_all("Content-Security-Policy") or []
    assert len(policies) == 1
    assert CSP.fullmatch(policies[0]), policies[0]


@live
def test_client_forwarded_headers_do_not_reach_django(stack: Stack) -> None:
    stack.serving("web")
    plain = json.loads(stack.fetch("/edge-probe").body)
    spoofed_headers = {"X-Forwarded-Proto": "http", "X-Forwarded-For": SPOOFED_IP}
    spoofed = json.loads(stack.fetch("/edge-probe", headers=spoofed_headers).body)
    assert spoofed["secure"] is True
    assert spoofed == plain  # Django sees the client address Caddy saw, not the client's claim
    assert ipaddress.ip_address(spoofed["forwarded_for"]) != ipaddress.ip_address(SPOOFED_IP)


@live
def test_body_cap_is_25_mb(stack: Stack) -> None:
    stack.serving("web")
    over = stack.fetch("/edge-probe", method="POST", body=bytes(26 * 1024 * 1024), timeout=60)
    assert over.status == 413  # FILE-02 outer cap
    under = stack.fetch("/edge-probe", method="POST", body=bytes(20 * 1000 * 1000), timeout=60)
    # A 20 MB upload still reaches web: Django's CSRF check answers it, not Caddy's cap (M2d).
    assert (under.status, under.headers["X-Skiw-Csrf"]) == (403, "rejected")


@live
def test_maintenance_page_when_web_is_down(stack: Stack) -> None:
    stack.serving(None)
    reply = stack.fetch("/")
    assert reply.status == 503
    assert reply.headers["Retry-After"].isdigit()
    assert reply.headers.get_all("Strict-Transport-Security") == [HSTS]
    assert b"SKIW is being updated" in reply.body


@live
def test_25_second_response_completes_through_caddy(stack: Stack) -> None:
    stack.serving("stub")
    started = time.monotonic()
    reply = stack.fetch("/long-poll", timeout=45)
    assert (reply.status, reply.body) == (200, b"done")
    assert time.monotonic() - started >= 25
