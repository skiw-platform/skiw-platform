import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from procrastinate.contrib.django import app

from jobs.enqueue import JobEnqueueError, enqueue_in_tx
from jobs.tasks import noop

from .conftest import insert_probe_and_enqueue, separate

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]


class Rollback(Exception):
    pass


@app.task(queue="default")
def unregistered(probe_id: str) -> None:
    pass


def probe_rows(probe_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return separate("SELECT id FROM jobs_probe WHERE id = %s", probe_id)


def job_rows(probe_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return separate(
        "SELECT status::text, task_name, queue_name, args FROM procrastinate_jobs"
        " WHERE args->>'probe_id' = %s",
        str(probe_id),
    )


def test_commit_includes_the_job() -> None:
    probe_id = uuid.uuid4()
    job_id = insert_probe_and_enqueue(noop, probe_id)
    assert probe_rows(probe_id) == [(probe_id,)]
    assert job_rows(probe_id) == [("todo", noop.name, "default", {"probe_id": str(probe_id)})]
    assert separate("SELECT id FROM procrastinate_jobs WHERE id = %s", job_id) == [(job_id,)]


def test_rollback_excludes_the_job() -> None:
    probe_id = uuid.uuid4()
    with pytest.raises(Rollback), transaction.atomic():
        insert_probe_and_enqueue(noop, probe_id)
        raise Rollback
    assert probe_rows(probe_id) == []
    assert job_rows(probe_id) == []


def test_job_is_invisible_from_another_connection_before_commit() -> None:
    probe_id = uuid.uuid4()
    with transaction.atomic():
        insert_probe_and_enqueue(noop, probe_id)
        assert probe_rows(probe_id) == []
        assert job_rows(probe_id) == []
    assert probe_rows(probe_id) == [(probe_id,)]
    assert [row[0] for row in job_rows(probe_id)] == ["todo"]


def in_running_loop(probe_id: uuid.UUID) -> int:
    async def call() -> int:
        return enqueue_in_tx(noop, probe_id=probe_id)

    return asyncio.run(call())


REFUSED_INSIDE_ATOMIC: dict[str, Callable[[uuid.UUID], int]] = {
    "running event loop": in_running_loop,
    "agency_id keyword": lambda u: enqueue_in_tx(noop, probe_id=u, agency_id=uuid.uuid4()),
    "key outside the id schema": lambda u: enqueue_in_tx(noop, probe_id=u, other=uuid.uuid4()),
    "declared id missing": lambda u: enqueue_in_tx(noop),
    # Deliberately mistyped: a non-uuid value (which could carry PII) must be refused.
    "id that is not a uuid": lambda u: enqueue_in_tx(noop, probe_id=str(u)),  # type: ignore[arg-type]
    "task not from jobs.registry": lambda u: enqueue_in_tx(unregistered, probe_id=u),
}


def assert_refused_without_sql(call: Callable[[], int]) -> None:
    with CaptureQueriesContext(connection) as queries, pytest.raises(JobEnqueueError):
        call()
    assert len(queries) == 0


@pytest.mark.parametrize("call", REFUSED_INSIDE_ATOMIC.values(), ids=REFUSED_INSIDE_ATOMIC.keys())
def test_refusal_inside_atomic_runs_no_sql_and_leaves_no_job(
    call: Callable[[uuid.UUID], int],
) -> None:
    probe_id = uuid.uuid4()
    with transaction.atomic():
        assert_refused_without_sql(lambda: call(probe_id))
    assert job_rows(probe_id) == []


def test_refusal_outside_atomic_runs_no_sql_and_leaves_no_job() -> None:
    probe_id = uuid.uuid4()
    assert_refused_without_sql(lambda: enqueue_in_tx(noop, probe_id=probe_id))
    assert job_rows(probe_id) == []
