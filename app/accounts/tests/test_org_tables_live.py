"""`org_unit` and `user_role` on the live schema (plan row M4r-1b; slice spec §4, Decisions 2, 3).
skiw_app may only SELECT them until M4r-1g, so rows are written by the owner, skiw_migrator, in one
transaction under transaction-local NO FORCE that is rolled back, with two agencies of its own.
TEN-08 read isolation and the cross-agency composite FKs also run through the harness
(accounts/tests/isolation_cases.py); the grant audit is in test_access_tables_live.py."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from accounts.tests.test_access_tables_live import add_role, refused_by
from tenancy import seed

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

X, Y = uuid.uuid4(), uuid.uuid4()  # this module's agencies, gone with the rollback
UNIT = "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) VALUES (%s, %s, %s, %s, %s)"
ASSIGN = (
    "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)"
)
type Cursor = psycopg.Cursor[Any]


@pytest.fixture
def owner() -> Iterator[Cursor]:
    """The migrator fixture: FORCE lifted on the tables these tests write, agencies X and Y added,
    all rolled back at the end (DDL is transactional, so FORCE is back too)."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn, conn.cursor() as cursor:
        for table in ("app_user", "role", "org_unit", "user_role"):
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        seed.insert_agency(cursor, X, "Org test X")
        seed.insert_agency(cursor, Y, "Org test Y")
        yield cursor
        conn.rollback()


def add_unit(
    cursor: Cursor, agency: uuid.UUID, parent: uuid.UUID | None, kind: str = "unit", name: str = "U"
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(UNIT, [row, agency, parent, kind, name])
    return row


def add_root(cursor: Cursor, agency: uuid.UUID) -> uuid.UUID:
    return add_unit(cursor, agency, None, kind="agency", name="Agency")


def add_user(cursor: Cursor, agency: uuid.UUID) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, 'U')",
        [row, agency, f"{row}@org.test"],
    )
    return row


def assignment(cursor: Cursor, agency: uuid.UUID) -> dict[str, uuid.UUID]:
    """A user, a role and a unit of `agency`, ready to be assigned."""
    unit = add_unit(cursor, agency, add_root(cursor, agency))
    role = add_role(cursor, f"Role {uuid.uuid4()}", agency=agency)
    return {"user_id": add_user(cursor, agency), "role_id": role, "org_unit_id": unit}


def assign(cursor: Cursor, agency: uuid.UUID, ids: dict[str, uuid.UUID], line: object) -> None:
    cursor.execute(ASSIGN, [agency, ids["user_id"], ids["role_id"], ids["org_unit_id"], line])


def test_one_root_per_agency(owner: Cursor) -> None:
    add_root(owner, X)
    params: list[object] = [uuid.uuid4(), X, None, "agency", "Second root"]
    assert refused_by(owner, UNIT, params) == "org_unit_one_root_per_agency"
    add_root(owner, Y)  # another agency has its own root


@pytest.mark.parametrize(
    ("kind", "rooted"),
    [("unit", False), ("team", False), ("agency", True)],
    ids=["unit-without-parent", "team-without-parent", "agency-with-parent"],
)
def test_the_root_is_exactly_the_agency_kind(owner: Cursor, kind: str, rooted: bool) -> None:
    parent = add_root(owner, X) if rooted else None
    params: list[object] = [uuid.uuid4(), X, parent, kind, "Mismatch"]
    assert refused_by(owner, UNIT, params) == "org_unit_root_is_agency"


def test_a_unit_cannot_be_its_own_parent(owner: Cursor) -> None:
    add_root(owner, X)
    row = uuid.uuid4()
    assert refused_by(owner, UNIT, [row, X, row, "team", "Self"]) == "org_unit_not_own_parent"


def test_unit_kinds_are_closed(owner: Cursor) -> None:
    root = add_root(owner, X)
    assert refused_by(owner, UNIT, [uuid.uuid4(), X, root, "region", "R"]) == (
        "org_unit_kind_known"
    )
    add_unit(owner, X, add_unit(owner, X, root, kind="unit"), kind="team")  # the closed set


@pytest.mark.parametrize(
    "name",
    ["", "x" * 65, "a\tb", "a\nb", "a\x7fb", "a\x85b"],
    ids=["empty", "65-chars", "tab", "newline", "del", "c1-nel"],
)
def test_unit_names_are_1_to_64_characters_without_control_characters(
    owner: Cursor, name: str
) -> None:
    root = add_root(owner, X)
    params = [uuid.uuid4(), X, root, "team", name]
    assert refused_by(owner, UNIT, params).startswith("org_unit_name_")
    add_unit(owner, X, root, name="Ünit " + "é" * 59)  # 64 characters, more bytes: accepted


