"""Recovery codes (spec D7, Flow 5.1 (2); plan M3 §3 M3f, DECISIONS M3f-2, M3f-3a). COUNT per
user, each LENGTH Crockford base32 symbols from `secrets` (80 bits), shown once as four groups of
four. Each code is one `user_factor` row (kind `recovery`) whose `secret_ct` is the
`tenant_source_key` version that signed it (RECOVERY_VERSION_BYTES, big-endian), then HMAC-SHA-256
under that version over LABEL || field(user id) || field(code), so the table holds no code. The
newest version signs; a candidate is matched under every listed version, each MAC behind its own
version, so a code keeps working across a rotation until its version is removed from the key file.

The version is in clear so that, before a version leaves the key file, an operator can count the
users whose codes it still signs (runbook host-rebuild.md, "Rotating `tenant_source_key`"). It is
no secret (a session row names its version too), and it is outside the MAC: a row whose version
was changed matches no candidate.

Both functions run in the caller's with_agency() transaction, as revoke.mark does, so M3f-3 can
write the AUTH-07 marker in the transaction that regenerates. A use is one `DELETE ... RETURNING`:
of two concurrent uses of a code the second waits on the first's row lock, then finds no row, so a
code works once. The match is the database's equality on a keyed MAC, not compare_digest: timing
could only tell how far the MAC of an attacker's own guess agrees with a stored one, and without
the key no guess can be steered toward a stored MAC. Nothing here logs; a code leaves only as
generate()'s return value (UNI-09)."""

import hashlib
import hmac
import secrets
import uuid

from django.db import connection
from django.db.transaction import TransactionManagementError

from accounts import source_key
from accounts.factor_model import RECOVERY_VERSION_BYTES, UserFactor

LABEL = b"skiw-recovery-v1"  # keeps this use of the key apart from the session MAC and throttle
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32: no I, L, O or U
COUNT = 10  # spec D7
LENGTH = 16  # symbols of 5 bits each: 80 bits [A, plan M3f]
GROUP = 4  # symbols per displayed group
INPUT_MAX = 32  # the longest candidate looked at: 16 symbols, separators and slack (UNI-03)
SYMBOLS = frozenset(ALPHABET)
READ_AS = str.maketrans({"I": "1", "L": "1", "O": "0", "-": None, " ": None})
LOCK_USER = "SELECT 1 FROM app_user WHERE id = %s FOR UPDATE"
DELETE_ALL = "DELETE FROM user_factor WHERE user_id = %s AND kind = 'recovery'"
CONSUME = (
    "DELETE FROM user_factor WHERE user_id = %s AND kind = 'recovery' AND secret_ct = ANY(%s)"
    " RETURNING id"
)


def _in_transaction() -> None:
    """Fail loudly, not by RLS's empty answer, when called outside the caller's with_agency()."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("recovery codes run inside the caller's with_agency()")


def _new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalise(candidate: str) -> str | None:
    """The LENGTH symbols `candidate` names, or None. Case is ignored, hyphens and spaces anywhere
    are dropped, I and L read as 1 and O as 0 (Crockford). Anything else is refused: U, other
    punctuation or whitespace, any non-ASCII character (checked before upper(), which maps some of
    them to ASCII), too few or too many symbols. A candidate longer than INPUT_MAX is refused
    before anything else is done with it."""
    if len(candidate) > INPUT_MAX or not candidate.isascii():
        return None
    code = candidate.upper().translate(READ_AS)
    return code if len(code) == LENGTH and SYMBOLS.issuperset(code) else None


def macs(user: uuid.UUID, code: str) -> list[bytes]:
    """The stored form of the normalised `code` for `user` under each listed key version, newest
    first: the version in RECOVERY_VERSION_BYTES big-endian bytes, then the MAC under it."""
    message = LABEL + source_key.field(str(user)) + source_key.field(code)
    return [
        version.to_bytes(RECOVERY_VERSION_BYTES, "big")
        + hmac.new(key, message, hashlib.sha256).digest()
        for version, key in source_key.require_key()
    ]


def generate(agency: uuid.UUID, user: uuid.UUID) -> list[str]:
    """Replaces every recovery code of `user` with COUNT new ones and returns them for display:
    the only time they exist outside this call. The user row is locked first, so two
    regenerations take turns and leave exactly COUNT rows."""
    _in_transaction()
    codes = [_new_code() for _ in range(COUNT)]
    with connection.cursor() as cursor:
        cursor.execute(LOCK_USER, [user])
        cursor.execute(DELETE_ALL, [user])
    UserFactor.objects.bulk_create(
        UserFactor(agency_id=agency, user_id=user, kind="recovery", secret_ct=macs(user, code)[0])
        for code in codes
    )
    return ["-".join(code[i : i + GROUP] for i in range(0, LENGTH, GROUP)) for code in codes]


def consume(user: uuid.UUID, candidate: str) -> bool:
    """True when `candidate` is one of `user`'s unused codes, which is then deleted, so it never
    works again; False for anything else, with no query when it cannot be a code."""
    _in_transaction()
    code = normalise(candidate)
    if code is None:
        return False
    with connection.cursor() as cursor:
        cursor.execute(CONSUME, [user, macs(user, code)])
        return cursor.fetchone() is not None
