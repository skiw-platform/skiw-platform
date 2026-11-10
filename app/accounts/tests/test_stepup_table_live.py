"""`auth_stepup` (spec §4.1; plan M3 §3 M3h, design M3h-1): the column rules, the append-only
grant and the factor foreign key (NO ACTION: a factor a step-up names is never deleted), as
skiw_app bound to the configured agency. Cross-agency parents and the grants are also covered by
the TEN-08 harness (accounts.tests.isolation_cases) and the TEN-03 audit
(jobs.tests.test_queue_grants). Every test runs in one with_agency() transaction that is rolled
back: skiw_app may not delete rows here."""

import hashlib
import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import IntegrityError, ProgrammingError, connection, transaction
from django.db.backends.utils import CursorWrapper
from django.db.models import ProtectedError

from accounts.factor_model import UserFactor
from accounts.stepup_model import EVIDENCE_LENGTH
from accounts.tests.test_user_tables_live import add_factor, add_user, refused_by
from tenancy.binding import with_agency

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

# A stored_key()-shaped value, derived so no high-entropy literal sits in the source.
KEY_HASH = hashlib.sha256(b"auth-stepup-test").hexdigest()


@pytest.fixture
def cursor() -> Iterator[CursorWrapper]:
    agency = uuid.UUID(os.environ["SKIW_DEPLOYMENT_AGENCY_ID"])
    with with_agency(agency), connection.cursor() as bound:
        yield bound
        transaction.set_rollback(True)


def add_totp(cursor: CursorWrapper, user: uuid.UUID) -> uuid.UUID:
    factor = uuid.uuid4()
    add_factor(cursor, user, id=factor, kind="totp", secret_ct=b"\0" * 48)
    return factor


def add_stepup(cursor: CursorWrapper, user: uuid.UUID, **columns: Any) -> uuid.UUID:
    row = uuid.uuid4()
    factor = columns.pop("factor_id") if "factor_id" in columns else add_totp(cursor, user)
    values: dict[str, Any] = {
        "id": row,
        "user_id": user,
        "factor_id": factor,
        "purpose": "factor.change",
        "session_key_hash": KEY_HASH,
        "evidence_mac": b"\0" * EVIDENCE_LENGTH,
        **columns,
    }
    cursor.execute(
        f"INSERT INTO auth_stepup (agency_id, verified_at, {', '.join(values)})"  # noqa: S608
        f" VALUES (guard.current_agency(), now(), {', '.join(['%s'] * len(values))})",
        list(values.values()),
    )
    return row


@pytest.mark.parametrize(
    "purpose",
    ["factor.change", "outbox.approve", "drive.write", "export", "role_change", "budget_change.x"],
)
def test_a_purpose_of_the_known_shape_is_accepted(cursor: CursorWrapper, purpose: str) -> None:
    add_stepup(cursor, add_user(cursor), purpose=purpose)


@pytest.mark.parametrize(
    "purpose",
    ["", "Factor.change", "factor.", ".change", "a..b", "a.b.c", "a_.b", "_a", "a-b", "a b", "a1"],
)
def test_a_purpose_outside_the_shape_is_refused(cursor: CursorWrapper, purpose: str) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_stepup(c, user, purpose=purpose))
    assert refusal == "auth_stepup_purpose_shape"


@pytest.mark.parametrize(
    "key_hash",
    [KEY_HASH.upper(), KEY_HASH[:-1], "g" + KEY_HASH[1:]],
    ids=["upper-case", "short", "not-hex"],  # a longer one is cut off by varchar(64) first
)
def test_a_session_key_hash_must_be_lower_case_sha256_hex(
    cursor: CursorWrapper, key_hash: str
) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_stepup(c, user, session_key_hash=key_hash))
    assert refusal == "auth_stepup_key_hash_shape"


@pytest.mark.parametrize("size", [0, EVIDENCE_LENGTH - 1, EVIDENCE_LENGTH + 1, 32])
def test_the_evidence_mac_is_a_key_version_and_a_sha256_mac(
    cursor: CursorWrapper, size: int
) -> None:
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_stepup(c, user, evidence_mac=b"\0" * size))
    assert refusal == "auth_stepup_evidence_mac_length"


def test_the_evidence_length_is_the_key_version_then_the_mac() -> None:
    assert 4 + hashlib.sha256().digest_size == EVIDENCE_LENGTH


def test_every_step_up_names_the_factor_that_proved_it(cursor: CursorWrapper) -> None:
    """accounts.0013 (DECISIONS M3h-2): NULL lost its only meaning with the SET NULL action."""
    user = add_user(cursor)
    refusal = refused_by(cursor, lambda c: add_stepup(c, user, factor_id=None))
    assert refusal == "auth_stepup_factor_named"


@pytest.mark.parametrize(
    "verb", ["UPDATE auth_stepup SET purpose = 'export'", "DELETE FROM auth_stepup"]
)
def test_skiw_app_cannot_change_or_remove_evidence(cursor: CursorWrapper, verb: str) -> None:
    add_stepup(cursor, add_user(cursor))
    denied = pytest.raises(ProgrammingError, match="permission denied for table auth_stepup")
    with denied, transaction.atomic():
        cursor.execute(verb)


def test_a_factor_a_step_up_names_cannot_be_deleted(cursor: CursorWrapper) -> None:
    """Review R1 on PR 136: clearing factor_id would void genuine evidence that the M9 executor
    and the M16 drive_writer verify later. The delete is refused, as skiw_app, and nothing moves;
    a factor no step-up names is deleted as before; the other factor's rows are untouched."""
    user = add_user(cursor)
    named, other, free = add_totp(cursor, user), add_totp(cursor, user), add_totp(cursor, user)
    first = add_stepup(cursor, user, factor_id=named)
    second = add_stepup(cursor, user, factor_id=other)
    refused = pytest.raises(IntegrityError, match="auth_stepup_factor_id_fk")
    with refused, transaction.atomic():
        cursor.execute("DELETE FROM user_factor WHERE id = %s", [named])
    cursor.execute("DELETE FROM user_factor WHERE id = %s", [free])
    cursor.execute("SELECT id, factor_id FROM auth_stepup WHERE user_id = %s", [user])
    assert dict(cursor.fetchall()) == {first: named, second: other}
    cursor.execute("SELECT count(*) FROM user_factor WHERE id IN (%s, %s)", [named, other])
    assert cursor.fetchall() == [(2,)]


def test_the_factor_key_has_no_referential_action(cursor: CursorWrapper) -> None:
    """Pinned in the catalog: it is the composite (agency_id, id) key, and carries no ON DELETE
    action (no SET NULL, no CASCADE), which would change or remove evidence."""
    cursor.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
        " WHERE conrelid = 'public.auth_stepup'::regclass AND conname = 'auth_stepup_factor_id_fk'"
    )
    assert cursor.fetchall() == [
        ("FOREIGN KEY (agency_id, factor_id) REFERENCES user_factor(agency_id, id)",)
    ]


def test_deleting_a_named_factor_through_the_orm_is_refused_before_the_database(
    cursor: CursorWrapper,
) -> None:
    """The model says PROTECT, so Django raises ProtectedError and runs no DELETE at all."""
    user = add_user(cursor)
    named = add_totp(cursor, user)
    row = add_stepup(cursor, user, factor_id=named)
    with pytest.raises(ProtectedError):
        UserFactor.objects.get(id=named).delete()
    cursor.execute("SELECT factor_id FROM auth_stepup WHERE id = %s", [row])
    assert cursor.fetchall() == [(named,)]
