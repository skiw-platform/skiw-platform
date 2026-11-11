"""Step-up evidence against the real table (accounts.auth.stepup; spec §4.1 `auth_stepup`, AUTH-09;
plan M3 §4 M3h row "a row inserted by SQL with a bad MAC, another session's hash, another purpose
or older than 5 min -> recent() returns None"; DECISIONS M3h-2), as skiw_app. Users are committed
and kept (TEN-03); each test runs in one with_agency() transaction that is rolled back, because
skiw_app may not delete step-up rows. Forged rows go in by raw INSERT, which skiw_app may do."""

import copy
import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.contrib.sessions.backends import db
from django.db import connection, transaction
from django.db.backends.utils import CursorWrapper
from django.http import HttpRequest
from django.test import RequestFactory
from django.utils import timezone

from accounts import source_key
from accounts.auth import stepup
from accounts.auth.login import login
from accounts.factor_model import RECOVERY_SECRET_CT_LENGTH
from accounts.session import SessionStore, stored_key
from accounts.stepup_model import AuthStepup
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import Clock, committed_user
from .test_auth_blob import key_line
from .test_auth_recovery import use_source_keys
from .test_auth_stepup import CHANGES
from .test_stepup_table_live import add_totp
from .test_user_tables_live import add_factor, add_user

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
CHANGE = stepup.FACTOR_CHANGE
PROBE = "test.probe"  # a purpose of the table's shape that PURPOSES does not list


def signed_in(user: AppUser) -> HttpRequest:
    """A request whose session holds a completed login of `user` (login() as the views call it)."""
    request = RequestFactory().post("/")
    request.session = SessionStore()
    login(request, user, factor="totp")
    return request


def key_hash(request: HttpRequest) -> str:
    return stored_key(str(request.session.session_key))


@pytest.fixture
def user() -> AppUser:
    return committed_user()


@pytest.fixture
def signed(user: AppUser) -> HttpRequest:
    return signed_in(user)


@pytest.fixture
def cursor(signed: HttpRequest, user: AppUser) -> Iterator[CursorWrapper]:
    with with_agency(user.agency_id), connection.cursor() as bound:
        yield bound
        transaction.set_rollback(True)


@pytest.fixture
def factor(cursor: CursorWrapper, user: AppUser) -> uuid.UUID:
    return add_totp(cursor, user.id)


def genuine(request: HttpRequest, user: AppUser, factor: uuid.UUID, **columns: Any) -> AuthStepup:
    """A row as record() would sign it for this session, at `verified_at` (default 1 min ago)."""
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "agency_id": user.agency_id,
        "user_id": user.id,
        "factor_id": factor,
        "purpose": CHANGE,
        "verified_at": timezone.now() - timedelta(minutes=1),
        "session_key_hash": key_hash(request),
        **columns,
    }
    made = AuthStepup(**values)
    made.evidence_mac = stepup.evidence(made)
    return made


def insert(cursor: CursorWrapper, made: AuthStepup) -> None:
    """The row by raw SQL, as injected SQL running as skiw_app could write it."""
    cursor.execute(
        "INSERT INTO auth_stepup (id, agency_id, user_id, factor_id, purpose, verified_at,"
        " session_key_hash, evidence_mac) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        [
            made.id,
            made.agency_id,
            made.user_id,
            made.factor_id,
            made.purpose,
            made.verified_at,
            made.session_key_hash,
            bytes(made.evidence_mac),
        ],
    )


def test_record_writes_evidence_that_recent_returns(
    signed: HttpRequest, cursor: CursorWrapper, factor: uuid.UUID, clock: Clock
) -> None:
    """verified_at has microseconds; the MAC over the value read back verifies, so timestamptz
    kept it exactly."""
    clock.now = clock.now.replace(microsecond=654_321)
    made = stepup.record(signed, factor, CHANGE)
    assert stepup.recent(signed, CHANGE) == made
    cursor.execute(
        "SELECT verified_at, session_key_hash, substring(evidence_mac FROM 1 FOR 4)"
        " FROM auth_stepup WHERE id = %s",
        [made.id],
    )
    version = source_key.require_key()[0][0]
    assert cursor.fetchall() == [(clock.now, key_hash(signed), version.to_bytes(4, "big"))]


