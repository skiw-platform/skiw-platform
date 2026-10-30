"""Every context that imports Django settings carries both session lifetime variables with a valid
value (plan M2b "Wiring"; UNI-16). A missing one is a start-up failure, so each context is checked
here and then started. Rendered host Compose: infra/host/tests/test_compose_config.py."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NAMES = ("SKIW_SESSION_ABSOLUTE_H", "SKIW_SESSION_IDLE_MIN")
VALUES = {"SKIW_SESSION_ABSOLUTE_H": "12", "SKIW_SESSION_IDLE_MIN": "30"}  # spec §8.1


def assignments(text: str, pattern: str) -> dict[str, str]:
    return {name: value for name, value in re.findall(pattern, text) if name in NAMES}


def env_file(path: str) -> dict[str, str]:
    return assignments((REPO / path).read_text(), r"(?m)^([A-Z0-9_]+)=(.*)$")


def tool_env() -> dict[str, str]:
    makefile = (REPO / "Makefile").read_text().replace("\\\n", " ")
    line = re.search(r"(?m)^TOOL_ENV := (.*)$", makefile)
    assert line is not None
    return assignments(line[1], r"([A-Z0-9_]+)=(\S+)")


def block(text: str, start: str, end: str) -> str:
    match = re.search(rf"(?ms)^{start}$(.*?)(?=^{end})", text)
    assert match is not None, start
    return match[1]


def label_step() -> dict[str, str]:
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    step = block(ci, r"      - name: Label image[^\n]*", r"      - ")
    for name in NAMES:
        assert f"-e {name} " in step or f"-e {name}\n" in step  # passed into the container
    return assignments(step, r'(?m)^ {10}([A-Z0-9_]+): "?([^"\n]*)"?$')


CONTEXTS = {
    "env/staging.env": lambda: env_file("infra/host/env/staging.env"),
    "env/production.env": lambda: env_file("infra/host/env/production.env"),
    "env/ci.env": lambda: env_file("infra/host/env/ci.env"),
    ".env.example": lambda: env_file(".env.example"),
    "Makefile TOOL_ENV": tool_env,
    "CI label step": label_step,
}


@pytest.mark.parametrize("context", CONTEXTS)
def test_context_carries_both_values(context: str) -> None:
    assert CONTEXTS[context]() == VALUES


@pytest.mark.parametrize("service", ["app", "worker"])
def test_local_compose_service_takes_both_from_the_env_file(service: str) -> None:
    compose = (REPO / "docker-compose.yml").read_text()
    environment = block(compose, f"  {service}:", r"  [a-z]+:|volumes:")
    for name in NAMES:
        assert f"      {name}: ${{{name}:?set in .env}}\n" in environment


@pytest.mark.parametrize("context", CONTEXTS)
def test_context_values_start_the_settings(context: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(REPO / "app"),
            "DJANGO_SECRET_KEY": "test-only-not-a-secret",
            "DATABASE_URL": "postgres://u:p@localhost:5432/db",
            **CONTEXTS[context](),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
