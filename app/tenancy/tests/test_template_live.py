"""`tenant_table()` applied to scratch tables as the migrator (plan M4c-6a), in one transaction that
rolls back: the catalog holds the §4.2 shape, a composite FK refuses a cross-agency parent, and the
reverses put the catalog back exactly. ACLs are compared as effective privileges: the first GRANT
turns a NULL (default) ACL into an explicit owner entry, which REVOKE leaves behind."""

import os
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
import pytest

from tenancy import seed
from tenancy.template import tenant_table_sql

pytestmark = pytest.mark.live

DEPARSED = "(agency_id = ( SELECT guard.current_agency() AS current_agency))"
TABLES = ("tmpl_parent", "tmpl_child")
CATALOG = """
    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
      coalesce(c.relacl, acldefault('r', c.relowner))::text,
      ARRAY(SELECT conname || ':' || pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = c.oid ORDER BY conname),
      ARRAY(SELECT policyname || ':' || permissive || ':' || cmd || ':' || roles::text || ':'
                   || coalesce(qual, '-') || ':' || coalesce(with_check, '-')
            FROM pg_policies WHERE tablename = c.relname ORDER BY policyname)
    FROM pg_class c WHERE c.relname = ANY(%s) ORDER BY c.relname
"""


def catalog(cursor: "psycopg.Cursor[Any]") -> list[tuple[Any, ...]]:
    return cursor.execute(CATALOG, [list(TABLES)]).fetchall()


def run(cursor: "psycopg.Cursor[Any]", statements: Sequence[str]) -> None:
    for statement in statements:
        cursor.execute(statement)


@pytest.fixture
def cursor() -> Iterator["psycopg.Cursor[Any]"]:
    with (
        psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
        conn.cursor() as cursor,
    ):
        for table in TABLES:
            column = ", parent_id uuid" if table == "tmpl_child" else ""
            cursor.execute(
                f"CREATE TABLE {table} (id uuid PRIMARY KEY, agency_id uuid NOT NULL{column},"
                " UNIQUE (agency_id, id))"
            )
        yield cursor


PARENT = tenant_table_sql("tmpl_parent", commands={"SELECT", "INSERT", "UPDATE", "DELETE"})
CHILD = tenant_table_sql(
    "tmpl_child", commands={"INSERT", "SELECT"}, composite_fks=[("parent_id", "tmpl_parent")]
)


def test_the_template_shape_and_its_exact_reverse(cursor: "psycopg.Cursor[Any]") -> None:
    before = catalog(cursor)
    for forward, _ in [*PARENT, *CHILD]:
        run(cursor, forward)
    child = catalog(cursor)[0]
    assert child[:4] == (
        "tmpl_child",
        True,
        True,
        "{skiw_migrator=arwdDxtm/skiw_migrator,skiw_app=ar/skiw_migrator}",
    )
    assert child[4] == [
        "tmpl_child_agency_fk:FOREIGN KEY (agency_id) REFERENCES agency(id)",
        "tmpl_child_agency_id_id_key:UNIQUE (agency_id, id)",
        "tmpl_child_parent_id_fk:FOREIGN KEY (agency_id, parent_id)"
        " REFERENCES tmpl_parent(agency_id, id)",
        "tmpl_child_pkey:PRIMARY KEY (id)",
    ]
    assert child[5] == [
        f"tmpl_child_ins:PERMISSIVE:INSERT:{{skiw_app}}:-:{DEPARSED}",
        f"tmpl_child_sel:PERMISSIVE:SELECT:{{skiw_app}}:{DEPARSED}:-",
        f"tmpl_child_tenant:RESTRICTIVE:ALL:{{skiw_app}}:{DEPARSED}:{DEPARSED}",
    ]
    parent = catalog(cursor)[1]
    assert parent[3].endswith(",skiw_app=arwd/skiw_migrator}")
    assert [p.split(":")[2] for p in parent[5]] == ["DELETE", "INSERT", "SELECT", "ALL", "UPDATE"]
    for _, reverse in reversed([*PARENT, *CHILD]):
        run(cursor, reverse)
    assert catalog(cursor) == before


def test_a_composite_fk_refuses_another_agencys_parent(cursor: "psycopg.Cursor[Any]") -> None:
    a, b, parent = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    seed.insert_agency(cursor, a, "Template A")
    seed.insert_agency(cursor, b, "Template B")
    for forward, _ in [*PARENT, *CHILD]:
        run(cursor, forward)
    for table in TABLES:  # the owner writes under NO FORCE, as the seed does
        cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    cursor.execute("INSERT INTO tmpl_parent (id, agency_id) VALUES (%s, %s)", [parent, a])
    cursor.execute(
        "INSERT INTO tmpl_child (id, agency_id, parent_id) VALUES (%s, %s, %s)",
        [uuid.uuid4(), a, parent],
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation), cursor.connection.transaction():
        cursor.execute(
            "INSERT INTO tmpl_child (id, agency_id, parent_id) VALUES (%s, %s, %s)",
            [uuid.uuid4(), b, parent],
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation), cursor.connection.transaction():
        cursor.execute(
            "INSERT INTO tmpl_parent (id, agency_id) VALUES (%s, %s)", [uuid.uuid4(), uuid.uuid4()]
        )
