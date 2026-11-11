"""Step-up evidence MAC, purposes and the transaction rule (accounts.auth.stepup; spec §4.1
`auth_stepup`, AUTH-09; plan M3 §3 M3h, DECISIONS M3h-2). No database: rows are built in memory.
The live tests are in test_auth_stepup_live.py."""

import hashlib
import hmac
import re
import uuid
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from django.db.transaction import TransactionManagementError
from django.test import RequestFactory

from accounts import source_key
from accounts.auth import recovery, stepup, throttle
from accounts.stepup_model import EVIDENCE_LENGTH, PURPOSE, AuthStepup

from .test_auth_blob import key_line
from .test_auth_recovery import use_source_keys

KEY_HASH = hashlib.sha256(b"auth-stepup-unit").hexdigest()
# A time with microseconds, given in +08:00: the MAC takes the same instant in UTC.
AT = datetime(2026, 11, 10, 20, 0, 0, 654_321, tzinfo=timezone(timedelta(hours=8)))


def row(**columns: Any) -> AuthStepup:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "agency_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "factor_id": uuid.uuid4(),
        "purpose": stepup.FACTOR_CHANGE,
        "verified_at": AT,
        "session_key_hash": KEY_HASH,
        **columns,
    }
    return AuthStepup(**values)


def signed(**columns: Any) -> AuthStepup:
    made = row(**columns)
    made.evidence_mac = stepup.evidence(made)
    return made


def expected(key: bytes, made: AuthStepup) -> bytes:
    """The DECISIONS M3h-1 layout built by hand: the label, then each value behind its 8-byte
    length, the time in UTC to the microsecond."""
    message = b"skiw-stepup-v1"
    values = (
        made.id,
        made.agency_id,
        made.user_id,
        made.factor_id,
        made.purpose,
        "2026-11-10T12:00:00.654321+00:00",
        made.session_key_hash,
    )
    for value in values:
        data = str(value).encode()
        message += len(data).to_bytes(8, "big") + data
    return hmac.new(key, message, hashlib.sha256).digest()


def test_evidence_is_the_newest_version_then_the_mac_of_every_other_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    newest, _ = use_source_keys(monkeypatch, key_line(7), key_line(3))
    made = signed()
    assert bytes(made.evidence_mac) == (7).to_bytes(4, "big") + expected(newest, made)
    assert len(made.evidence_mac) == EVIDENCE_LENGTH


def test_the_largest_key_version_fits_the_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    use_source_keys(monkeypatch, key_line(999_999))
    made = signed()
    assert bytes(made.evidence_mac)[:4] == (999_999).to_bytes(4, "big")
    assert stepup._genuine(made)


CHANGES: dict[str, Callable[[AuthStepup], object]] = {
    "id": lambda _: uuid.uuid4(),
    "agency_id": lambda _: uuid.uuid4(),
    "user_id": lambda _: uuid.uuid4(),
    "factor_id": lambda _: uuid.uuid4(),
    "purpose": lambda _: "export",
    "verified_at": lambda made: made.verified_at + timedelta(microseconds=1),
    "session_key_hash": lambda _: hashlib.sha256(b"another session").hexdigest(),
}


@pytest.mark.parametrize("column", sorted(CHANGES))
def test_every_column_is_under_the_mac(monkeypatch: pytest.MonkeyPatch, column: str) -> None:
    use_source_keys(monkeypatch, key_line(1))
    made = signed()
    assert stepup._genuine(made)  # positive control
    setattr(made, column, CHANGES[column](made))
    assert not stepup._genuine(made)


def test_the_same_instant_in_any_zone_is_the_same_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_source_keys(monkeypatch, key_line(1))
    made = signed()
    made.verified_at = AT.astimezone(UTC)
    assert stepup._genuine(made)


def test_a_flipped_bit_or_a_changed_version_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    use_source_keys(monkeypatch, key_line(2), key_line(1))
    made = signed()
    mac = bytes(made.evidence_mac)
    made.evidence_mac = mac[:-1] + bytes([mac[-1] ^ 1])
    assert not stepup._genuine(made)
    made.evidence_mac = (1).to_bytes(4, "big") + mac[4:]  # listed, but not the signing version
    assert not stepup._genuine(made)
    made.evidence_mac = (99).to_bytes(4, "big") + mac[4:]  # unlisted: no key, not "try the newest"
    assert not stepup._genuine(made)


def test_an_older_listed_version_verifies_and_a_removed_one_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = key_line(1)
    use_source_keys(monkeypatch, old)
    made = signed()
    use_source_keys(monkeypatch, key_line(2), old)
    assert stepup._genuine(made)
    assert bytes(stepup.evidence(made))[:4] == (2).to_bytes(4, "big")  # the newest signs
    use_source_keys(monkeypatch, key_line(2))
    assert not stepup._genuine(made)


def test_a_row_without_a_factor_is_never_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    use_source_keys(monkeypatch, key_line(1))
    with pytest.raises(ValueError, match="names the factor"):
        signed(factor_id=None)


def test_the_label_is_apart_from_every_other_use_of_the_source_key() -> None:
    """The throttle HMACs have no length prefix, so no label may be a prefix of another."""
    others = [source_key.LABEL, recovery.LABEL, throttle.ACCOUNT, throttle.IP, throttle.LOCK]
    label = stepup.LABEL
    assert not any(label.startswith(other) or other.startswith(label) for other in others)


def test_every_purpose_fits_the_table_check_and_only_a_totp_proves_one() -> None:
    assert {"factor.change"} == stepup.PURPOSES
    assert all(re.fullmatch(PURPOSE, purpose) for purpose in stepup.PURPOSES)
    assert {"totp"} == stepup.FACTOR_KINDS  # spec D7; M3g adds the passkey


def test_a_step_up_carries_no_mac_and_no_session_hash() -> None:
    assert [f.name for f in fields(stepup.StepUp)] == ["id", "factor_id", "purpose", "verified_at"]


CALLS: dict[str, Callable[[str], object]] = {
    "record": lambda purpose: stepup.record(RequestFactory().post("/"), uuid.uuid4(), purpose),
    "recent": lambda purpose: stepup.recent(RequestFactory().get("/"), purpose),
}


@pytest.mark.parametrize("call", sorted(CALLS))
def test_both_refuse_an_unknown_purpose(call: str) -> None:
    with pytest.raises(ValueError, match="unknown step-up purpose"):
        CALLS[call]("export")


@pytest.mark.parametrize("call", sorted(CALLS))
def test_both_refuse_to_run_outside_a_transaction(call: str) -> None:
    with pytest.raises(TransactionManagementError):
        CALLS[call](stepup.FACTOR_CHANGE)


def test_a_timezone_naive_instant_is_never_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    use_source_keys(monkeypatch, key_line(1))
    with pytest.raises(ValueError, match="timezone-aware"):
        stepup.evidence(row(verified_at=datetime(2026, 11, 1, 12, 0, 0)))
