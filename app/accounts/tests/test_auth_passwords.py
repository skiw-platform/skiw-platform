"""Argon2id hashing (spec T5, AUTH-04; plan M3b). Most tests set tiny parameters through the
settings fixture, so `make test` stays fast; the bounds themselves are tested in
app/tests/test_auth_settings.py, and one test hashes at the lowest allowed values (T5's own)."""

import uuid
from collections.abc import Iterator

import pytest
from argon2 import PasswordHasher, Type, extract_parameters
from argon2.low_level import hash_secret
from django.apps import apps
from pytest_django import Settings

from accounts.auth import blob, passwords
from accounts.tests.test_auth_blob import encoded, key_line
from tests.settings_env import AUTH_BOUNDS

# phc-winner-argon2 src/test.c (commit f57e61e1), Argon2id v=19, t=2, m=2^8 KiB, p=1, password
# "password", salt "somesalt": the reference implementation's own known answer.
VECTOR = "$argon2id$v=19$m=256,t=2,p=1$c29tZXNhbHQ$nf65EOgLrQMR/uIPnA4rEsF5h7TKyQwu9U1bMCHGi/4"


@pytest.fixture
def tiny(settings: Settings) -> Iterator[Settings]:
    settings.SKIW_ARGON2_MEMORY_KIB, settings.SKIW_ARGON2_TIME_COST = 64, 1
    settings.SKIW_ARGON2_PARALLELISM = 2
    yield settings


def test_the_reference_known_answer() -> None:
    raw = hash_secret(b"password", b"somesalt", 2, 256, 1, 32, Type.ID)
    assert raw.decode() == VECTOR
    assert passwords.verify(VECTOR, "password")
    assert not passwords.verify(VECTOR, "differentpassword")


def test_a_new_hash_carries_the_configured_parameters(tiny: Settings) -> None:
    stored = passwords.hash_password("correct horse")
    parameters = extract_parameters(stored)
    assert (parameters.type, parameters.version) == (Type.ID, 19)
    assert (parameters.memory_cost, parameters.time_cost, parameters.parallelism) == (64, 1, 2)
    assert (parameters.salt_len, parameters.hash_len) == (16, 32)
    assert passwords.verify(stored, "correct horse")
    assert not passwords.verify(stored, "correct horse ")
    assert passwords.hash_password("correct horse") != stored  # random salt


def test_a_malformed_hash_verifies_false(tiny: Settings) -> None:
    assert not passwords.verify("not-a-hash", "x")
    assert not passwords.verify(passwords.hash_password("x")[:-4], "x")


def test_needs_rehash_follows_the_configured_parameters(tiny: Settings) -> None:
    stored = passwords.hash_password("x")
    assert not passwords.needs_rehash(stored)
    tiny.SKIW_ARGON2_TIME_COST = 2
    assert passwords.needs_rehash(stored)


def test_dummy_verify_runs_one_verify_with_the_current_parameters(
    tiny: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    real = PasswordHasher.verify

    def spy(self: PasswordHasher, hash: str | bytes, password: str | bytes) -> bool:
        seen.append(str(hash))
        return real(self, hash, password)

    monkeypatch.setattr(PasswordHasher, "verify", spy)
    passwords.dummy_verify("guess")
    passwords.dummy_verify("guess")
    assert len(seen) == 2 and seen[0] == seen[1]  # one dummy hash per parameter set
    real_hash = passwords.hash_password("x")
    assert extract_parameters(seen[0]) == extract_parameters(real_hash)
    tiny.SKIW_ARGON2_MEMORY_KIB = 128
    passwords.dummy_verify("guess")
    assert extract_parameters(seen[2]).memory_cost == 128


def test_the_app_makes_the_dummy_hash_before_any_request() -> None:
    """Plan Risk 2: the first unknown-email login must not also pay for making the dummy hash."""
    passwords._dummy_hash.cache_clear()
    apps.get_app_config("accounts").ready()
    assert passwords._dummy_hash.cache_info().currsize == 1


def test_a_real_hash_at_the_lowest_allowed_values_fits_the_login_blob(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    floor = tuple(
        AUTH_BOUNDS[f"SKIW_ARGON2_{n}"][0] for n in ("MEMORY_KIB", "TIME_COST", "PARALLELISM")
    )
    assert floor == (65_536, 3, 1)  # T5: 64 MiB, t=3, p=1 is the weakest allowed (PR 78 P2)
    settings.SKIW_ARGON2_MEMORY_KIB, settings.SKIW_ARGON2_TIME_COST = floor[0], floor[1]
    settings.SKIW_ARGON2_PARALLELISM = floor[2]
    stored = passwords.hash_password("x")
    assert len(stored) == len(encoded(*floor))  # the blob tests' synthetic hashes match the format
    monkeypatch.setenv("LOGIN_BLOB_KEY", key_line(1))
    blob.require_key.cache_clear()
    record = blob.LoginRecord(uuid.uuid4(), uuid.uuid4(), stored)
    sealed = blob.seal_login(record, "a@example.test")
    assert len(sealed) == 220 and blob.open_login(sealed, "a@example.test") == record
    blob.require_key.cache_clear()


@pytest.mark.parametrize(
    "stored, typed",
    [
        ("caf\u00e9 cr\u00e8me", "cafe\u0301 cre\u0300me"),  # NFC enrols, NFD signs in
        ("cafe\u0301 cre\u0300me", "caf\u00e9 cr\u00e8me"),  # and the other way round
        ("\ufb01ne \uff21", "fine A"),  # compatibility forms: the ligature, a full-width letter
    ],
)
def test_a_password_is_nfkc_normalised_before_it_is_hashed_or_verified(
    tiny: Settings, stored: str, typed: str
) -> None:
    """PR 115 R1 P3 #1 (NIST SP 800-63B-4 §3.1.1.2): NFKC, as for the email."""
    assert passwords.verify(passwords.hash_password(stored), typed)
    raw = PasswordHasher(memory_cost=64, time_cost=1, parallelism=2).hash(stored)
    assert passwords.verify(raw, stored) is (passwords.normalise(stored) == stored)


def test_normalising_changes_nothing_else(tiny: Settings) -> None:
    stored = passwords.hash_password(" Correct Horse ")
    assert passwords.normalise(" Correct Horse ") == " Correct Horse "
    assert not passwords.verify(stored, "correct horse")
    assert not passwords.verify(stored, "Correct Horse")


def test_dummy_verify_normalises_like_verify(
    tiny: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str | bytes] = []
    real = PasswordHasher.verify

    def spy(self: PasswordHasher, hash: str | bytes, password: str | bytes) -> bool:
        seen.append(password)
        return real(self, hash, password)

    monkeypatch.setattr(PasswordHasher, "verify", spy)
    passwords.dummy_verify("cafe\u0301")
    assert seen == ["caf\u00e9"]
