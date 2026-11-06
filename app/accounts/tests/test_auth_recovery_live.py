"""Recovery codes against the real tables (accounts.auth.recovery; spec D7; plan M3 §3 M3f, §4 M3f
row "each recovery code once, two parallel uses → one success; regenerate invalidates old
codes"), as skiw_app on committed users (kept). The second-factor route is M3f-3."""

import logging
import re
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext

from accounts import source_key
from accounts.auth import recovery
from accounts.factor_model import UserFactor
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import committed_user
from .test_auth_blob import key_line
from .test_auth_recovery import expected, use_source_keys

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
    key = source_key.require_key()[0][1]
    return {expected(key, user.id, code.replace("-", "")) for code in codes}


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
    use_source_keys(monkeypatch, v2, v1)
    assert used(user, codes[0])  # made under v1 while v2 signs
    use_source_keys(monkeypatch, v2)
    assert not used(user, codes[1]) and len(stored(user)) == 9  # refused, not deleted
    use_source_keys(monkeypatch, v2, v1)
    fresh = generated(user)
    assert set(stored(user)) == macs_of(user, fresh)  # signed with v2, the newest
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


def test_only_recovery_rows_are_used_or_replaced(user: AppUser) -> None:
    """A TOTP row, even one holding a recovery MAC, is neither consumed by a use nor deleted by a
    regeneration: both are scoped to kind `recovery`."""
    code = "ABCD-EFGH-JKMN-PQRS"
    mac = recovery.macs(user.id, recovery.normalise(code) or "")[0]
    with with_agency(user.agency_id), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO user_factor (id, agency_id, user_id, kind, secret_ct)"
            " VALUES (gen_random_uuid(), %s, %s, 'totp', %s)",
            [user.agency_id, user.id, mac],
        )

    def totp_rows() -> int:
        with with_agency(user.agency_id):
            return UserFactor.objects.filter(user_id=user.id, kind="totp").count()

    assert not used(user, code) and totp_rows() == 1
    generated(user)
    generated(user)
    assert totp_rows() == 1 and len(stored(user)) == 10