@pytest.mark.parametrize("line", ["Insurance", "any", ""])
def test_the_line_is_one_of_three(owner: Cursor, line: str) -> None:
    ids = assignment(owner, X)
    params = [X, ids["user_id"], ids["role_id"], ids["org_unit_id"], line]
    assert refused_by(owner, ASSIGN, params) == "user_role_line_known"
    for accepted in ("insurance", "investment", "both"):
        ids["role_id"] = add_role(owner, f"Role {accepted}", agency=X)
        assign(owner, X, ids, accepted)


NO_LINE = {
    "null": "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (gen_random_uuid(), %s, %s, %s, %s, NULL)",
    "omitted": "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id)"
    " VALUES (gen_random_uuid(), %s, %s, %s, %s)",
}


@pytest.mark.parametrize("sql", NO_LINE.values(), ids=NO_LINE.keys())
def test_the_line_is_required_with_no_default(owner: Cursor, sql: str) -> None:
    ids = assignment(owner, X)
    with pytest.raises(psycopg.errors.NotNullViolation) as caught, owner.connection.transaction():
        owner.execute(sql, [X, ids["user_id"], ids["role_id"], ids["org_unit_id"]])
    assert caught.value.diag.column_name == "line"


def test_an_assignment_is_unique_per_user_role_and_unit(owner: Cursor) -> None:
    ids = assignment(owner, X)
    assign(owner, X, ids, "insurance")
    params = [X, ids["user_id"], ids["role_id"], ids["org_unit_id"], "investment"]
    assert refused_by(owner, ASSIGN, params) == "user_role_assignment_uq"  # line is not in the key
    other_unit = add_unit(owner, X, ids["org_unit_id"], kind="team")
    assign(owner, X, {**ids, "org_unit_id": other_unit}, "investment")  # Decision 8: several
    assign(owner, X, {**ids, "role_id": add_role(owner, "Second role", agency=X)}, "both")


@pytest.mark.parametrize("column", ["user_id", "role_id", "org_unit_id"])
def test_an_assignment_cannot_name_another_agencys_row(owner: Cursor, column: str) -> None:
    ids = assignment(owner, X)
    ids[column] = assignment(owner, Y)[column]
    params = [X, ids["user_id"], ids["role_id"], ids["org_unit_id"], "both"]
    assert refused_by(owner, ASSIGN, params) == f"user_role_{column}_fk"


def test_a_unit_cannot_sit_under_another_agencys_unit(owner: Cursor) -> None:
    add_root(owner, X)
    foreign = add_root(owner, Y)
    params = [uuid.uuid4(), X, foreign, "unit", "Cross"]
    assert refused_by(owner, UNIT, params) == "org_unit_parent_id_fk"


@pytest.mark.parametrize(
    ("sql", "column"),
    [
        ("DELETE FROM app_user WHERE id = %s", "user_id"),
        ("DELETE FROM role WHERE id = %s", "role_id"),
        ("DELETE FROM org_unit WHERE id = %s", "org_unit_id"),
    ],
    ids=["user", "role", "unit"],
)
def test_an_assigned_row_cannot_be_deleted(owner: Cursor, sql: str, column: str) -> None:
    ids = assignment(owner, X)
    assign(owner, X, ids, "both")
    assert refused_by(owner, sql, [ids[column]]) == f"user_role_{column}_fk"


def test_a_unit_with_a_child_cannot_be_deleted(owner: Cursor) -> None:
    root = add_root(owner, X)
    add_unit(owner, X, root)
    assert refused_by(owner, "DELETE FROM org_unit WHERE id = %s", [root]) == (
        "org_unit_parent_id_fk"
    )


def test_every_new_foreign_key_is_on_delete_restrict(owner: Cursor) -> None:
    rows = owner.execute(
        "SELECT conname::text, confdeltype::text FROM pg_constraint"
        " WHERE contype = 'f' AND conrelid IN ('org_unit'::regclass, 'user_role'::regclass)"
        " AND conname NOT LIKE '%%agency_fk'"
    ).fetchall()
    assert sorted(rows) == [
        ("org_unit_parent_id_fk", "r"),
        ("user_role_org_unit_id_fk", "r"),
        ("user_role_role_id_fk", "r"),
        ("user_role_user_id_fk", "r"),
    ]
