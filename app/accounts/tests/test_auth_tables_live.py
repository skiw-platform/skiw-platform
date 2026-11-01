"""The global auth tables take only 32-byte HMACs and keep security_event append-only, as
skiw_app (spec §4.1, TEN-03; plan M3c). Each statement runs on its own connection and fails, so
no row is left behind."""

import os
import secrets
import uuid

import psycopg
import pytest
from psycopg import sql

pytestmark = pytest.mark.live
HMAC = secrets.token_bytes(32)
EMAIL = b"adviser@example.test"  # 20 bytes: a raw value, not an HMAC


def run(statement: str, *params: object) -> None:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        conn.execute(sql.SQL(statement), params)


INSERT_THROTTLE = "INSERT INTO auth_throttle (key_hmac, window_start, count) VALUES (%s, now(), 1)"
INSERT_EVENT = (
    "INSERT INTO security_event (id, at, kind, email_hmac, ip_hmac, details_json)"
    " VALUES (%s, now(), 'probe', %s, %s, '{}')"
)


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        (INSERT_THROTTLE, (EMAIL,)),
        (INSERT_THROTTLE, (HMAC + b"\0",)),
        (INSERT_EVENT, (uuid.uuid4(), EMAIL, HMAC)),
        (INSERT_EVENT, (uuid.uuid4(), HMAC, b"192.0.2.7")),
    ],
)
def test_only_32_byte_hmacs_fit_the_key_columns(statement: str, params: tuple[object]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        run(statement, *params)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE security_event SET kind = 'x'",
        "DELETE FROM security_event",
        "TRUNCATE security_event",
        "DELETE FROM auth_throttle",
        "TRUNCATE auth_throttle",
    ],
)
def test_the_app_role_cannot_rewrite_events_or_remove_counters(statement: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        run(statement)
