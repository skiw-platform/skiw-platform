import inspect
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from procrastinate.contrib.django import app
from procrastinate.jobs import DeleteJobCondition

from jobs.enqueue import enqueue_in_tx
from jobs.registry import id_schema, job
from jobs.tasks import noop
from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parents[2]
# Registered by Procrastinate itself; nothing defers it and skiw_app cannot run it (spec §4.1).
BUILTIN_TASKS = {
    "builtin:procrastinate.builtin_tasks.remove_old_jobs",
    "procrastinate.builtin_tasks.remove_old_jobs",
}

SAMPLE = uuid.UUID("0f0f0f0f-aaaa-4bbb-8ccc-dddddddddddd")
received: list[object] = []


@job(name="jobs.test_record", queue="default", ids={"probe_id": "jobs_probe"})
def record(probe_id: uuid.UUID) -> None:
    received.append(probe_id)


@pytest.fixture(autouse=True)
def clear_received() -> None:
    received.clear()


def test_production_settings_register_only_the_probe_task() -> None:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(APP_DIR),
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_SECRET_KEY": "test-only-not-a-secret",
        "DATABASE_URL": "postgres://u:p@localhost:5432/db",
        **REQUIRED,
    }
    code = (
        "import json, django; django.setup();"
        "from procrastinate.contrib.django import app; print(json.dumps(sorted(app.tasks)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    assert set(json.loads(result.stdout)) - BUILTIN_TASKS == {"jobs.noop"}
    assert noop.name == "jobs.noop"


def test_registry_records_the_typed_id_schema() -> None:
    assert id_schema(noop) == {"probe_id": "jobs_probe"}
    assert id_schema(app.tasks["builtin:procrastinate.builtin_tasks.remove_old_jobs"]) is None


def test_handler_receives_a_uuid_parsed_from_the_stored_string() -> None:
    probe_id = uuid.uuid4()
    record(probe_id=str(probe_id))  # how the worker calls a task: task(**job.task_kwargs)
    assert received == [probe_id]
    assert isinstance(received[0], uuid.UUID)


def test_handler_ignores_undeclared_fields() -> None:
    probe_id = uuid.uuid4()
    record(probe_id=str(probe_id), added_later="x")
    assert received == [probe_id]


@pytest.mark.parametrize(
    "raw",
    [
        "not-a-uuid",
        "",
        str(SAMPLE).upper(),
        SAMPLE.hex,
        f"{{{SAMPLE}}}",
        f"urn:uuid:{SAMPLE}",
        1,
        None,
    ],
)
def test_malformed_id_fails_the_job_before_the_handler_runs(raw: object) -> None:
    with pytest.raises(ValueError, match="probe_id"):
        record(probe_id=raw)
    assert received == []


def test_missing_id_fails_the_job_before_the_handler_runs() -> None:
    with pytest.raises(ValueError, match="probe_id"):
        record()
    assert received == []


def test_enqueue_signature_takes_one_positional_task_and_ids_only() -> None:
    params = list(inspect.signature(enqueue_in_tx).parameters.values())
    assert [(p.name, p.kind) for p in params] == [
        ("task", inspect.Parameter.POSITIONAL_ONLY),
        ("ids", inspect.Parameter.VAR_KEYWORD),
    ]


def test_worker_never_deletes_finished_jobs() -> None:
    # The worker command adds no delete_jobs of its own, so the worker gets these defaults.
    assert app._worker().delete_jobs is DeleteJobCondition.NEVER
