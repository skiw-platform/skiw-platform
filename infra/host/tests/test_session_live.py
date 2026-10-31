"""A session survives a restart and a redeploy of the one `web` container (spec §9 M2; owner Q3
(a); plan M2d). Through Caddy over HTTPS, on a throwaway stack of its own (test_edge_live.py's
fixture, a fresh instance for this module), against the edge_probe session views, which run the
real middleware and session store. The tests run in file order and share one session; the
negative control goes last because it replaces the key."""

import base64
import importlib
import json
import secrets
import subprocess
import time
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:  # mypy names the module by its path; pytest imports it by file name
    import tests.test_edge_live as edge
    from tests.test_edge_live import Reply, Stack
else:
    edge = importlib.import_module("test_edge_live")
    Reply, Stack = edge.Reply, edge.Stack

COOKIE = "__Host-skiw_session"
VALUE = "X-Probe-Value"  # edge_probe/urls.py
COUNT_ROWS = (  # the password stays inside the db container
    'PGPASSWORD="$(cat /run/secrets/postgres_password)" exec psql -X -At -U postgres -d skiw '
    '-c "SELECT count(*) FROM django_session"'
)
live = pytest.mark.host_live
stack = edge.stack


class Session:
    cookie = ""
    value = ""


def session_cookie(reply: Reply) -> Morsel[str]:
    jar: SimpleCookie = SimpleCookie()
    for header in reply.headers.get_all("Set-Cookie") or []:
        jar.load(header)
    return jar[COOKIE]


def readyz(stack: Stack) -> None:
    for _ in range(60):
        try:
            if stack.fetch("/readyz").status == 200:
                return
        except OSError:  # web or Caddy not accepting yet
            pass
        time.sleep(1)
    pytest.fail("/readyz did not answer 200 through Caddy within 60 s")


def get(stack: Stack) -> Reply:
    """204: the session holds the value set by the first test; 404: the session is empty."""
    headers = {"Cookie": f"{COOKIE}={Session.cookie}", VALUE: Session.value}
    return stack.fetch("/probe/session/get", headers=headers)


def rows(stack: Stack) -> int:
    return int(stack.run("exec", "-T", "db", "sh", "-c", COUNT_ROWS).strip())


def web(stack: Stack) -> tuple[str, str]:
    """(container ID, image ID) of the running web container."""
    container = stack.run("ps", "-q", "web").strip()
    inspect = [stack.command[0], "inspect", "--format", "{{.Image}}", container]
    image = subprocess.run(inspect, capture_output=True, text=True, check=True).stdout.strip()
    return container, image


@live
def test_session_survives_a_restart_of_web(stack: Stack) -> None:
    stack.serving("web")
    reply = stack.fetch("/probe/session/set")
    assert reply.status == 204
    Session.cookie, Session.value = session_cookie(reply).value, reply.headers[VALUE]
    assert get(stack).status == 204
    before = rows(stack)

    stack.run("restart", "web")
    readyz(stack)
    assert get(stack).status == 204
    assert rows(stack) == before


@live
def test_session_survives_a_redeploy_of_web(stack: Stack) -> None:
    assert Session.cookie, "needs the session of the restart test"
    old = web(stack)
    label = f"skiw.test.redeploy={secrets.token_hex(4)}"
    image = edge.build_image(stack.command[0], "--label", label)
    assert image != old[1]
    stack.env["SKIW_IMAGE"] = image  # what skiw-deploy writes to the state file (M1g)
    stack.run("run", "--rm", "migrate")
    stack.run("up", "-d", "--no-deps", "--wait", "web")
    new = web(stack)
    assert new[0] != old[0] and new[1] == image
    readyz(stack)
    assert get(stack).status == 204


@live
def test_a_replaced_source_key_logs_the_session_out(stack: Stack) -> None:
    """Negative control: the same cookie, with a key the row was not sealed under."""
    assert Session.cookie, "needs the session of the restart test"
    secrets_config = json.loads(stack.run("config", "--format", "json"))["secrets"]
    key = Path(secrets_config["tenant_source_key"]["file"])
    key.write_text("v2:" + base64.b64encode(secrets.token_bytes(32)).decode() + "\n")
    stack.run("up", "-d", "--no-deps", "--force-recreate", "--wait", "web")
    readyz(stack)
    reply = get(stack)
    assert reply.status == 404
    deleted = session_cookie(reply)
    assert deleted.value == "" and deleted["max-age"] == "0"
