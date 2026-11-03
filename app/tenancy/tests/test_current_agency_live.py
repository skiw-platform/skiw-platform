"""`guard.current_agency()` after `make migrate` (spec §4.2 "Tenant binding" items 2 and 3, v1.21;
TEN-06, TEN-09, TEN-12; plan M4c-4a). Tokens are minted by hand with `tenancy.token` and set as
skiw_app on a plain psycopg connection; `with_agency()` is tested in test_binding_live.py.
The vector key goes in under two high test versions (the `vector_keys` fixture, conftest.py)."""

import base64
import importlib
import os
import uuid
from typing import Any, LiteralString

import psycopg
import pytest
from django.conf import settings

from tenancy import token
from tenancy.tests.conftest import ABSENT, ACTIVE, RETIRED
from tenancy.tests.test_token import (
    VECTOR,
    VECTOR_AGENCY,
    VECTOR_DATABASE,
    VECTOR_INPUT,
    VECTOR_KEY,
    VECTOR_XID,
)

pytestmark = pytest.mark.live

OTHER = uuid.UUID("11111111-2222-4333-8444-555555555555")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"  # base64url order
# Hand-made and forged tokens, set on purpose: Semgrep `tenancy-token-setting` allows
# tenancy/tests (docs/DECISIONS.md "M4c-4b-1", PR 91 review R1 P3).
SET_TOKEN: LiteralString = "SELECT set_config('app.tenant_token', %s, true)"


