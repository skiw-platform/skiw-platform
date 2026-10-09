import asyncio
import uuid

from django.db import connections
from procrastinate.contrib.django import app
from procrastinate.contrib.django.django_connector import DjangoConnector

from .registry import JobTask, id_schema


class JobEnqueueError(RuntimeError):
    pass


def enqueue_in_tx(task: JobTask, /, **ids: uuid.UUID) -> int:
    """Defer `task` inside the caller's open transaction (EVT-01). M0c subset of spec D5
    "Staging": the agency derivation, RLS id check and args_mac arrive in M4, same signature.
    Every refusal happens before any SQL."""
    if _event_loop_running():
        # .defer_async() runs on another thread, outside the caller's transaction.
        raise JobEnqueueError("enqueue_in_tx is synchronous; it refuses a running event loop")
    connector = app.connector
    if not isinstance(connector, DjangoConnector) or not (
        connections[connector.alias].in_atomic_block
    ):
        raise JobEnqueueError("enqueue_in_tx must run inside transaction.atomic()")
    if "agency_id" in ids:
        raise JobEnqueueError("the agency is derived, never passed in (spec D5)")
    schema = id_schema(task)
    if schema is None:
        raise JobEnqueueError("task is not registered through jobs.registry")
    if set(ids) != set(schema) or not all(isinstance(v, uuid.UUID) for v in ids.values()):
        raise JobEnqueueError(f"task {task.name} takes exactly the uuid ids {sorted(schema)}")
    # Job args are JSON: uuids travel as canonical strings and registry.parse_id reads them back.
    return task.defer(**{name: str(value) for name, value in ids.items()})


def _event_loop_running() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True
