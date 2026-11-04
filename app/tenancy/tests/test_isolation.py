"""`refused()` and `IsolationCase` from the TEN-08 harness (plan M4c-7a), without a database."""

import uuid

import psycopg
import pytest
from django.db import DatabaseError

from tenancy.tests.isolation import IsolationCase, refused


def _raise(sqlstate: str) -> None:
    error = psycopg.errors.lookup(sqlstate)("refused")
    raise DatabaseError("wrapped") from error


def test_refused_accepts_only_the_expected_sqlstate() -> None:
    with refused("42501", "t"):
        _raise("42501")
    with pytest.raises(AssertionError, match="got 23503"), refused("42501", "t"):
        _raise("23503")
    with pytest.raises(AssertionError, match="42501, but it succeeded"), refused("42501", "t"):
        pass


@pytest.mark.parametrize(
    ("table", "commands"),
    [("client", {"SELECT", "INSERT"}), ("public.client", {"SELECT"}), ("public.c", {"TRUNCATE"})],
)
def test_a_case_needs_a_qualified_name_and_select_and_insert(
    table: str, commands: set[str]
) -> None:
    with pytest.raises(ValueError, match="isolation case"):
        IsolationCase(table, lambda cursor, agency, parents: uuid.uuid4(), frozenset(commands))
