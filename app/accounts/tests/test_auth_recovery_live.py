"""Recovery codes against the real tables (accounts.auth.recovery; spec D7; plan M3 §3 M3f, §4 M3f
row "each recovery code once, two parallel uses → one success; regenerate invalidates old
codes"), as skiw_app on committed users (kept). The second-factor route is M3f-3c."""

import logging
import os
import re
import secrets
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext

from accounts import source_key
from accounts.auth import recovery
from accounts.factor_model import TOTP_SECRET_CT_LENGTH, UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import committed_user
from .test_auth_blob import key_line
from .test_auth_recovery import USERS_REPORT, VERSION_REPORT, stored_form, use_source_keys

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]
PARALLEL = 10
SHOWN = re.compile(r"[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){3}")


def generated(user: AppUser) -> list[str]:
    with with_agency(user.agency_id):
        return recovery.generate(user.agency_id, user.id)


def used(user: AppUser, code: str) -> bool:
    with with_agency(user.agency_id):
        return recovery.consume(user.id, code)


def stored(user: AppUser) -> list[bytes]:
    with with_agency(user.agency_id), connection.cursor() as cursor:
        cursor.execute(
            "SELECT secret_ct FROM user_factor WHERE user_id = %s AND kind = 'recovery'", [user.id]
        )
        return [bytes(value) for (value,) in cursor.fetchall()]


def macs_of(user: AppUser, codes: list[str]) -> set[bytes]:
    version, key = source_key.require_key()[0]
    return {stored_form(version, key, user.id, code.replace("-", "")) for code in codes}


def version_report(agency: uuid.UUID) -> list[tuple[int, int]]:
    """The runbook's report, run as skiw_app bound to `agency` (the operator runs it as
    `postgres`, which sees every agency)."""
    with with_agency(agency), connection.cursor() as cursor:
        cursor.execute(VERSION_REPORT)
        return [(int(version), int(users)) for version, users in cursor.fetchall()]


def users_of(agency: uuid.UUID, version: int) -> list[str]:
    """The runbook's list of the users one version signs (its `00000001` replaced), as skiw_app."""
    with with_agency(agency), connection.cursor() as cursor:
        cursor.execute(USERS_REPORT.replace("00000001", f"{version:08x}"))
        return [email for (email,) in cursor.fetchall()]


def in_parallel[T](user: AppUser, action: Callable[[], T]) -> list[T]:
    """PARALLEL threads, each on its own connection and with_agency() transaction, released
    together once every transaction is open."""
    start = threading.Barrier(PARALLEL)

    def one(_: int) -> T:
        try:
            with with_agency(user.agency_id):
                start.wait()
                return action()
        finally:
            connection.close()

    with ThreadPoolExecutor(PARALLEL) as pool:
        return list(pool.map(one, range(PARALLEL)))


@pytest.fixture
def user() -> AppUser:
    return committed_user()


def test_ten_codes_are_shown_and_only_their_macs_stored(user: AppUser) -> None:
    codes = generated(user)
    assert len(set(codes)) == 10 and all(SHOWN.fullmatch(code) for code in codes)
    rows = stored(user)
    assert len(rows) == 10 and set(rows) == macs_of(user, codes)


def test_each_code_works_once_and_a_wrong_one_deletes_nothing(user: AppUser) -> None:
    first, second, *_ = generated(user)
    assert not used(user, "0000-0000-0000-0000") and len(stored(user)) == 10
    assert used(user, first)
    assert not used(user, first) and not used(user, first.lower())
    assert used(user, f" {second.lower().replace('-', ' ')} ")
    assert len(stored(user)) == 8


def test_parallel_uses_of_one_code_succeed_once(user: AppUser) -> None:
    code = generated(user)[0]
    results = in_parallel(user, lambda: recovery.consume(user.id, code))
    assert results.count(True) == 1 and len(stored(user)) == 9


def test_parallel_regenerations_leave_exactly_one_set_of_ten(user: AppUser) -> None:
    results = in_parallel(user, lambda: recovery.generate(user.agency_id, user.id))
    rows = stored(user)
    assert len(rows) == 10
    assert [set(rows) == macs_of(user, codes) for codes in results].count(True) == 1


def test_regenerating_invalidates_every_old_code(user: AppUser) -> None:
    old = generated(user)
    new = generated(user)
    assert [used(user, code) for code in old] == [False] * 10
    assert len(stored(user)) == 10 and used(user, new[0])