def test_a_raw_row_with_the_right_mac_counts(
    signed: HttpRequest, user: AppUser, cursor: CursorWrapper, factor: uuid.UUID
) -> None:
    """The positive control for every forgery below: raw SQL with a genuine MAC is accepted."""
    made = genuine(signed, user, factor)
    insert(cursor, made)
    found = stepup.recent(signed, CHANGE)
    assert found is not None and found.id == made.id


@pytest.mark.parametrize("column", sorted(CHANGES))
def test_a_row_whose_mac_was_made_over_another_value_is_refused(
    signed: HttpRequest, user: AppUser, cursor: CursorWrapper, factor: uuid.UUID, column: str
) -> None:
    """Each column on its own: the MAC is genuine for another value, the row holds this
    session's, so it passes every filter and only the MAC refuses it."""
    made = genuine(signed, user, factor)
    other = copy.copy(made)
    setattr(other, column, CHANGES[column](made))
    made.evidence_mac = stepup.evidence(other)
    insert(cursor, made)
    assert stepup.recent(signed, CHANGE) is None


MACS: dict[str, Callable[[bytes], bytes]] = {
    "bit-flipped": lambda mac: mac[:-1] + bytes([mac[-1] ^ 1]),
    "version-changed": lambda mac: (99).to_bytes(4, "big") + mac[4:],
    "zeros": lambda mac: bytes(len(mac)),
}


@pytest.mark.parametrize("change", sorted(MACS))
def test_a_changed_mac_is_refused_and_logged_without_its_material(
    signed: HttpRequest,
    user: AppUser,
    cursor: CursorWrapper,
    factor: uuid.UUID,
    change: str,
    security_log: pytest.LogCaptureFixture,
) -> None:
    made = genuine(signed, user, factor)
    made.evidence_mac = MACS[change](bytes(made.evidence_mac))
    insert(cursor, made)
    assert stepup.recent(signed, CHANGE) is None
    assert [r.getMessage() for r in security_log.records] == [
        "step-up row rejected: its evidence does not verify"
    ]
    for secret in (bytes(made.evidence_mac).hex(), key_hash(signed), str(made.id)):
        assert secret not in security_log.text


def test_a_removed_key_version_voids_its_rows_and_a_listed_older_one_does_not(
    monkeypatch: pytest.MonkeyPatch, signed: HttpRequest, cursor: CursorWrapper, factor: uuid.UUID
) -> None:
    old = key_line(1)
    use_source_keys(monkeypatch, old)
    made = stepup.record(signed, factor, CHANGE)
    use_source_keys(monkeypatch, key_line(2), old)
    assert stepup.recent(signed, CHANGE) == made
    use_source_keys(monkeypatch, key_line(2))
    assert stepup.recent(signed, CHANGE) is None


def test_a_genuine_row_of_another_session_user_or_purpose_is_not_this_ones(
    monkeypatch: pytest.MonkeyPatch,
    signed: HttpRequest,
    user: AppUser,
    cursor: CursorWrapper,
    factor: uuid.UUID,
) -> None:
    """Each row's MAC verifies for its own values, so only the filters refuse it here."""
    elsewhere = signed_in(user)  # the same user, another session
    stranger = AppUser(id=add_user(cursor), agency_id=user.agency_id)
    strangers_factor = add_totp(cursor, stranger.id)
    rows = {
        "session": genuine(elsewhere, user, factor),
        "user": genuine(signed, stranger, strangers_factor),
        "purpose": genuine(signed, user, factor, purpose=PROBE),
    }
    for made in rows.values():
        insert(cursor, made)
    assert stepup.recent(signed, CHANGE) is None
    with pytest.raises(ValueError, match="unknown step-up purpose"):  # a genuine row, no purpose
        stepup.recent(signed, PROBE)
    monkeypatch.setattr(stepup, "PURPOSES", stepup.PURPOSES | {PROBE})
    # Each is found where it belongs, so the refusals above are the filters, not the MACs.
    assert getattr(stepup.recent(elsewhere, CHANGE), "id", None) == rows["session"].id
    assert getattr(stepup.recent(signed, PROBE), "id", None) == rows["purpose"].id


