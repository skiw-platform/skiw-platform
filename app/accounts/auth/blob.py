"""Login and credential lookup blobs under `login_blob_key` (spec §4.1 `login_blob_ct`,
`lookup_blob_ct`, §8.4 H4; plan M3b, M3e-1a). No database access.

blob = nonce (12 random bytes) || AES-256-GCM ciphertext || tag (16 bytes). Nothing in a blob is
in clear, so it reads as random bytes, like the decoy `guard.auth_lookup_login` returns for an
unknown email (owner decision 2026-11-04: a cleartext key version would tell the two apart). Each
version's AES key is HKDF-SHA-256 of that version's key under LABEL, so a key line longer than 32
bytes still gives one AES-256 key. The AAD is the version bytes || a purpose label || the lookup
value, so a blob moved to another row, purpose or version fails its tag. Plaintexts are padded to
one size per purpose, so every blob of a purpose has one length (login 220, credential 60). The
newest version seals; opening tries every listed version, always all of them, so a decoy and a
real blob cost the same.
"""

import functools
import os
import unicodedata
import uuid
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

LABEL = b"skiw-blob-key-v1"
LOGIN_AAD = b"skiw-login-v1"
CREDENTIAL_AAD = b"skiw-credential-v1"
LOGIN_SIZE = 192  # user id 16 || agency id 16 || 2-byte length || Argon2 encoded hash || zeros
CREDENTIAL_SIZE = 32  # user id 16 || agency id 16
NONCE = 12
OVERHEAD = NONCE + 16


@dataclass(frozen=True)
class LoginRecord:
    user_id: uuid.UUID
    agency_id: uuid.UUID
    password_hash: str


@functools.cache
def require_key() -> dict[int, AESGCM]:
    """One AES-GCM cipher per listed login_blob_key version, read once; raises (fail closed) on a
    missing or malformed key. The first entry is the newest version."""
    ciphers: dict[int, AESGCM] = {}
    for version, key in settings.SKIW_LOGIN_BLOB_KEYS():
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=LABEL)
        ciphers[version] = AESGCM(hkdf.derive(key))
    return ciphers


def normalise_email(email: str) -> str:
    return unicodedata.normalize("NFKC", email).strip().lower()


def _aad(version: int, purpose: bytes, value: bytes) -> bytes:
    return version.to_bytes(2, "big") + purpose + value


def _seal(plaintext: bytes, purpose: bytes, value: bytes) -> bytes:
    version, cipher = next(iter(require_key().items()))
    nonce = os.urandom(NONCE)
    return nonce + cipher.encrypt(nonce, plaintext, _aad(version, purpose, value))


def _attempt(cipher: AESGCM, blob: bytes, aad: bytes) -> bytes | None:
    try:
        return cipher.decrypt(blob[:NONCE], blob[NONCE:], aad)
    except InvalidTag:
        return None


def _open(blob: bytes, size: int, purpose: bytes, value: bytes) -> bytes | None:
    """The plaintext, or None for a blob of the wrong length or one no listed version opens. Every
    listed version is tried, also after one opens it, so the work does not depend on which version
    sealed it or whether any did. Logs nothing: in M3e every unknown email reaches here with a
    decoy."""
    if len(blob) != size + OVERHEAD:
        return None
    opened = None
    for version, cipher in require_key().items():
        plaintext = _attempt(cipher, blob, _aad(version, purpose, value))
        if opened is None:
            opened = plaintext
    return opened


def seal_login(record: LoginRecord, email: str) -> bytes:
    encoded = record.password_hash.encode("ascii")
    body = record.user_id.bytes + record.agency_id.bytes + len(encoded).to_bytes(2, "big")
    if len(body) + len(encoded) > LOGIN_SIZE:
        raise ValueError("the password hash does not fit the fixed login blob size")
    plaintext = (body + encoded).ljust(LOGIN_SIZE, b"\0")
    return _seal(plaintext, LOGIN_AAD, normalise_email(email).encode())


def open_login(blob: bytes, email: str) -> LoginRecord | None:
    plaintext = _open(blob, LOGIN_SIZE, LOGIN_AAD, normalise_email(email).encode())
    if plaintext is None:
        return None
    length = int.from_bytes(plaintext[32:34], "big")
    return LoginRecord(
        uuid.UUID(bytes=plaintext[:16]),
        uuid.UUID(bytes=plaintext[16:32]),
        plaintext[34 : 34 + length].decode("ascii"),
    )


def seal_credential(user_id: uuid.UUID, agency_id: uuid.UUID, credential_id: bytes) -> bytes:
    return _seal(user_id.bytes + agency_id.bytes, CREDENTIAL_AAD, credential_id)


def open_credential(blob: bytes, credential_id: bytes) -> tuple[uuid.UUID, uuid.UUID] | None:
    plaintext = _open(blob, CREDENTIAL_SIZE, CREDENTIAL_AAD, credential_id)
    if plaintext is None:
        return None
    return uuid.UUID(bytes=plaintext[:16]), uuid.UUID(bytes=plaintext[16:])