def test_another_users_or_agencys_codes_cannot_be_used(user: AppUser, agency_b: uuid.UUID) -> None:
    """TEN-08 through the module: the user filter, the agency binding and the MAC's user id each
    stop it alone, and a write for another agency's user fails and changes nothing."""
    other, foreign = committed_user(), committed_user(agency=agency_b)
    others, foreigns = generated(other), generated(foreign)
    generated(user)
    assert not used(user, others[0])
    with with_agency(user.agency_id):
        assert not recovery.consume(foreign.id, foreigns[0])  # agency B's rows are not visible
    with with_agency(user.agency_id), connection.cursor() as cursor:  # other's MACs copied to user
        cursor.execute(
            "INSERT INTO user_factor (id, agency_id, user_id, kind, secret_ct)"
            " SELECT gen_random_uuid(), agency_id, %s, kind, secret_ct FROM user_factor"
            " WHERE user_id = %s",
            [user.id, other.id],
        )
    assert not used(user, others[1])  # the MAC names the user, not only the row
    for agency in (agency_b, user.agency_id):  # RLS WITH CHECK; composite FK to app_user
        with pytest.raises(DatabaseError), with_agency(user.agency_id):
            recovery.generate(agency, foreign.id)
    assert len(stored(user)) == 20 and len(stored(other)) == 10
    assert set(stored(foreign)) == macs_of(foreign, foreigns)
    assert used(other, others[0]) and used(foreign, foreigns[0])


def test_a_code_works_while_its_key_version_is_listed(
    user: AppUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    v1, v2 = key_line(1), key_line(2)
    use_source_keys(monkeypatch, v1)
    codes = generated(user)
    assert {row[:4].hex() for row in stored(user)} == {"00000001"}
    use_source_keys(monkeypatch, v2, v1)
    assert used(user, codes[0])  # made under v1 while v2 signs
    use_source_keys(monkeypatch, v2)
    assert not used(user, codes[1]) and len(stored(user)) == 9  # refused, not deleted
    use_source_keys(monkeypatch, v2, v1)
    fresh = generated(user)
    assert set(stored(user)) == macs_of(user, fresh)  # signed with v2, the newest
    assert {row[:4].hex() for row in stored(user)} == {"00000002"}
    use_source_keys(monkeypatch, v1)
    assert not used(user, fresh[0])


def test_no_code_reaches_a_log_a_query_or_a_repr(
    user: AppUser, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="django")  # django propagates to root (LOGGING)
    wrong = "0000-0000-0000-0000"
    with CaptureQueriesContext(connection) as queries:
        codes = generated(user)
        assert used(user, codes[0]) and not used(user, wrong)
    with with_agency(user.agency_id):
        row = UserFactor.objects.filter(user_id=user.id, kind="recovery").first()
    assert row is not None
    text = caplog.text + str(queries.captured_queries) + str(row) + repr(row)
    for code in [*codes, wrong]:
        for form in (code, code.replace("-", ""), code.lower()):
            assert form not in text


def test_the_runbook_report_counts_users_per_signing_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before a version leaves the key file the operator counts the users it still signs. The
    versions are random so that no other test's committed users can match."""
    older = secrets.randbelow(900_000) + 1
    newer = older + 50_000
    users = [committed_user() for _ in range(3)]
    use_source_keys(monkeypatch, key_line(older))
    generated(users[0])
    generated(users[1])
    use_source_keys(monkeypatch, key_line(newer), key_line(older))
    generated(users[1])  # regenerated: all under the newer version now
    generated(users[2])
    ours = {older, newer}
    assert [row for row in version_report(users[0].agency_id) if row[0] in ours] == [
        (older, 1),
        (newer, 2),
    ]
    agency = users[0].agency_id
    assert users_of(agency, older) == [users[0].email]
    assert sorted(users_of(agency, newer)) == sorted(user.email for user in users[1:])


def test_only_recovery_rows_are_used_or_replaced(user: AppUser) -> None:
    """Rows of another kind are neither consumed by a use nor deleted by a regeneration: both are
    scoped to kind `recovery`. (No other kind can hold a recovery MAC: the `secret_ct` rules of
    accounts.0010 and 0015.)"""
    code = "ABCD-EFGH-JKMN-PQRS"
    with with_agency(user.agency_id), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO user_factor (id, agency_id, user_id, kind, secret_ct) VALUES"
            " (gen_random_uuid(), %s, %s, 'totp', %s)",
            [user.agency_id, user.id, os.urandom(TOTP_SECRET_CT_LENGTH)],
        )
        # Retired, so the kept row holds no lookup blob: the tenancy reversal test's accounts.0008
        # reverse puts back a 62-byte blob rule (as logins.unseal does for login blobs).
        cursor.execute(
            "INSERT INTO user_factor (id, agency_id, user_id, kind, credential_id, retired_at)"
            " VALUES (gen_random_uuid(), %s, %s, 'passkey', %s, now())",
            [user.agency_id, user.id, os.urandom(16)],
        )

    def other_rows() -> int:
        with with_agency(user.agency_id):
            return UserFactor.objects.filter(user_id=user.id).exclude(kind="recovery").count()

    assert not used(user, code) and other_rows() == 2
    generated(user)
    generated(user)
    assert other_rows() == 2 and len(stored(user)) == 10
