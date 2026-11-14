"""The passkey list's created time (DECISIONS M3g-2s-2; plan M3 §3 M3g). GET /api/auth/factors gives
each passkey in use exactly its id and `created_at` (ISO 8601 UTC, or null for a row made before
accounts.0016), oldest first: a null one first, equal times by id. TOTPs keep `{"id"}`. As
skiw_app. Every passkey a test commits is deleted afterwards, and every login blob cleared: the
tenancy reversal test's accounts.0008 reverse refuses a kept one (M3g-1b, M3e-2a)."""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from django.utils import timezone

from accounts.auth import blob
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .test_action_wrapper_live import signed_in
from .test_factor_remove_live import first_totp, listed, migrate

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]

MADE: list[tuple[uuid.UUID, uuid.UUID]] = []  # (agency, factor) written by `add`
EARLIER = datetime(2026, 11, 1, tzinfo=UTC)
unsealed = sign_in.unsealed  # autouse: a kept login blob breaks the accounts.0008 reverse


@pytest.fixture(autouse=True)
def no_passkey_kept(live_db: None) -> Iterator[None]:
    MADE.clear()
    yield
    for agency, factor in MADE:
        with with_agency(agency):
            UserFactor.objects.filter(id=factor, kind="passkey").delete()


def user_signed_in() -> tuple[AppUser, str]:
    user, _, _ = sign_in.signing_in()
    return user, signed_in(user, factor="totp")


def add(user: AppUser, factor: uuid.UUID, *, retired: bool = False) -> None:
    """A passkey of `user` with id `factor`, written through the ORM as `confirm_passkey` does."""
    credential = os.urandom(16)
    sealed = blob.seal_credential(user.id, user.agency_id, credential)
    with with_agency(user.agency_id):
        UserFactor.objects.create(
            id=factor,
            agency_id=user.agency_id,
            user_id=user.id,
            kind="passkey",
            credential_id=credential,
            public_key=None if retired else b"\1" * 77,
            lookup_blob_ct=None if retired else sealed,
            retired_at=timezone.now() if retired else None,
        )
    MADE.append((user.agency_id, factor))


def created(user: AppUser, factor: uuid.UUID) -> datetime | None:
    with with_agency(user.agency_id):
        return UserFactor.objects.get(id=factor).created_at


def set_created(user: AppUser, at: datetime | None, *factors: uuid.UUID) -> None:
    with with_agency(user.agency_id):
        UserFactor.objects.filter(id__in=factors).update(created_at=at)


def iso(at: datetime | None) -> str | None:
    return None if at is None else at.astimezone(UTC).isoformat(timespec="microseconds")


def two_ids() -> tuple[uuid.UUID, uuid.UUID]:
    low, high = sorted([uuid.uuid4(), uuid.uuid4()])
    return low, high


def test_each_passkey_has_exactly_its_id_and_created_time_oldest_first() -> None:
    """Added high id first, so the order by time is not the order by id."""
    user, cookie = user_signed_in()
    low, high = two_ids()
    add(user, high)
    add(user, low)
    add(user, uuid.uuid4(), retired=True)  # not listed
    first, second = created(user, high), created(user, low)
    assert first is not None and second is not None and first < second
    body = listed(cookie)
    assert body == {
        "totp": [{"id": str(first_totp(user))}],  # TOTP shape unchanged
        "passkey": [
            {"id": str(high), "created_at": iso(first)},
            {"id": str(low), "created_at": iso(second)},
        ],
        "recovery_left": 10,
    }
    shown = datetime.fromisoformat(body["passkey"][0]["created_at"])
    assert shown == first and shown.utcoffset() == UTC.utcoffset(None)
    assert body["passkey"][0]["created_at"].endswith("+00:00")


def test_equal_created_times_are_ordered_by_id() -> None:
    user, cookie = user_signed_in()
    low, high = two_ids()
    add(user, high)
    add(user, low)
    set_created(user, EARLIER, low, high)
    assert listed(cookie)["passkey"] == [
        {"id": str(low), "created_at": iso(EARLIER)},
        {"id": str(high), "created_at": iso(EARLIER)},
    ]


def test_a_passkey_with_no_created_time_is_listed_first_as_null() -> None:
    """A row made before accounts.0016 has NULL: it is older than every dated one."""
    user, cookie = user_signed_in()
    dated, (low, high) = uuid.uuid4(), two_ids()
    add(user, dated)
    add(user, high)
    add(user, low)
    set_created(user, None, low, high)
    assert listed(cookie)["passkey"] == [
        {"id": str(low), "created_at": None},
        {"id": str(high), "created_at": None},
        {"id": str(dated), "created_at": iso(created(user, dated))},
    ]


def test_the_app_role_reaches_created_at_and_the_lookup_owner_does_not() -> None:
    """skiw_app's table grants cover the column; the definer's column grant (accounts.0015) does
    not grow to it."""
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT r, p FROM unnest(ARRAY['skiw_app', 'skiw_auth_lookup']) r,"
            " unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'REFERENCES']) p"
            " WHERE has_column_privilege(r, 'user_factor', 'created_at', p) ORDER BY 1, 2"
        ).fetchall()
    assert rows == [("skiw_app", "INSERT"), ("skiw_app", "SELECT"), ("skiw_app", "UPDATE")]


def column() -> tuple[object, ...] | None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
        return conn.execute(
            "SELECT data_type, is_nullable, column_default FROM information_schema.columns"
            " WHERE table_name = 'user_factor' AND column_name = 'created_at'"
        ).fetchone()


def test_accounts_0016_reverses_and_reapplies_with_the_created_times_kept() -> None:
    """The reverse keeps the column, its default and its values (as accounts.0014, 0015); the
    re-apply finds them and the list shows the same time."""
    stamped = ("timestamp with time zone", "YES", "statement_timestamp()")
    user, cookie = user_signed_in()
    factor = uuid.uuid4()
    add(user, factor)
    before = created(user, factor)
    assert before is not None and column() == stamped
    try:
        migrate("accounts", "0015")
        assert column() == stamped
    finally:
        migrate()
    assert created(user, factor) == before and column() == stamped
    assert listed(cookie)["passkey"] == [{"id": str(factor), "created_at": iso(before)}]


def test_a_first_apply_leaves_existing_rows_null_and_stamps_new_ones() -> None:
    """On a database that never had the column, accounts.0016 gives the rows already there NULL
    (time unknown), not the migration's time, and new rows their insert time. The column is
    dropped as its owner to stand for that database; the other tests' rows lose only their times."""
    user, cookie = user_signed_in()
    old, new = uuid.uuid4(), uuid.uuid4()
    add(user, old)
    try:
        migrate("accounts", "0015")
        with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as conn:
            conn.execute('ALTER TABLE "user_factor" DROP COLUMN "created_at"')
    finally:
        migrate()
    add(user, new)
    stamped = created(user, new)
    assert created(user, old) is None and stamped is not None
    assert listed(cookie)["passkey"] == [
        {"id": str(old), "created_at": None},
        {"id": str(new), "created_at": iso(stamped)},
    ]
