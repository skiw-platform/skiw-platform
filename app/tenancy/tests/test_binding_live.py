"""`with_agency()` on the real Django connection as skiw_app, after `make migrate` (spec §4.2
"Tenant binding" items 2 and 4, TEN-09 function-level forged-tenant tests; plan M4c-4b). There is
no tenant table yet, so "denied" means `guard.current_agency()` gives NULL, which every policy
will compare against (M4c-6a); the row-level set is M4c-7b."""

import logging
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from tenancy import binding, token
from tenancy.binding import with_agency
from tenancy.tests.conftest import ABSENT, ACTIVE, RETIRED
from tenancy.tests.test_token import VECTOR_KEY

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

A = uuid.UUID("aaaaaaaa-0000-4000-8000-00000000000a")
B = uuid.UUID("bbbbbbbb-0000-4000-8000-00000000000b")


def one(query: str, params: list[Any] | None = None) -> Any:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    assert row is not None
    return row[0]


def current() -> uuid.UUID | None:
    agency: uuid.UUID | None = one("SELECT guard.current_agency()")
    return agency


def setting() -> str:
    """The token setting; '' (or NULL) once its transaction has ended."""
    value: str = one("SELECT coalesce(current_setting('app.tenant_token', true), '')")
    return value


def set_token(value: str) -> None:
    one("SELECT set_config('app.tenant_token', %s, true)", [value])


def mint(version: int, key: bytes, agency: uuid.UUID) -> str:
    """A token for this transaction's own xid and database, as an attacker with `key` would."""
    xid = int(one("SELECT pg_current_xact_id()::text"))
    return token.mint(version, key, one("SELECT current_database()"), agency, xid)


def swap_mac(text: str, mac: str) -> str:
    return text.rsplit(".", 1)[0] + "." + mac


def test_inside_with_agency_the_verifier_gives_that_agency() -> None:
    with with_agency(A):
        assert current() == A
    with with_agency(B):  # the next transaction on the same connection sees only its own
        assert current() == B


def test_no_token_survives_the_block() -> None:
    with with_agency(A):
        assert setting().startswith("v")
    with transaction.atomic():
        one("SELECT pg_current_xact_id()")
        assert setting() == ""
        assert current() is None


def test_an_error_inside_rolls_back_and_leaves_no_token() -> None:
    with pytest.raises(ValueError, match="boom"), with_agency(A):
        raise ValueError("boom")
    with transaction.atomic():
        one("SELECT pg_current_xact_id()")
        assert setting() == "" and current() is None


def test_it_mints_under_the_newest_key(vector_keys: None, monkeypatch: pytest.MonkeyPatch) -> None:
    keys = binding.token_keys()
    monkeypatch.setattr(binding, "token_keys", lambda: ((ACTIVE, VECTOR_KEY), *keys))
    with with_agency(A):
        assert setting().startswith(f"v{ACTIVE}.{A}.")
        assert current() == A


@pytest.mark.usefixtures("vector_keys")
def test_the_control_a_token_under_an_active_key_does_switch() -> None:
    """The forged cases below differ from this one only in what they get wrong, so each NULL is
    caused by that, not by a wrong xid or database in the test."""
    with with_agency(A):
        set_token(mint(ACTIVE, VECTOR_KEY, B))
        assert current() == B


FORGED: dict[str, Callable[[str], str]] = {
    "random": lambda own: "not a token",
    "b-shaped-bad-mac": lambda own: own.replace(str(A), str(B)),
    "truncated": lambda own: own[:-1],
    "extra-field": lambda own: own + ".x",
    "zero-mac": lambda own: swap_mac(own, "A" * 43),
    "unknown-version": lambda own: mint(ABSENT, VECTOR_KEY, B),
    "retired-version": lambda own: mint(RETIRED, VECTOR_KEY, B),
}


@pytest.mark.usefixtures("vector_keys")
@pytest.mark.parametrize("make", FORGED.values(), ids=FORGED.keys())
def test_a_forged_token_inside_with_agency_gives_null(make: Callable[[str], str]) -> None:
    with with_agency(A):
        set_token(make(setting()))
        assert current() is None


def test_a_genuine_token_replayed_from_another_transaction_gives_null() -> None:
    with with_agency(B):
        captured = setting()
        assert current() == B
    with with_agency(A):
        set_token(captured)
        assert current() is None


def test_a_plain_agency_id_setting_does_not_switch() -> None:
    with with_agency(A):
        one("SELECT set_config('app.agency_id', %s, true)", [str(B)])
        assert current() == A


def test_commit_begin_without_the_helper_gives_null() -> None:
    with with_agency(A), connection.cursor() as cursor:
        cursor.execute("COMMIT")
        cursor.execute("BEGIN")
        cursor.execute("SELECT pg_current_xact_id()")
        assert setting() == ""
        assert current() is None


def test_a_nested_atomic_keeps_the_binding() -> None:
    with with_agency(A):
        with transaction.atomic():
            assert current() == A
        with pytest.raises(ValueError, match="inner"), transaction.atomic():
            raise ValueError("inner")
        assert current() == A


def test_nesting_and_an_open_atomic_block_are_refused() -> None:
    with with_agency(A):
        with pytest.raises(TransactionManagementError), with_agency(B):
            pass
        assert current() == A
    with transaction.atomic(), pytest.raises(TransactionManagementError), with_agency(A):
        pass


@pytest.mark.parametrize(
    "value", [str(A), A.bytes, A.int, None], ids=["str", "bytes", "int", "none"]
)
def test_only_a_uuid_is_taken(value: Any) -> None:
    with pytest.raises(TypeError, match=r"uuid\.UUID"), with_agency(value):
        pass


def test_the_token_is_not_logged_by_the_debug_cursor(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(connection, "force_debug_cursor", True)
    connection.queries_log.clear()
    with caplog.at_level(logging.DEBUG, logger="django.db.backends"), with_agency(A):
        value = setting()
    assert value.startswith("v")
    logged = " ".join(q["sql"] for q in connection.queries) + caplog.text
    assert "pg_current_xact_id" in logged  # the wrapper did log the other statements
    assert value not in logged and value.rsplit(".", 1)[1] not in logged
