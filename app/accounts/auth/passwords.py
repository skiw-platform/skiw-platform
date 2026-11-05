"""Argon2id password hashes (spec T5, AUTH-04; plan M3b). Parameters come from the interim host
config (owner Q6 (a)); salt and hash lengths are fixed here because the login blob's fixed size
depends on them (accounts.auth.blob). A verify reads the parameters from the stored hash.

Every password is NFKC-normalised before it is hashed, verified or counted (NIST SP 800-63B-4
§3.1.1.2; PR 115 R1 P3 #1), as emails are (blob.normalise_email): a device that sends "é" as one
code point and one that sends "e" plus a combining accent then give the same hash. Nothing else is
changed: no strip, no case folding.
"""

import functools
import secrets
import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from django.conf import settings

SALT_BYTES = 16
HASH_BYTES = 32


def _parameters() -> tuple[int, int, int]:
    return (
        settings.SKIW_ARGON2_MEMORY_KIB,
        settings.SKIW_ARGON2_TIME_COST,
        settings.SKIW_ARGON2_PARALLELISM,
    )


@functools.cache
def _hasher(memory_kib: int, time_cost: int, parallelism: int) -> PasswordHasher:
    return PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_kib,
        parallelism=parallelism,
        hash_len=HASH_BYTES,
        salt_len=SALT_BYTES,
        type=Type.ID,
    )


@functools.cache
def _dummy_hash(memory_kib: int, time_cost: int, parallelism: int) -> str:
    """A hash of a random password, made once per parameter set, for unknown accounts."""
    return _hasher(memory_kib, time_cost, parallelism).hash(secrets.token_urlsafe(32))


def normalise(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    return _hasher(*_parameters()).hash(normalise(password))


def verify(encoded: str, password: str) -> bool:
    try:
        return _hasher(*_parameters()).verify(encoded, normalise(password))
    except (VerificationError, InvalidHashError):
        return False


def dummy_verify(password: str) -> None:
    """The same Argon2 work as `verify` with the current parameters, for an unknown account (M3e).
    `warm` makes the dummy hash at start-up, so no first call pays for it."""
    verify(_dummy_hash(*_parameters()), password)


def warm() -> None:
    _dummy_hash(*_parameters())


def needs_rehash(encoded: str) -> bool:
    return _hasher(*_parameters()).check_needs_rehash(encoded)
