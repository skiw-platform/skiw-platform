"""The tenant token (spec §4.2 "Tenant binding" items 2 and 3, v1.21; plan M4c-4a). One encoding
for the minter here and the verifier `guard.current_agency()` (`tenancy/0003`); the committed vector
in `tests/test_token.py` pins it.

`v<n>.<agency uuid>.<xid>.<MAC>`: `n` in decimal (1 to 999999, no leading zeros), the uuid
lowercase and hyphenated, the xid unsigned decimal, the MAC base64url without padding. The MAC is
HMAC-SHA-256 under key version n over four fields, each preceded by its length as a 4-byte
big-endian unsigned integer: `skiw-tenant-v1` (ASCII), the database name (UTF-8), the agency id
(16 raw bytes) and the xid (8 bytes, big-endian unsigned). Nothing here logs or returns a key.
"""

import base64
import hashlib
import hmac
import uuid

DOMAIN = b"skiw-tenant-v1"
MAX_VERSION = 999_999
MAX_XID = 2**64 - 1


def mac_input(database: str, agency_id: uuid.UUID, xid: int) -> bytes:
    if not 0 <= xid <= MAX_XID:
        raise ValueError("xid is out of range")
    fields = (DOMAIN, database.encode(), agency_id.bytes, xid.to_bytes(8, "big"))
    return b"".join(len(field).to_bytes(4, "big") + field for field in fields)


def mint(version: int, key: bytes, database: str, agency_id: uuid.UUID, xid: int) -> str:
    if not 1 <= version <= MAX_VERSION:
        raise ValueError("key version is out of range")
    digest = hmac.new(key, mac_input(database, agency_id, xid), hashlib.sha256).digest()
    mac = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return f"v{version}.{agency_id}.{xid}.{mac}"
