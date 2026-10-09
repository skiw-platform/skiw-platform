"""Defer -> fetch -> finish -> retry as skiw_app, spec §4.1 "Procrastinate queue grants" (ii).
The worker runs in-process on the connector `manage.py procrastinate worker` uses."""

import asyncio
import contextlib
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import psycopg
import pytest
from django.utils import timezone
from procrastinate import App, RetryStrategy
from procrastinate.contrib.django import app
from procrastinate.contrib.django.django_connector import DjangoConnector
from procrastinate.exceptions import ConnectorException
from procrastinate.periodic import PeriodicDeferrer, PeriodicRegistry

from jobs.registry import job
from jobs.tasks import noop

from .conftest import insert_probe_and_enqueue, separate

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]


@job(name="jobs.test_failing_probe", queue="probe_failing", ids={"probe_id": "jobs_probe"})
def failing_probe(probe_id: uuid.UUID) -> None:
    raise RuntimeError("failing probe")


# One retry, zero wait. jobs.registry has no retry option until a production task needs one.
failing_probe.retry_strategy = RetryStrategy(max_attempts=1)


@app.task(queue="probe_periodic")
def periodic_probe(timestamp: int) -> None:
    pass


@contextlib.asynccontextmanager
async def worker_app() -> AsyncIterator[App]:
    """Swap in the worker connector exactly as the worker command does: psycopg, built from
    Django's database settings, so it connects as skiw_app."""
    connector = app.connector
    assert isinstance(connector, DjangoConnector)
    with app.replace_connector(connector.get_worker_connector()) as worker:
        async with worker.open_async():
            yield worker


def run_worker_until(done: Callable[[], bool], queue: str, **options: Any) -> None:
    async def run() -> None:
        async with worker_app() as worker:
            running = asyncio.create_task(
                worker.run_worker_async(
                    queues=[queue],
                    install_signal_handlers=False,
                    fetch_job_polling_interval=0.1,
                    **options,
                )
            )
            try:
                async with asyncio.timeout(20):
                    while not await asyncio.to_thread(done):
                        if running.done():
                            running.result()  # a worker crash (e.g. a missing grant) surfaces here
                        await asyncio.sleep(0.1)
            finally:
                running.cancel()  # graceful stop: finishes jobs, then unregisters the worker
                with contextlib.suppress(asyncio.CancelledError):
                    await running

    asyncio.run(run())


def job_state(job_id: int) -> tuple[Any, ...]:
    return separate(
        "SELECT status::text, attempts, worker_id FROM procrastinate_jobs WHERE id = %s", job_id
    )[0]


def events(job_id: int) -> list[str]:
    # skiw_app has no SELECT on procrastinate_events (spec §4.1); the audit reads as the owner.
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT type::text FROM procrastinate_events WHERE job_id = %s ORDER BY id", (job_id,)
        )
        return [event for (event,) in rows]


def test_worker_prunes_registers_runs_heartbeats_and_unregisters() -> None:
    ((stalled,),) = separate(
        "INSERT INTO procrastinate_workers (last_heartbeat)"
        " VALUES (now() - interval '1 hour') RETURNING id"
    )
    probe_id = uuid.uuid4()
    job_id = insert_probe_and_enqueue(noop, probe_id)
    seen: dict[str, Any] = {}

    def done() -> bool:
        workers = separate(
            "SELECT id, last_heartbeat FROM procrastinate_workers WHERE id > %s", stalled
        )
        if not workers:
            return False
        worker_id, heartbeat = workers[0]
        seen.setdefault("worker_id", worker_id)
        seen.setdefault("first_heartbeat", heartbeat)
        seen["stalled_left"] = separate(
            "SELECT id FROM procrastinate_workers WHERE id = %s", stalled
        )
        seen["job"] = job_state(job_id)
        return bool(seen["job"][0] == "succeeded" and heartbeat > seen["first_heartbeat"])

    run_worker_until(done, "default", update_heartbeat_interval=0.2)

    assert seen["stalled_left"] == []  # pruned on start
    assert seen["job"] == ("succeeded", 1, seen["worker_id"])  # fetched by the registered worker
    assert separate("SELECT id FROM procrastinate_workers WHERE id = %s", seen["worker_id"]) == []
    assert separate("SELECT args FROM procrastinate_jobs WHERE id = %s", job_id) == [
        ({"probe_id": str(probe_id)},)
    ]
    assert events(job_id) == ["deferred", "started", "succeeded"]


def test_failing_job_retries_once_then_fails_and_admin_retry_requeues_it() -> None:
    job_id = insert_probe_and_enqueue(failing_probe, uuid.uuid4())

    run_worker_until(lambda: job_state(job_id)[0] == "failed", "probe_failing")
    assert job_state(job_id)[:2] == ("failed", 2)
    retried = ["deferred", "started", "scheduled", "deferred_for_retry", "started", "failed"]
    assert events(job_id) == retried

    # Admin retry (EVT-05) on the Django connection, as the app would run it.
    app.job_manager.retry_job_by_id(job_id, retry_at=timezone.now())
    assert job_state(job_id)[:2] == ("todo", 3)

    run_worker_until(lambda: job_state(job_id)[0] == "failed", "probe_failing")
    assert job_state(job_id)[:2] == ("failed", 4)
    assert events(job_id)[len(retried) :] == ["scheduled", "retried", "started", "failed"]


def test_each_periodic_tick_defers_one_job_and_drops_the_previous_ticks_row() -> None:
    periodic_id = uuid.uuid4().hex
    registry = PeriodicRegistry()  # type: ignore[no-untyped-call]  # unannotated upstream
    periodic = registry.register_task(
        task=periodic_probe, cron="* * * * *", periodic_id=periodic_id, configure_kwargs={}
    )
    first = int(time.time())
    second = first + 60

    def tick(timestamp: int) -> list[tuple[Any, ...]]:
        # The call the worker's periodic deferrer makes on every tick (EVT-06).
        async def defer() -> None:
            async with worker_app():
                await PeriodicDeferrer(registry=registry).defer_jobs([(periodic, timestamp)])

        asyncio.run(defer())
        return separate(
            "SELECT defer_timestamp, job_id FROM procrastinate_periodic_defers"
            " WHERE periodic_id = %s",
            periodic_id,
        )

    ((first_tick, first_job),) = tick(first)
    ((second_tick, second_job),) = tick(second)
    assert (first_tick, second_tick) == (first, second)
    assert separate(
        "SELECT id, args FROM procrastinate_jobs WHERE id IN (%s, %s) ORDER BY id",
        first_job,
        second_job,
    ) == [(first_job, {"timestamp": first}), (second_job, {"timestamp": second})]


def test_builtin_old_job_cleanup_cannot_run_as_the_app_role() -> None:
    # Body of Procrastinate's builtin remove_old_jobs task; skiw_app has no DELETE on jobs.
    async def cleanup() -> None:
        async with worker_app() as worker:
            await worker.job_manager.delete_old_jobs(nb_hours=0)

    with pytest.raises(ConnectorException) as raised:
        asyncio.run(cleanup())
    assert isinstance(raised.value.__cause__, psycopg.errors.InsufficientPrivilege)
