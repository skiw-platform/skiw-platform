"""`with_agency()`: the only place a tenant token is minted and set (spec §4.2 "Tenant binding"
item 2, TEN-09; plan M4c-4b). The token names the agency and this transaction's xid, under the
newest tenant_token_key version; `guard.current_agency()` (tenancy/0003) is its only reader.

The keys are read once per process, newest first, as accounts.source_key does: config.asgi and
`runworker` call token_keys() at start-up, so a missing or malformed key stops the process before
it serves. Rotation (item 1) adds a version and restarts web and worker, so the cache never holds
a version `migrate` has not written. The token is never logged or returned.
"""

import functools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from django.conf import settings
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from tenancy import token


@functools.cache
def token_keys() -> tuple[tuple[int, bytes], ...]:
    """The tenant_token_key versions, newest first, read once. Raises (fail closed) when the key
    is missing or malformed."""
    return tuple(settings.SKIW_TENANT_TOKEN_KEYS())


@contextmanager
def with_agency(agency_id: uuid.UUID) -> Iterator[None]:
    """One transaction bound to `agency_id`. Refused inside an open atomic block (and so nested):
    a second token on the same xid could name another agency. A nested atomic() inside keeps the
    xid (a savepoint), so the binding holds for the whole block."""
    if not isinstance(agency_id, uuid.UUID):
        raise TypeError("with_agency() takes a uuid.UUID")
    if connection.in_atomic_block:
        raise TransactionManagementError("with_agency() cannot run inside an atomic block")
    version, key = token_keys()[0]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_current_xact_id()::text, current_database()")
            xid, database = cursor.fetchone()
            value = token.mint(version, key, database, agency_id, int(xid))
            # The driver cursor, not Django's wrapper: the debug wrapper (DEBUG, or
            # force_debug_cursor) logs every query with its parameters, and this one is the token.
            cursor.cursor.execute("SELECT set_config('app.tenant_token', %s, true)", [value])
        yield
