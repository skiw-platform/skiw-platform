"""`scope_probe` (slice spec §4; plan M4r-4 §2 option A): a test-only tenant table built by
skiw_migrator with tenant_table() SQL for one test module and dropped after it, so the TEN-08
coverage test never sees it; no migration, so its model is unmanaged. No line column: lines are
per record type (owner, 2026-11-27). A NULL owner is allowed, so rows without one are tested."""

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from django.db import models

from accounts.access.scope import ScopedModel
from tenancy.models import TenantModel
from tenancy.template import tenant_table_sql
from tenancy.tests.isolation import Executes

CREATE = (
    "CREATE TABLE public.scope_probe (id uuid PRIMARY KEY, agency_id uuid NOT NULL,"
    " owner_user_id uuid, UNIQUE (agency_id, id))"
)
FKS = [("owner_user_id", "app_user")]


class ScopeProbe(ScopedModel):
    id = models.UUIDField(primary_key=True)
    owner_user_id = models.UUIDField(null=True)
    SCOPE_OWNER = "owner_user_id"
    SCOPE_LINE = None

    class Meta(TenantModel.Meta):
        app_label = "accounts"
        db_table = "scope_probe"
        managed = False


def insert(cursor: Executes, agency: uuid.UUID, owner: uuid.UUID | None) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute("INSERT INTO scope_probe VALUES (%s, %s, %s)", [row, agency, owner])
    return row


def drop() -> None:
    """Also the leftover of an interrupted run (app/conftest.py)."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        conn.execute("DROP TABLE IF EXISTS public.scope_probe")


@contextmanager
def table() -> Iterator[None]:
    drop()
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        conn.execute(CREATE)
        steps = tenant_table_sql("scope_probe", commands={"SELECT", "INSERT"}, composite_fks=FKS)
        for statement in (s for forward, _ in steps for s in forward):
            conn.execute(statement)
    try:
        yield
    finally:
        drop()
