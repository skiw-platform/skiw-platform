"""Login and credential blobs (spec §4.1 `login_blob_ct`, `lookup_blob_ct`; plan M3b, A3). Keys
are generated per run; no database."""

import base64
import itertools
import secrets
import uuid
from collections.abc import Callable, Iterator

import pytest

from accounts.auth import blob
from accounts.auth.blob import LoginRecord
from accounts.auth.passwords import HASH_BYTES, SALT_BYTES
from tests.settings_env import AUTH_BOUNDS

USER, AGENCY = uuid.uuid4(), uuid.uuid4()
EMAIL = "adviser@example.test"
CREDENTIAL = secrets.token_bytes(64)
LOGIN_L, CREDENTIAL_L = 222, 62  # plan M3b [A]: 2 + 12 + 192 + 16 and 2 + 12 + 32 + 16


def key_line(version: int, size: int = 32) -> str:
    return f"v{version}:" + base64.b64encode(secrets.token_bytes(size)).decode()


@pytest.fixture
def use_keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    def use(*lines: str) -> None:
        monkeypatch.delenv("LOGIN_BLOB_KEY_FILE", raising=False)
        monkeypatch.setenv("LOGIN_BLOB_KEY", "\n".join(lines))
        blob.require_key.cache_clear()

    use(key_line(1))
    yield use
    blob.require_key.cache_clear()


def encoded(memory_kib: int, time_cost: int, parallelism: int) -> str:
    """An Argon2id encoded hash in the library's format, without the cost of computing it."""
    salt = base64.b64encode(bytes(SALT_BYTES)).decode().rstrip("=")
    digest = base64.b64encode(bytes(HASH_BYTES)).decode().rstrip("=")
    return f"$argon2id$v=19$m={memory_kib},t={time_cost},p={parallelism}${salt}${digest}"


RECORD = LoginRecord(USER, AGENCY, encoded(65_536, 3, 1))


def flips(data: bytes) -> Iterator[bytes]:
    for index in range(len(data)):
        yield data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1 :]


def test_login_and_credential_round_trip_at_their_fixed_lengths(use_keys: object) -> None:
    sealed = blob.seal_login(RECORD, EMAIL)
    assert len(sealed) == LOGIN_L and blob.open_login(sealed, EMAIL) == RECORD
    credential = blob.seal_credential(USER, AGENCY, CREDENTIAL)
    assert len(credential) == CREDENTIAL_L
    assert blob.open_credential(credential, CREDENTIAL) == (USER, AGENCY)


def test_the_email_is_normalised_before_it_binds_the_blob(use_keys: object) -> None:
    sealed = blob.seal_login(RECORD, EMAIL)
    fullwidth_a = "\uff21"  # NFKC maps it to "A"; then strip and lower-case
    assert blob.open_login(sealed, f"  {fullwidth_a}DVISER@Example.TEST ") == RECORD


def test_a_blob_does_not_open_for_another_email_credential_or_purpose(use_keys: object) -> None:
    login = blob.seal_login(RECORD, EMAIL)
    credential = blob.seal_credential(USER, AGENCY, CREDENTIAL)
    assert blob.open_login(login, "other@example.test") is None
    assert blob.open_credential(credential, CREDENTIAL[:-1] + b"\0") is None
    assert blob.open_credential(login, CREDENTIAL) is None
    assert blob.open_login(credential, EMAIL) is None


def test_every_flipped_bit_and_every_truncation_is_refused(use_keys: object) -> None:
    sealed = blob.seal_login(RECORD, EMAIL)
    assert all(blob.open_login(bad, EMAIL) is None for bad in flips(sealed))
    assert all(blob.open_login(sealed[:size], EMAIL) is None for size in range(len(sealed)))
    assert blob.open_login(sealed + b"\0", EMAIL) is None
    credential = blob.seal_credential(USER, AGENCY, CREDENTIAL)
    assert all(blob.open_credential(bad, CREDENTIAL) is None for bad in flips(credential))


def test_another_key_or_an_unlisted_version_is_refused(use_keys: Callable[..., None]) -> None:
    use_keys(key_line(1))
    first = blob.seal_login(RECORD, EMAIL)
    use_keys(key_line(1))  # same version number, other key
    assert blob.open_login(first, EMAIL) is None
    use_keys(key_line(2))
    second = blob.seal_login(RECORD, EMAIL)
    use_keys(key_line(1))  # v2 no longer listed
    assert blob.open_login(second, EMAIL) is None


def test_the_newest_version_seals_and_every_listed_one_opens(use_keys: Callable[..., None]) -> None:
    old = key_line(1, size=40)  # longer than 32 bytes: HKDF still gives an AES-256 key
    use_keys(old)
    sealed_v1 = blob.seal_login(RECORD, EMAIL)
    use_keys(old, key_line(65_535))
    sealed_new = blob.seal_login(RECORD, EMAIL)
    assert sealed_new[:2] == (65_535).to_bytes(2, "big") and sealed_v1[:2] == b"\0\x01"
    assert blob.open_login(sealed_v1, EMAIL) == blob.open_login(sealed_new, EMAIL) == RECORD


@pytest.mark.parametrize(
    "parameters",
    list(
        itertools.product(
            *(
                AUTH_BOUNDS[f"SKIW_ARGON2_{name}"]
                for name in ("MEMORY_KIB", "TIME_COST", "PARALLELISM")
            )
        )
    ),
)
def test_every_parameter_set_within_the_bounds_gives_one_length(
    use_keys: object, parameters: tuple[int, int, int]
) -> None:
    record = LoginRecord(USER, AGENCY, encoded(*parameters))
    assert len(blob.seal_login(record, EMAIL)) == LOGIN_L
    assert blob.open_login(blob.seal_login(record, EMAIL), EMAIL) == record


def test_a_hash_too_long_for_the_fixed_size_is_refused_not_cut(use_keys: object) -> None:
    record = LoginRecord(USER, AGENCY, "$" * (blob.LOGIN_SIZE - 33))
    with pytest.raises(ValueError, match="does not fit"):
        blob.seal_login(record, EMAIL)
    fits = LoginRecord(USER, AGENCY, "$" * (blob.LOGIN_SIZE - 34))
    assert blob.open_login(blob.seal_login(fits, EMAIL), EMAIL) == fits
