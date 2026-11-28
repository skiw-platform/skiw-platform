"""`scope_probe` (slice spec §4; plan M4r-4 §2 option A): a test-only tenant table built by
skiw_migrator with tenant_table() SQL for one test module and dropped after it, so the TEN-08
coverage test never sees it; no migration, so its model is unmanaged. No line column: lines are
per record type (owner, 2026-11-27), so `scope_probe_insurance` and `scope_probe_investment` are
the same table for the two lines (M4r-4c). A NULL owner is allowed, so rows without one are
tested."""

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar, Literal

import psycopg
from django.db import models

from accounts.access.scope import ScopedModel
from tenancy.models import TenantModel
from tenancy.template import tenant_table_sql
from tenancy.tests.isolation import Executes

TABLES = ("scope_probe", "scope_probe_insurance", "scope_probe_investment")
CREATE = (
    "CREATE TABLE public.{} (id uuid PRIMARY KEY, agency_id uuid NOT NULL,"
    " owner_user_id uuid, UNIQUE (agency_id, id))"
)
FKS = [("owner_user_id", "app_user")]


class Probe(ScopedModel):
    id = models.UUIDField(primary_key=True)
    owner_user_id = models.UUIDField(null=True)
    SCOPE_OWNER = "owner_user_id"
    SCOPE_LINE: ClassVar[Literal["insurance", "investment"] | None] = None

    class Meta(TenantModel.Meta):
        abstract = True
        app_label = "accounts"
        managed = False


class ScopeProbe(Probe):
    class Meta(Probe.Meta):
        db_table = "scope_probe"


class ScopeProbeInsurance(Probe):
    SCOPE_LINE = "insurance"

    class Meta(Probe.Meta):
        db_table = "scope_probe_insurance"


class ScopeProbeInvestment(Probe):
    SCOPE_LINE = "investment"

    class Meta(Probe.Meta):
        db_table = "scope_probe_investment"


PROBES = (ScopeProbe, ScopeProbeInsurance, ScopeProbeInvestment)


def insert(
    cursor: Executes, agency: uuid.UUID, owner: uuid.UUID | None, table: str = "scope_probe"
) -> uuid.UUID:
    if table not in TABLES:
        raise ValueError(table)
    row = uuid.uuid4()
    statement = f"INSERT INTO {table} VALUES (%s, %s, %s)"  # noqa: S608 - one of TABLES
    cursor.execute(statement, [row, agency, owner])
    return row


def drop() -> None:
    """Also the leftover of an interrupted run (app/conftest.py)."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {', '.join(f'public.{t}' for t in TABLES)}")


@contextmanager
def table() -> Iterator[None]:
    """The three tables."""
    drop()
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        for name in TABLES:
            conn.execute(CREATE.format(name))
            steps = tenant_table_sql(name, commands={"SELECT", "INSERT"}, composite_fks=FKS)
            for statement in (s for forward, _ in steps for s in forward):
                conn.execute(statement)
    try:
        yield
    finally:
        drop()
