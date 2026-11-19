"""async_with_agency() as skiw_app, after `make migrate` (spec D26, §4.2 TEN-09 "sync and async
helpers"; plan M4c-8). The M4c-4b forged list, checked on `guard.current_agency()` and as the M4c-7b
row-level set on every registered case (the M4c-7a fixture pair included), the leak test on one
pooled connection, and cancellation. The module runs on one event loop, as a web process does,
with the pool at one connection, so every block reuses the same backend."""

import asyncio
import uuid
from collections.abc import Callable, Coroutine, Iterator, Sequence
from typing import Any, cast

import pytest
from django.db import connection
from django.db.backends.utils import CursorWrapper
from django.test import override_settings
from psycopg import AsyncConnection
from psycopg.errors import InsufficientPrivilege
from psycopg.pq import TransactionStatus

from tenancy import async_binding, binding, token
from tenancy.async_binding import async_with_agency
from tenancy.binding import with_agency
from tenancy.tests import isolation
from tenancy.tests.conftest import ABSENT, ACTIVE, RETIRED
from tenancy.tests.isolation import COUNT, DELETE, TOUCH, A, B, IsolationCase
from tenancy.tests.test_binding_live import FORGED
from tenancy.tests.test_row_level_live import FORGERIES
from tenancy.tests.test_token import VECTOR_KEY

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db", "fixture_pair")]

Conn = AsyncConnection[tuple[Any, ...]]
Mint = Callable[[int, uuid.UUID], str]
CASES = isolation.registry()
TABLES = sorted(CASES)


@pytest.fixture(scope="module")
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    with override_settings(SKIW_ASYNC_DB_POOL_MAX=1):
        yield loop
    if async_binding._pool is not None:
        loop.run_until_complete(async_binding._pool.close())
        async_binding._pool = None
    loop.close()


def run[T](loop: asyncio.AbstractEventLoop, body: Coroutine[Any, Any, T]) -> T:
    return loop.run_until_complete(body)


async def one(conn: Conn, query: str, params: Sequence[Any] = ()) -> Any:
    row = await (await conn.execute(query, params)).fetchone()
    assert row is not None
    return row[0]


async def current(conn: Conn) -> uuid.UUID | None:
    agency: uuid.UUID | None = await one(conn, "SELECT guard.current_agency()")
    return agency


async def setting(conn: Conn) -> str:
    value: str = await one(conn, "SELECT coalesce(current_setting('app.tenant_token', true), '')")
    return value


async def set_token(conn: Conn, value: str) -> None:
    await one(conn, "SELECT set_config('app.tenant_token', %s, true)", [value])


async def minter(conn: Conn) -> Mint:
    """Mints for this transaction's own xid and database, as an attacker with the key would."""
    xid, database = int(await one(conn, "SELECT pg_current_xact_id()::text")), conn.info.dbname
    return lambda version, agency: token.mint(version, VECTOR_KEY, database, agency, xid)


# M4c-4b's list (test_binding_live.FORGED), minted on the async connection.
ASYNC_FORGED: dict[str, Callable[[str, Mint], str]] = {
    "random": lambda own, mint: "not a token",
    "b-shaped-bad-mac": lambda own, mint: own.replace(str(A), str(B)),
    "truncated": lambda own, mint: own[:-1],
    "extra-field": lambda own, mint: own + ".x",
    "zero-mac": lambda own, mint: own.rsplit(".", 1)[0] + "." + "A" * 43,
    "unknown-version": lambda own, mint: mint(ABSENT, B),
    "retired-version": lambda own, mint: mint(RETIRED, B),
}


async def genuine_b() -> str:
    async with async_with_agency(B) as conn:
        return await setting(conn)


async def forge(conn: Conn, forgery: str, replayed: str) -> None:
    """Replace A's token in this transaction with the named forgery; `replayed` is a genuine B
    token captured before the block (a block inside it would be nested)."""
    if forgery == "replayed-b":
        value = replayed
    else:
        value = ASYNC_FORGED[forgery](await setting(conn), await minter(conn))
    await set_token(conn, value)


def test_the_forgeries_are_the_sync_lists() -> None:
    assert ASYNC_FORGED.keys() == FORGED.keys()
    assert {*ASYNC_FORGED, "replayed-b"} == FORGERIES.keys()


