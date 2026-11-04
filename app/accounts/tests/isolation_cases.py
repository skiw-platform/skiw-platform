"""TEN-08 isolation cases for the accounts tenant tables (plan M3 §3 M3d; the harness is
tenancy/tests/isolation.py, M4c-7a). `commands` repeat the RLS migrations' grants; each insert
names only the columns the row needs."""

import uuid
from collections.abc import Mapping

from django.db.backends.utils import CursorWrapper

from tenancy.tests.isolation import IsolationCase


def _app_user(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, %s)",
        [row, agency, f"{row}@isolation.test", "Isolation user"],
    )
    return row


CASES = [
    IsolationCase("public.app_user", _app_user, frozenset({"SELECT", "INSERT", "UPDATE"})),
]
