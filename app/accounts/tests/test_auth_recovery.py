"""Recovery-code normalisation, MACs and the transaction rule (accounts.auth.recovery; spec D7,
plan M3 §3 M3f). No database; the live tests are in test_auth_recovery_live.py."""

import hashlib
import hmac
import uuid
from collections.abc import Callable

import pytest
from django.db.transaction import TransactionManagementError

from accounts import source_key
from accounts.auth import recovery, throttle

from .test_auth_blob import key_line

CANONICAL = "ABCDEFGHJKMNPQRS"


def use_source_keys(monkeypatch: pytest.MonkeyPatch, *lines: str) -> list[bytes]:
    """tenant_source_key from these lines, newest first; returns the raw keys in that order."""
    monkeypatch.delenv("TENANT_SOURCE_KEY_FILE", raising=False)
    monkeypatch.setenv("TENANT_SOURCE_KEY", "\n".join(lines))
    source_key.require_key.cache_clear()
    return [key for _, key in source_key.require_key()]


def expected(key: bytes, user: uuid.UUID, code: str) -> bytes:
    """The plan's construction built by hand: the label, then each value behind its 8-byte
    length."""
    message = b"skiw-recovery-v1"
    for value in (str(user).encode(), code.encode()):
        message += len(value).to_bytes(8, "big") + value
    return hmac.new(key, message, hashlib.sha256).digest()


class Untouchable(str):
    """A candidate whose methods fail the test: only len() may run on it."""

    def isascii(self) -> bool:
        raise AssertionError("worked on an over-long candidate")

    def upper(self) -> str:
        raise AssertionError("worked on an over-long candidate")


def test_the_alphabet_is_crockford_base32_and_a_code_holds_80_bits() -> None:
    assert recovery.ALPHABET == "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    assert len(recovery.ALPHABET) ** recovery.LENGTH == 2**80 and recovery.COUNT == 10


@pytest.mark.parametrize(
    "candidate",
    [
        "ABCD-EFGH-JKMN-PQRS",
        "abcd-efgh-jkmn-pqrs",
        "AbCdEfGhJkMnPqRs",
        "ABCD EFGH JKMN PQRS",
        "  ABCD-EFGH-JKMN-PQRS ",
        "A-B-C-D-E-F-G-H-J-K-M-N-P-Q-R-S",
        " " * 16 + CANONICAL,  # exactly INPUT_MAX characters
    ],
)
def test_accepted_forms_name_the_same_code(candidate: str) -> None:
    assert recovery.normalise(candidate) == CANONICAL


def test_i_and_l_read_as_one_and_o_as_zero() -> None:
    assert recovery.normalise("10Ol-iI0o-TVWX-YZ23") == "10011100TVWXYZ23"


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "ABCD-EFGH-JKMN-PQR",  # 15 symbols
        "ABCD-EFGH-JKMN-PQRST",  # 17
        "ABCU-EFGH-JKMN-PQRS",  # U is not Crockford and reads as nothing
        "ABCD_EFGH_JKMN_PQRS",
        "ABCD.EFGH.JKMN.PQRS",
        "ABCD\tEFGH-JKMN-PQRS",
        "ABCD-EFGH-JKMN-PQRS\n",
        "\uff21BCD-EFGH-JKMN-PQRS",  # full-width A
        "\u0410BCD-EFGH-JKMN-PQRS",  # Cyrillic A
        "\u0131BCD-EFGH-JKMN-PQRS",  # dotless i: upper() makes it I, so 1, without the ASCII check
        "ABCD\u2010EFGH-JKMN-PQRS",  # a Unicode hyphen
        " " * 17 + CANONICAL,  # INPUT_MAX + 1
    ],
)
def test_other_input_is_refused(candidate: str) -> None:
    assert recovery.normalise(candidate) is None


def test_an_over_long_candidate_is_refused_before_any_work() -> None:
    assert recovery.normalise(Untouchable("A" * 10_000)) is None


def test_macs_follow_the_plan_construction_newest_version_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    newest, older = use_source_keys(monkeypatch, key_line(2), key_line(1))
    user = uuid.uuid4()
    mac = recovery.macs(user, CANONICAL)
    assert mac == [expected(newest, user, CANONICAL), expected(older, user, CANONICAL)]
    assert all(len(value) == 32 for value in mac)


def test_a_mac_is_bound_to_the_user_and_the_code(monkeypatch: pytest.MonkeyPatch) -> None:
    use_source_keys(monkeypatch, key_line(1))
    user = uuid.uuid4()
    mac = recovery.macs(user, CANONICAL)
    assert recovery.macs(uuid.uuid4(), CANONICAL) != mac
    assert recovery.macs(user, "ABCDEFGHJKMNPQRT") != mac


def test_the_label_is_apart_from_every_other_use_of_the_source_key() -> None:
    """The throttle HMACs have no length prefix, so no label may be a prefix of another."""
    others = [source_key.LABEL, throttle.ACCOUNT, throttle.IP, throttle.LOCK]
    label = recovery.LABEL
    assert not any(label.startswith(other) or other.startswith(label) for other in others)


@pytest.mark.parametrize(
    "call",
    [
        lambda: recovery.generate(uuid.uuid4(), uuid.uuid4()),
        lambda: recovery.consume(uuid.uuid4(), CANONICAL),
    ],
    ids=["generate", "consume"],
)
def test_both_refuse_to_run_outside_a_transaction(call: Callable[[], object]) -> None:
    with pytest.raises(TransactionManagementError):
        call()