def test_a_step_up_counts_for_exactly_the_max_age(
    signed: HttpRequest, cursor: CursorWrapper, factor: uuid.UUID, clock: Clock
) -> None:
    made = stepup.record(signed, factor, CHANGE)
    clock.advance(timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN))
    assert stepup.recent(signed, CHANGE) == made
    clock.advance(timedelta(microseconds=1))
    assert stepup.recent(signed, CHANGE) is None


def test_a_step_up_in_the_future_does_not_count(
    signed: HttpRequest, user: AppUser, cursor: CursorWrapper, factor: uuid.UUID, clock: Clock
) -> None:
    insert(cursor, genuine(signed, user, factor, verified_at=clock.now + timedelta(microseconds=1)))
    assert stepup.recent(signed, CHANGE) is None
    now = genuine(signed, user, factor, verified_at=clock.now)
    insert(cursor, now)
    assert getattr(stepup.recent(signed, CHANGE), "id", None) == now.id


def test_the_newest_genuine_row_wins_and_a_newer_forged_one_is_passed_over(
    signed: HttpRequest, user: AppUser, cursor: CursorWrapper, factor: uuid.UUID, clock: Clock
) -> None:
    older = genuine(signed, user, factor, verified_at=clock.now - timedelta(minutes=2))
    newer = genuine(signed, user, factor, verified_at=clock.now - timedelta(minutes=1))
    forged = genuine(signed, user, factor, verified_at=clock.now - timedelta(seconds=30))
    forged.evidence_mac = bytes(len(forged.evidence_mac))
    for made in (older, newer, forged):
        insert(cursor, made)
    assert getattr(stepup.recent(signed, CHANGE), "id", None) == newer.id


Add = Callable[[CursorWrapper, uuid.UUID], uuid.UUID]


def of_kind(kind: str, secret_ct: bytes | None) -> Add:
    def add(cursor: CursorWrapper, user: uuid.UUID) -> uuid.UUID:
        row = uuid.uuid4()
        add_factor(cursor, user, id=row, kind=kind, secret_ct=secret_ct)
        return row

    return add


NOT_PROOF: dict[str, Add] = {
    "recovery": of_kind("recovery", bytes(RECOVERY_SECRET_CT_LENGTH)),
    "passkey": of_kind("passkey", None),
    "another-users-totp": lambda cursor, _: add_totp(cursor, add_user(cursor)),
    "no-such-factor": lambda cursor, _: uuid.uuid4(),
}


@pytest.mark.parametrize("case", sorted(NOT_PROOF))
def test_only_the_users_own_totp_proves_a_step_up(
    signed: HttpRequest, user: AppUser, cursor: CursorWrapper, case: str
) -> None:
    """Review PR 136 R2: a recovery row is deleted by raw DELETE (sign-in, regenerate); a step-up
    naming it would make that DELETE fail on auth_stepup_factor_id_fk."""
    with pytest.raises(ValueError, match="own TOTP"):
        stepup.record(signed, NOT_PROOF[case](cursor, user.id), CHANGE)
    cursor.execute("SELECT count(*) FROM auth_stepup WHERE user_id = %s", [user.id])
    assert cursor.fetchall() == [(0,)]


def test_a_session_with_no_completed_login_has_no_step_up(cursor: CursorWrapper) -> None:
    request = RequestFactory().post("/")
    request.session = SessionStore()
    assert stepup.recent(request, CHANGE) is None
    with pytest.raises(ValueError, match="signed-in session"):
        stepup.record(request, uuid.uuid4(), CHANGE)
    request.session = db.SessionStore()
    with pytest.raises(TypeError, match="accounts session store"):
        stepup.recent(request, CHANGE)