def migrator(query: LiteralString, *params: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall() if cursor.description else []


def verify(make: Any, *, assign: bool = True) -> uuid.UUID | None:
    """One skiw_app transaction: assign its xid (unless told not to), set `make(xid, database)`
    as the token, and return what the verifier says."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        query: LiteralString = "SELECT pg_current_xact_id()::text" if assign else "SELECT '1'"
        row = conn.execute(f"{query}, current_database()").fetchone()
        assert row is not None
        value = make(int(row[0]), row[1])
        if value is not None:
            conn.execute(SET_TOKEN, (value,))
        result = conn.execute("SELECT guard.current_agency()").fetchone()
        assert result is not None
        agency: uuid.UUID | None = result[0]
        return agency


def live(xid: int, database: str, agency: uuid.UUID = VECTOR_AGENCY) -> str:
    version, key = settings.SKIW_TENANT_TOKEN_KEYS()[0]
    return token.mint(version, key, database, agency, xid)


def vector(version: int) -> Any:
    return lambda xid, database: token.mint(version, VECTOR_KEY, database, VECTOR_AGENCY, xid)


def test_a_token_under_the_migrate_written_key_gives_its_agency() -> None:
    assert verify(live) == VECTOR_AGENCY
    assert verify(lambda xid, db: live(xid, db, OTHER)) == OTHER


@pytest.mark.usefixtures("vector_keys")
def test_the_verifier_accepts_the_vector_key_and_refuses_retired_and_absent_versions() -> None:
    assert verify(vector(ACTIVE)) == VECTOR_AGENCY
    assert verify(vector(RETIRED)) is None
    assert verify(vector(ABSENT)) is None


MIGRATION = importlib.import_module("tenancy.migrations.0003_current_agency")
DATABASE = "pg_catalog.current_database()::text"


def sql_mac_input(database: str, agency: uuid.UUID, xid: int) -> tuple[bytes, bytes]:
    """The migration's own MAC-input expression, evaluated by PostgreSQL with literal inputs (the
    database name swapped for a parameter), and `guard.hmac` over it under the vector key."""
    assert MIGRATION.MAC_INPUT.count(DATABASE) == 2  # the length prefix and the value
    expression = MIGRATION.MAC_INPUT.replace(DATABASE, "v.database")
    query: LiteralString = (
        f"SELECT m, guard.hmac(m, %s, 'sha256') FROM (SELECT {expression} AS m FROM (SELECT"  # noqa: S608 - the migration's constant
        " %s::text AS database, %s::uuid AS agency, %s::pg_catalog.xid8 AS xact) v) w"
    )
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(query, (VECTOR_KEY, database, str(agency), str(xid))).fetchone()
    assert row is not None
    return bytes(row[0]), bytes(row[1])


def test_the_sql_encoding_reproduces_the_committed_vector() -> None:
    """Spec v1.21 §4.2 item 2: both implementations reproduce the committed bytes."""
    data, mac = sql_mac_input(VECTOR_DATABASE, VECTOR_AGENCY, VECTOR_XID)
    assert data.hex() == VECTOR_INPUT
    assert mac == base64.urlsafe_b64decode(VECTOR.rsplit(".", 1)[1] + "=")


def test_the_sql_encoding_matches_the_minter_on_a_multibyte_name_and_the_largest_xid() -> None:
    data, mac = sql_mac_input("é-skiw", OTHER, 2**64 - 1)
    assert data == token.mac_input("é-skiw", OTHER, 2**64 - 1)
    assert token.mint(1, VECTOR_KEY, "é-skiw", OTHER, 2**64 - 1).endswith(
        "." + base64.urlsafe_b64encode(mac).rstrip(b"=").decode()
    )


def swap_mac(text: str, mac: str) -> str:
    return text.rsplit(".", 1)[0] + "." + mac


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda xid, db: None, id="no-token"),
        pytest.param(lambda xid, db: "not a token", id="random"),
        pytest.param(lambda xid, db: live(xid, db)[:-1], id="truncated"),
        pytest.param(lambda xid, db: live(xid, db) + ".x", id="extra-field"),
        pytest.param(lambda xid, db: swap_mac(live(xid, db), "A" * 43), id="bad-mac"),
        pytest.param(
            lambda xid, db: live(xid, db).replace(str(VECTOR_AGENCY), str(OTHER)), id="other-agency"
        ),
        pytest.param(lambda xid, db: live(xid + 1, db), id="other-xid"),
        pytest.param(lambda xid, db: live(xid, db + "x"), id="other-database"),
        pytest.param(lambda xid, db: live(xid, db).upper(), id="upper-case"),
        pytest.param(lambda xid, db: live(xid, db) + "=", id="padded-mac"),
        pytest.param(lambda xid, db: live(xid, db).replace("v", "v0", 1), id="leading-zero"),
        pytest.param(
            lambda xid, db: live(xid, db).replace(f".{xid}.", f".{xid + 2**64}.", 1),
            id="xid-out-of-range",
        ),
    ],
)
def test_anything_but_a_genuine_token_gives_null(make: Any) -> None:
    assert verify(make) is None


def test_a_non_canonical_last_mac_character_gives_null() -> None:
    def make(xid: int, db: str) -> str:
        text = live(xid, db)
        return text[:-1] + ALPHABET[ALPHABET.index(text[-1]) ^ 1]

    assert verify(make) is None


def test_a_transaction_without_an_xid_gives_null() -> None:
    assert verify(lambda xid, db: live(1, db), assign=False) is None


def test_a_token_replayed_from_another_transaction_gives_null() -> None:
    captured: list[str] = []

    def capture(xid: int, db: str) -> str:
        captured.append(live(xid, db))
        return captured[0]

    assert verify(capture) == VECTOR_AGENCY
    assert verify(lambda xid, db: captured[0]) is None


def test_a_plain_agency_id_setting_is_not_trusted() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("SELECT pg_current_xact_id()")
        conn.execute("SELECT set_config('app.agency_id', %s, true)", (str(VECTOR_AGENCY),))
        assert conn.execute("SELECT guard.current_agency()").fetchall() == [(None,)]


def test_the_function_matches_the_ten_12_row() -> None:
    assert migrator(
        "SELECT p.proowner::regrole::text, p.proacl::text, p.prosecdef, p.proconfig,"
        " p.provolatile, l.lanname, p.prorettype::regtype::text, p.prosrc ~* 'execute|raise'"
        " FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang"
        " WHERE p.oid = to_regprocedure('guard.current_agency()')"
    ) == [
        (
            "skiw_tenant_guard",
            "{skiw_tenant_guard=X/skiw_tenant_guard,skiw_app=X/skiw_tenant_guard}",
            True,
            ["search_path=pg_catalog, pg_temp"],
            "s",
            "plpgsql",
            "uuid",
            False,
        )
    ]


@pytest.mark.parametrize("role", ["skiw_readonly", "skiw_migrator", "skiw_backup"])
def test_no_other_role_may_call_it(role: str) -> None:
    assert migrator(
        "SELECT has_function_privilege(%s, 'guard.current_agency()', 'EXECUTE')", role
    ) == [(False,)]
