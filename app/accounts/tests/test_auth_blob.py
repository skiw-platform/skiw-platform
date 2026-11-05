"""Login and credential blobs (spec §4.1 `login_blob_ct`, `lookup_blob_ct`; plan M3b, A3). Keys
are generated per run; no database."""

import base64
import itertools
import secrets
import uuid
from collections.abc import Callable, Iterator

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from accounts.auth import blob
from accounts.auth.blob import LoginRecord
from accounts.auth.passwords import HASH_BYTES, SALT_BYTES
from tests.settings_env import AUTH_BOUNDS

USER, AGENCY = uuid.uuid4(), uuid.uuid4()
EMAIL = "adviser@example.test"
CREDENTIAL = secrets.token_bytes(64)
LOGIN_L, CREDENTIAL_L = 220, 60  # 12 + 192 + 16 and 12 + 32 + 16 (no header, owner 2026-11-04)


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
    old, newest = key_line(1, size=40), key_line(65_535)  # 40 bytes: HKDF still gives AES-256
    use_keys(old)
    sealed_v1 = blob.seal_login(RECORD, EMAIL)
    use_keys(newest, old)
    sealed_new = blob.seal_login(RECORD, EMAIL)
    use_keys(newest)  # the newest alone opens the second blob, not the first
    assert blob.open_login(sealed_new, EMAIL) == RECORD
    assert blob.open_login(sealed_v1, EMAIL) is None
    use_keys(newest, old)
    assert blob.open_login(sealed_v1, EMAIL) == blob.open_login(sealed_new, EMAIL) == RECORD


def test_the_version_is_bound_by_the_aad(use_keys: Callable[..., None]) -> None:
    same = base64.b64encode(secrets.token_bytes(32)).decode()
    use_keys(f"v2:{same}")
    sealed = blob.seal_login(RECORD, EMAIL)
    use_keys(f"v1:{same}")  # the same key under another version: only the AAD differs
    assert blob.open_login(sealed, EMAIL) is None
    use_keys(f"v2:{same}")
    assert blob.open_login(sealed, EMAIL) == RECORD


def test_the_aes_key_is_derived_not_the_raw_key(use_keys: Callable[..., None]) -> None:
    raw = secrets.token_bytes(32)
    use_keys("v1:" + base64.b64encode(raw).decode())
    sealed = blob.seal_login(RECORD, EMAIL)
    aad = b"\0\x01" + blob.LOGIN_AAD + EMAIL.encode()  # the exact AAD: only the key differs
    with pytest.raises(InvalidTag):
        AESGCM(raw).decrypt(sealed[: blob.NONCE], sealed[blob.NONCE :], aad)


@pytest.fixture
def attempts(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    seen: list[int] = []
    real = blob._attempt

    def counted(cipher: AESGCM, sealed: bytes, aad: bytes) -> bytes | None:
        seen.append(int.from_bytes(aad[:2], "big"))
        return real(cipher, sealed, aad)

    monkeypatch.setattr(blob, "_attempt", counted)
    return seen


def test_every_listed_version_is_tried_whatever_opens_the_blob(
    use_keys: Callable[..., None], attempts: list[int]
) -> None:
    """Owner 2026-11-04 (1): a real blob, a decoy and an oldest-version blob do the same work."""
    lines = key_line(3), key_line(2), key_line(1)
    use_keys(lines[2])
    oldest = blob.seal_login(RECORD, EMAIL)
    use_keys(*lines)
    newest = blob.seal_login(RECORD, EMAIL)
    decoy = secrets.token_bytes(LOGIN_L)
    attempts.clear()
    for sealed, opened in ((newest, RECORD), (decoy, None), (oldest, RECORD)):
        assert blob.open_login(sealed, EMAIL) == opened
        assert attempts == [3, 2, 1]
        attempts.clear()
    assert blob.open_credential(secrets.token_bytes(CREDENTIAL_L), CREDENTIAL) is None
    assert attempts == [3, 2, 1]


def test_a_blob_has_no_fixed_leading_bytes(use_keys: object) -> None:
    """Owner 2026-11-04 (5): nothing in clear, so a blob and a random decoy look alike."""
    logins = {blob.seal_login(RECORD, EMAIL)[:2] for _ in range(64)}
    credentials = {blob.seal_credential(USER, AGENCY, CREDENTIAL)[:2] for _ in range(64)}
    assert len(logins) > 1 and len(credentials) > 1


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


FACTOR = uuid.uuid4()
SECRET = secrets.token_bytes(20)
FACTOR_L = 48  # 12 + 20 + 16


def test_a_factor_secret_round_trips_at_its_fixed_length(use_keys: object) -> None:
    sealed = blob.seal_factor_secret(SECRET, FACTOR, USER, AGENCY)
    assert len(sealed) == FACTOR_L
    assert blob.open_factor_secret(sealed, FACTOR, USER, AGENCY) == SECRET
    assert all(blob.open_factor_secret(b, FACTOR, USER, AGENCY) is None for b in flips(sealed))
    assert blob.open_factor_secret(sealed[:-1], FACTOR, USER, AGENCY) is None


def test_a_factor_secret_is_bound_to_its_factor_user_and_agency(use_keys: object) -> None:
    sealed = blob.seal_factor_secret(SECRET, FACTOR, USER, AGENCY)
    other = uuid.uuid4()
    for ids in ((other, USER, AGENCY), (FACTOR, other, AGENCY), (FACTOR, USER, other)):
        assert blob.open_factor_secret(sealed, *ids) is None
    assert blob.open_factor_secret(sealed, USER, FACTOR, AGENCY) is None  # order matters


@pytest.mark.parametrize("size", [0, 19, 21, 32])
def test_only_a_20_byte_secret_is_sealed(use_keys: object, size: int) -> None:
    with pytest.raises(ValueError, match="20 bytes"):
        blob.seal_factor_secret(secrets.token_bytes(size), FACTOR, USER, AGENCY)


def test_a_factor_secret_uses_its_own_subkey(use_keys: Callable[..., None]) -> None:
    """Plan M3f: an HKDF subkey of login_blob_key with info skiw-factor-secret-v1, so the lookup
    blobs' AES key never opens a factor secret even with the right AAD."""
    raw = secrets.token_bytes(32)
    use_keys("v1:" + base64.b64encode(raw).decode())
    sealed = blob.seal_factor_secret(SECRET, FACTOR, USER, AGENCY)
    aad = b"\0\x01" + blob.FACTOR_LABEL + FACTOR.bytes + USER.bytes + AGENCY.bytes
    lookup = blob.require_key()[1]
    with pytest.raises(InvalidTag):
        lookup.decrypt(sealed[: blob.NONCE], sealed[blob.NONCE :], aad)
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"skiw-factor-secret-v1")
    opened = AESGCM(hkdf.derive(raw)).decrypt(sealed[: blob.NONCE], sealed[blob.NONCE :], aad)
    assert opened == SECRET


def test_a_factor_secret_opens_under_every_listed_version(
    use_keys: Callable[..., None], attempts: list[int]
) -> None:
    old, new = key_line(1), key_line(2)
    use_keys(old)
    sealed_old = blob.seal_factor_secret(SECRET, FACTOR, USER, AGENCY)
    use_keys(new, old)
    attempts.clear()
    assert blob.open_factor_secret(sealed_old, FACTOR, USER, AGENCY) == SECRET
    assert attempts == [2, 1]
    use_keys(new)
    assert blob.open_factor_secret(sealed_old, FACTOR, USER, AGENCY) is None
