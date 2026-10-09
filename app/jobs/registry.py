import contextlib
import functools
import uuid
from collections.abc import Callable, Mapping
from types import MappingProxyType

from procrastinate.contrib.django import app
from procrastinate.tasks import Task

type JobTask = Task[..., None, ...]
type Handler = Callable[..., None]

# Task -> {id argument: table}. The tables are checked under RLS from M4 (spec D5 step 1b).
_id_schemas: dict[JobTask, Mapping[str, str]] = {}


def job(name: str, queue: str, ids: Mapping[str, str]) -> Callable[[Handler], JobTask]:
    """Register a production task. Its arguments are the declared ids only (spec D5). The name is
    stored in every job row, so it is explicit and never derived from the module path."""
    schema = MappingProxyType(dict(ids))

    def register(handler: Handler) -> JobTask:
        @functools.wraps(handler)
        def run(**args: object) -> None:
            # Undeclared fields are ignored (EVT-03); a bad id fails the job before the handler.
            handler(**{name: parse_id(name, args.get(name)) for name in schema})

        task: JobTask = app.task(name=name, queue=queue)(run)
        _id_schemas[task] = schema
        return task

    return register


def id_schema(task: JobTask) -> Mapping[str, str] | None:
    return _id_schemas.get(task)


def parse_id(name: str, raw: object) -> uuid.UUID:
    if isinstance(raw, str):
        with contextlib.suppress(ValueError):
            value = uuid.UUID(raw)
            if str(value) == raw:
                return value
    raise ValueError(f"job argument {name!r} is not a canonical uuid string")
