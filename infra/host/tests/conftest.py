import os
import shutil
import subprocess

import pytest


@pytest.fixture(scope="session")
def docker_cli() -> str:
    """The docker CLI with a running daemon; skips locally without one, fails in CI."""
    path = shutil.which("docker")
    if path and subprocess.run([path, "info"], capture_output=True, check=False).returncode == 0:
        return path
    if os.environ.get("CI") == "true":
        pytest.fail("no Docker daemon in CI: the live host tests must run, not skip")
    pytest.skip("no Docker daemon locally; CI runs the live host tests")
