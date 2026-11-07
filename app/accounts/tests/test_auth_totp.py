"""TOTP codes (spec Flow 5.1 (2); plan M3 §3 M3f, §4 M3f row). Own code against the RFCs' own
vectors; no database."""

import hmac

import pytest
from pytest_django import Settings

from accounts.auth import totp

RFC_SECRET = b"12345678901234567890"  # RFC 4226 Appendix D and RFC 6238 Appendix B (SHA-1)

# RFC 4226 Appendix D: HOTP values for counters 0 to 9, 6 digits.
HOTP = ["755224", "287082", "359152", "969429", "338314"]
HOTP += ["254676", "287922", "162583", "399871", "520489"]

# RFC 6238 Appendix B, SHA-1 rows: Unix time, the step (T, hex in the RFC), the 8-digit TOTP. A
# 6-digit code is the same truncated value mod 10^6, so its last six digits.
TOTP = [
    (59, 0x1, "94287082"),
    (1111111109, 0x23523EC, "07081804"),
    (1111111111, 0x23523ED, "14050471"),
    (1234567890, 0x273EF07, "89005924"),
    (2000000000, 0x3F940AA, "69279037"),
    (20000000000, 0x27BC86AA, "65353130"),
]

NOW = 1_800_000_015.0  # mid-step, so ±0.5 s never crosses a boundary
STEP = int(NOW // 30)


@pytest.fixture
def skew(settings: Settings) -> Settings:
    settings.SKIW_TOTP_SKEW_STEPS = 1
    return settings


@pytest.mark.parametrize("counter, expected", list(enumerate(HOTP)))
def test_the_rfc_4226_hotp_vectors(counter: int, expected: str) -> None:
    assert totp.code(RFC_SECRET, counter) == expected


@pytest.mark.parametrize("unix_time, step, expected", TOTP)
def test_the_rfc_6238_appendix_b_sha1_vectors(unix_time: int, step: int, expected: str) -> None:
    assert totp.step_at(unix_time) == step
    assert totp.code(RFC_SECRET, step) == expected[-6:]
    assert totp.accept(RFC_SECRET, expected[-6:], last=0, now=unix_time) == step


def test_a_code_keeps_its_leading_zeros() -> None:
    assert totp.code(RFC_SECRET, 0x23523EC) == "081804"


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_one_step_either_side_is_accepted(skew: Settings, offset: int) -> None:
    secret = totp.new_secret()
    candidate = totp.code(secret, STEP + offset)
    assert totp.accept(secret, candidate, last=0, now=NOW) == STEP + offset


@pytest.mark.parametrize("offset", [-2, 2, -3, 3])
def test_two_steps_away_is_refused(skew: Settings, offset: int) -> None:
    secret = totp.new_secret()
    assert totp.accept(secret, totp.code(secret, STEP + offset), last=0, now=NOW) is None


def test_with_no_skew_only_the_current_step_is_accepted(settings: Settings) -> None:
    settings.SKIW_TOTP_SKEW_STEPS = 0
    secret = totp.new_secret()
    assert totp.accept(secret, totp.code(secret, STEP), last=0, now=NOW) == STEP
    assert totp.accept(secret, totp.code(secret, STEP - 1), last=0, now=NOW) is None
    assert totp.accept(secret, totp.code(secret, STEP + 1), last=0, now=NOW) is None


def test_the_same_step_twice_is_refused(skew: Settings) -> None:
    """The caller stores the accepted step (`sign_count`) and passes it back."""
    secret = totp.new_secret()
    candidate = totp.code(secret, STEP)
    accepted = totp.accept(secret, candidate, last=0, now=NOW)
    assert accepted == STEP
    assert totp.accept(secret, candidate, last=accepted, now=NOW) is None
    assert totp.accept(secret, candidate, last=accepted, now=NOW + 30) is None  # still in window


def test_an_earlier_step_after_a_later_one_is_refused(skew: Settings) -> None:
    secret = totp.new_secret()
    assert totp.accept(secret, totp.code(secret, STEP + 1), last=0, now=NOW) == STEP + 1
    assert totp.accept(secret, totp.code(secret, STEP), last=STEP + 1, now=NOW) is None
    assert totp.accept(secret, totp.code(secret, STEP - 1), last=STEP - 2, now=NOW) == STEP - 1


def test_another_secret_is_refused(skew: Settings) -> None:
    candidate = totp.code(totp.new_secret(), STEP)
    others = [totp.new_secret() for _ in range(5)]
    # 3 steps x 5 secrets: a chance collision is about 1.5e-5, so the test is not flaky
    assert all(totp.accept(other, candidate, last=0, now=NOW) is None for other in others)


@pytest.mark.parametrize(
    "candidate",
    ["", "12345", "1234567", " 123456", "123456 ", "123 456", "12345a", "\uff11" * 6, "\u0661" * 6],
)
def test_only_six_ascii_digits_are_compared(skew: Settings, candidate: str) -> None:
    """Full-width and Arabic-Indic digits pass `str.isdigit`; they are refused all the same."""
    seen: list[str] = []
    real = hmac.compare_digest

    def spy(a: str, b: str) -> bool:
        seen.append(b)
        return real(a, b)

    secret = totp.new_secret()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(hmac, "compare_digest", spy)
        assert totp.accept(secret, candidate, last=0, now=NOW) is None
    assert seen == []


def test_every_step_in_the_window_is_compared_whichever_matches(skew: Settings) -> None:
    secret = totp.new_secret()
    real = hmac.compare_digest
    for offset in (-1, 0, 1, 5):
        seen: list[str] = []

        def spy(a: str, b: str, seen: list[str] = seen) -> bool:
            seen.append(a)
            return real(a, b)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(hmac, "compare_digest", spy)
            totp.accept(secret, totp.code(secret, STEP + offset), last=0, now=NOW)
        assert seen == [totp.code(secret, STEP + d) for d in (-1, 0, 1)]


def test_a_new_secret_is_20_random_bytes() -> None:
    secrets_made = {totp.new_secret() for _ in range(32)}
    assert len(secrets_made) == 32 and {len(s) for s in secrets_made} == {20}


def test_the_key_uri_carries_the_fixed_issuer_and_the_email_percent_encoded() -> None:
    uri = totp.uri(RFC_SECRET, "ann+work@example.test")
    assert uri == (
        "otpauth://totp/SKIW%20Assistant:ann%2Bwork@example.test"
        "?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=SKIW%20Assistant"
        "&algorithm=SHA1&digits=6&period=30"
    )
    assert totp.text(RFC_SECRET) == "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # RFC 4648 of the RFC secret


def test_the_key_uri_cannot_be_bent_by_the_account_name() -> None:
    uri = totp.uri(RFC_SECRET, "a b&issuer=Evil?x=1#frag/é@example.test")
    label, _, query = uri.removeprefix("otpauth://totp/").partition("?")
    assert " " not in uri and "#" not in uri and "&issuer=Evil" not in uri
    assert label.startswith("SKIW%20Assistant:") and query.count("issuer=") == 1
