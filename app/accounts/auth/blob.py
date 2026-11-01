"""Login and credential lookup blobs under `login_blob_key` (spec §4.1 `login_blob_ct`,
`lookup_blob_ct`, §8.4 H4; plan M3b). No database access.

blob = version (2 bytes, big-endian) || nonce (12 random bytes) || AES-256-GCM ciphertext || tag
(16 bytes). The AES key is HKDF-SHA-256 of the key version under LABEL, so a key line longer than
32 bytes still gives one AES-256 key. The AAD is the version bytes || a purpose label || the
lookup value, so a blob moved to another row or purpose fails its tag. Plaintexts are padded to
one size per purpose, so every blob of a purpose has one length (login 222, credential 62) and
an Argon2 parameter change cannot tell old blobs from new ones. The newest version seals; every
listed one opens.
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
OVERHEAD = 2 + NONCE + 16


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


def _seal(plaintext: bytes, purpose: bytes, value: bytes) -> bytes:
    version, cipher = next(iter(require_key().items()))
    header = version.to_bytes(2, "big")
    nonce = os.urandom(NONCE)
    return header + nonce + cipher.encrypt(nonce, plaintext, header + purpose + value)


def _open(blob: bytes, size: int, purpose: bytes, value: bytes) -> bytes | None:
    """The plaintext, or None for a blob of the wrong length, an unlisted version or a failed
    tag. Logs nothing: in M3e every unknown email reaches here with a decoy."""
    if len(blob) != size + OVERHEAD:
        return None
    cipher = require_key().get(int.from_bytes(blob[:2], "big"))
    if cipher is None:
        return None
    try:
        return cipher.decrypt(blob[2 : 2 + NONCE], blob[2 + NONCE :], blob[:2] + purpose + value)
    except InvalidTag:
        return None


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