def test_inside_it_the_verifier_gives_that_agency_as_skiw_app(
    loop: asyncio.AbstractEventLoop,
) -> None:
    async def body() -> None:
        for agency in (A, B):
            async with async_with_agency(agency) as conn:
                assert await current(conn) == agency
                assert await one(conn, "SELECT current_user") == "skiw_app"

    run(loop, body())


@pytest.mark.usefixtures("vector_keys")
def test_it_mints_under_the_newest_key(
    loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
) -> None:
    keys = binding._token_keys()
    monkeypatch.setattr(async_binding, "_token_keys", lambda: ((ACTIVE, VECTOR_KEY), *keys))

    async def body() -> None:
        async with async_with_agency(A) as conn:
            assert (await setting(conn)).startswith(f"v{ACTIVE}.{A}.")
            assert await current(conn) == A

    run(loop, body())


@pytest.mark.usefixtures("vector_keys")
def test_the_control_a_token_under_an_active_key_does_switch(
    loop: asyncio.AbstractEventLoop,
) -> None:
    async def body() -> None:
        async with async_with_agency(A) as conn:
            await set_token(conn, (await minter(conn))(ACTIVE, B))
            assert await current(conn) == B

    run(loop, body())


def test_nesting_and_a_non_uuid_are_refused(loop: asyncio.AbstractEventLoop) -> None:
    async def body() -> None:
        async with async_with_agency(A) as conn:
            with pytest.raises(RuntimeError, match="nested"):
                async with async_with_agency(B):
                    pass
            assert await current(conn) == A
        for value in (str(A), A.bytes, A.int, None):
            with pytest.raises(TypeError, match=r"uuid\.UUID"):
                async with async_with_agency(cast(uuid.UUID, value)):
                    pass

    run(loop, body())


class Recorder:
    """Takes the place of the sync cursor a registered case inserts through, so the case's own
    SQL runs on the async connection."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Sequence[Any]]] = []

    def execute(self, sql: str, params: Sequence[Any]) -> None:
        self.calls.append((sql, params))


async def insert(conn: Conn, case: IsolationCase, agency: uuid.UUID, parents: Any) -> uuid.UUID:
    recorder = Recorder()
    row = case.insert(cast(CursorWrapper, recorder), agency, parents)
    for statement, params in recorder.calls:
        await conn.execute(statement, params)
    return row


async def affected(conn: Conn, case: IsolationCase, statement: str, row: uuid.UUID) -> int:
    """COUNT gives count(*); TOUCH and DELETE give the row count."""
    cursor = await conn.execute(statement.format(t=case.table), [row])
    if statement.startswith("SELECT"):
        fetched = await cursor.fetchone()
        assert fetched is not None
        return int(fetched[0])
    return cursor.rowcount


def visible(case: IsolationCase, agency: uuid.UUID, row: uuid.UUID) -> int:
    with with_agency(agency):
        return isolation._sql(case, COUNT, [row])


def test_commit_and_rollback(loop: asyncio.AbstractEventLoop) -> None:
    """A clean exit commits the block's writes; an error inside rolls them back, and the token
    goes with the transaction either way."""
    case = CASES["tenancy_fixture.parent"]  # no parents of its own
    rows: list[uuid.UUID] = []

    async def body(fail: bool) -> None:
        async with async_with_agency(A) as conn:
            rows.append(await insert(conn, case, A, {}))
            if fail:
                raise ValueError("boom")

    run(loop, body(False))
    with pytest.raises(ValueError, match="boom"):
        run(loop, body(True))
    assert [visible(case, A, row) for row in rows] == [1, 0]


@pytest.mark.usefixtures("vector_keys")
@pytest.mark.parametrize("forgery", sorted(FORGERIES))
@pytest.mark.parametrize("table", TABLES)
def test_a_forged_token_reaches_no_row(
    loop: asyncio.AbstractEventLoop, table: str, forgery: str
) -> None:
    """test_row_level_live's check on the async path: under a forged token, SELECT, UPDATE and
    DELETE reach neither B's row nor A's own, and an INSERT naming B is refused."""
    case = CASES[table]
    mine, theirs = isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)
    parents = isolation._parents(CASES, case, B)

    async def body() -> None:
        replayed = await genuine_b()
        async with async_with_agency(A) as conn:
            await forge(conn, forgery, replayed)
            assert await current(conn) is None
            for row in (mine, theirs):
                assert await affected(conn, case, COUNT, row) == 0, f"{table}: sees a row"
                if "UPDATE" in case.commands:
                    assert await affected(conn, case, TOUCH, row) == 0, f"{table}: updates"
                if "DELETE" in case.commands:
                    assert await affected(conn, case, DELETE, row) == 0, f"{table}: deletes"
        with pytest.raises(InsufficientPrivilege):
            async with async_with_agency(A) as conn:
                await forge(conn, forgery, replayed)
                await insert(conn, case, B, parents)

    run(loop, body())
    assert visible(case, B, theirs) == 1, f"{table}: B's row is gone"


@pytest.mark.parametrize("table", TABLES)
def test_a_plain_agency_id_or_commit_begin_reaches_no_other_row(
    loop: asyncio.AbstractEventLoop, table: str
) -> None:
    """`app.agency_id` set to B inside A's transaction changes nothing; after `COMMIT; BEGIN`
    inside the block, A's own row is hidden and an INSERT naming A is refused."""
    case = CASES[table]
    mine, theirs = isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)
    parents = isolation._parents(CASES, case, A)

    async def body() -> None:
        async with async_with_agency(A) as conn:
            await one(conn, "SELECT set_config('app.agency_id', %s, true)", [str(B)])
            assert await current(conn) == A
            assert [await affected(conn, case, COUNT, r) for r in (mine, theirs)] == [1, 0]
            await conn.execute("COMMIT")
            await conn.execute("BEGIN")
            assert (await setting(conn), await current(conn)) == ("", None)
            assert await affected(conn, case, COUNT, mine) == 0
        with pytest.raises(InsufficientPrivilege):
            async with async_with_agency(A) as conn:
                await conn.execute("COMMIT")
                await conn.execute("BEGIN")
                await insert(conn, case, A, parents)

    run(loop, body())


