import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from jobs.startup import require_migrated

pytestmark = pytest.mark.live

APP = Path(__file__).resolve().parents[2]
ENTRYPOINTS = {
    # The ASGI server imports the app inside a running event loop; so must this.
    "web": [
        sys.executable,
        "-c",
        "import asyncio\nasync def main():\n    import config.asgi\nasyncio.run(main())",
    ],
    "worker": [sys.executable, str(APP / "manage.py"), "runworker"],
}


def run(argv: list[str]) -> subprocess.Popen[str]:
    """An entrypoint exactly as the containers start it: as skiw_app, nothing else in env."""
    env = {
        **os.environ,
        "PYTHONPATH": str(APP),
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    return subprocess.Popen(argv, env=env, stderr=subprocess.PIPE, text=True)


@pytest.mark.usefixtures("live_db")
def test_a_fully_migrated_database_passes_the_gate() -> None:
    require_migrated()


@pytest.mark.usefixtures("live_db")
def test_the_gate_names_the_unapplied_migration(unapplied_jobs_migration: None) -> None:
    with pytest.raises(ImproperlyConfigured, match=r"unapplied migrations.*jobs\.0001"):
        require_migrated()


@pytest.mark.usefixtures("live_db")
@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_entrypoints_refuse_to_start_when_a_migration_is_unapplied(
    entrypoint: str, unapplied_jobs_migration: None
) -> None:
    process = run(ENTRYPOINTS[entrypoint])
    _, stderr = process.communicate(timeout=60)
    assert process.returncode != 0
    assert "unapplied migrations" in stderr


@pytest.mark.usefixtures("live_db")
def test_the_web_entrypoint_starts_when_fully_migrated() -> None:
    process = run(ENTRYPOINTS["web"])
    _, stderr = process.communicate(timeout=60)
    assert process.returncode == 0, stderr


@pytest.mark.usefixtures("live_db")
def test_the_worker_entrypoint_keeps_running_when_fully_migrated() -> None:
    process = run(ENTRYPOINTS["worker"])
    try:
        time.sleep(4)
        assert process.poll() is None, "worker exited: " + (
            process.stderr.read() if process.stderr else ""
        )
    finally:
        process.terminate()
        process.communicate(timeout=30)
