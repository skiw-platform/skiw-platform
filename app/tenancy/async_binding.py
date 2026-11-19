"""`async_with_agency()`: the async twin of `with_agency()` for the bridge long-poll, the one async
view (spec D26, §4.2 "Tenant binding" item 2, TEN-09; plan M4c-8). Django's ORM has no transactions
in async code, so this runs on its own small per-process pool of psycopg connections as skiw_app,
built from the same `DATABASES["default"]` on first use. Semgrep `tenancy-async-pool` keeps the
pool class out of every other module. `bridge.db` re-exports this when the bridge lands (plan §9
item 5).

Each block is one transaction: BEGIN, read the xid, mint the token under the newest key, set it
transaction-locally, yield the connection, COMMIT; an exception, a cancellation included, rolls it
back, and the connection goes back to the pool idle, with no token. The pool runs in autocommit,
so outside a block no statement can leave a transaction open. The token is never logged.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, cast

from django.conf import settings
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from tenancy import token
from tenancy.binding import _token_keys

Conn = AsyncConnection[tuple[Any, ...]]

_pool: "AsyncConnectionPool[Conn] | None" = None
_bound: ContextVar[bool] = ContextVar("tenancy_async_bound", default=False)


def _new_pool() -> "AsyncConnectionPool[Conn]":
    """Closed until first use. One connection is kept open; it grows to SKIW_ASYNC_DB_POOL_MAX."""
    db = settings.DATABASES["default"]
    params = {"dbname": db["NAME"], "user": db["USER"], "password": db["PASSWORD"]}
    params |= {"host": db["HOST"], "port": db["PORT"], **db["OPTIONS"]}
    return AsyncConnectionPool(
        kwargs={**params, "autocommit": True},
        min_size=1,
        max_size=settings.SKIW_ASYNC_DB_POOL_MAX,
        open=False,
        name="tenancy-async",
    )


async def _get_pool() -> "AsyncConnectionPool[Conn]":
    global _pool
    if _pool is None:
        _pool = _new_pool()
    await _pool.open()  # a no-op once open
    return _pool


@asynccontextmanager
async def async_with_agency(agency_id: uuid.UUID) -> AsyncIterator[Conn]:
    """One transaction on a pooled connection, bound to `agency_id`. Refused when nested in the
    same task: the inner block would hold a second pooled connection while the outer one waits."""
    if not isinstance(agency_id, uuid.UUID):
        raise TypeError("async_with_agency() takes a uuid.UUID")
    if _bound.get():
        raise RuntimeError("async_with_agency() cannot be nested")
    version, key = _token_keys()[0]
    pool = await _get_pool()
    reset = _bound.set(True)
    try:
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute("SELECT pg_current_xact_id()::text, current_database()")
            xid, database = cast(tuple[str, str], await cursor.fetchone())  # always one row
            value = token.mint(version, key, database, agency_id, int(xid))
            await conn.execute("SELECT set_config('app.tenant_token', %s, true)", [value])
            yield conn
    finally:
        _bound.reset(reset)