async def after_return() -> tuple[int, str, uuid.UUID | None]:
    """The pooled connection as the next user gets it: backend, token setting, verifier."""
    pool = async_binding._pool
    assert pool is not None
    stats = pool.get_stats()
    assert stats.get("pool_available", 0) == stats.get("pool_size", 0) == 1
    async with pool.connection() as conn:
        assert conn.info.transaction_status == TransactionStatus.IDLE
        return await one(conn, "SELECT pg_backend_pid()"), await setting(conn), await current(conn)


@pytest.mark.parametrize("table", TABLES)
def test_two_agencies_in_turn_on_one_pooled_connection_see_only_their_own(
    loop: asyncio.AbstractEventLoop, table: str
) -> None:
    case = CASES[table]
    rows = [isolation.make_row(CASES, case, A), isolation.make_row(CASES, case, B)]

    async def body() -> None:
        pids = set()
        for agency in (A, B):
            async with async_with_agency(agency) as conn:
                pids.add(await one(conn, "SELECT pg_backend_pid()"))
                seen = [await affected(conn, case, COUNT, row) for row in rows]
                assert seen == [int(agency == A), int(agency == B)], f"{table}: {agency}"
            pid, left, verified = await after_return()
            assert (left, verified) == ("", None), f"{table}: {agency}'s token outlived it"
            pids.add(pid)
        assert len(pids) == 1

    run(loop, body())


def idle_in_transaction(pid: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity"
            " WHERE pid = %s AND state LIKE 'idle in transaction%%'",
            [pid],
        )
        return int(cursor.fetchone()[0])


@pytest.mark.parametrize("waiting_on", ["event", "query"])
def test_a_cancelled_coroutine_leaves_no_transaction_and_returns_its_connection(
    loop: asyncio.AbstractEventLoop, waiting_on: str
) -> None:
    """D26 (5): a client disconnect cancels the coroutine, whether it waits on the event loop or
    on the database. Its transaction is rolled back and its connection is back in the pool."""
    pids: list[int] = []

    async def poll(entered: asyncio.Event) -> None:
        async with async_with_agency(A) as conn:
            pids.append(await one(conn, "SELECT pg_backend_pid()"))
            entered.set()
            if waiting_on == "query":
                await conn.execute("SELECT pg_sleep(30)")
            await asyncio.Event().wait()

    async def body() -> tuple[int, str, uuid.UUID | None]:
        entered = asyncio.Event()
        task = asyncio.ensure_future(poll(entered))
        await entered.wait()
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return await after_return()

    pid, left, verified = run(loop, asyncio.wait_for(body(), timeout=10))
    assert (left, verified) == ("", None)
    assert idle_in_transaction(pids[0]) == 0
    assert pid == pids[0]  # the same connection, rolled back and reused
