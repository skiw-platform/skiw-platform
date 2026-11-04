"""Isolation cases for the tenancy app (plan M4c-7a): only the fixture pair, which
`test_isolation_live.py` builds from `tenant_table()` SQL for its module and drops again. `parent`
grants all four commands; `child` is append-only and has a composite FK to `parent`."""

import uuid
from collections.abc import Mapping

from django.db.backends.utils import CursorWrapper

from tenancy.tests.isolation import IsolationCase

SCHEMA = "tenancy_fixture"


def _parent(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO tenancy_fixture.parent (id, agency_id) VALUES (%s, %s)", [row, agency]
    )
    return row


def _child(cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO tenancy_fixture.child (id, agency_id, parent_id) VALUES (%s, %s, %s)",
        [row, agency, parents["parent_id"]],
    )
    return row


CASES = [
    IsolationCase(f"{SCHEMA}.parent", _parent, frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})),
    IsolationCase(
        f"{SCHEMA}.child",
        _child,
        frozenset({"SELECT", "INSERT"}),
        {"parent_id": f"{SCHEMA}.parent"},
    ),
]
