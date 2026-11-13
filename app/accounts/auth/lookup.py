"""The pre-tenant lookups (spec §4.1 "Pre-tenant lookups", Flow 5.1 (0); plan M3 §3 M3e, M3g).
The only callers of `guard.auth_lookup_login` and `guard.auth_lookup_credential` (Semgrep
`auth-lookup-accounts-auth-only`, TEN-10, TEN-12). Each function returns one opaque blob for any
key, known or not: a real blob opens, a decoy never does. Each call commits one `security_event`
(the function's own insert), so run them outside `with_agency()`: no tenant is known yet."""

import uuid
from dataclasses import dataclass

from django.db import connection

from accounts.auth.blob import normalise_email, open_credential


@dataclass(frozen=True)
class CredentialOwner:
    user_id: uuid.UUID
    agency_id: uuid.UUID


def _call(query: str, value: str | bytes) -> bytes:
    with connection.cursor() as cursor:
        cursor.execute(query, [value])
        row = cursor.fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("a pre-tenant lookup returned no blob")
    return bytes(row[0])


def lookup_login(email: str) -> bytes:
    return _call("SELECT guard.auth_lookup_login(%s)", normalise_email(email))


def lookup_credential(credential_id: bytes) -> CredentialOwner | None:
    """The user and agency sealed for a passkey's credential id, or None for an unknown or retired
    id (its decoy) and for a blob moved from another row (its AAD names the id). Opening tries
    every `login_blob_key` version either way (`blob._open`), so the caller cannot tell a decoy
    from a real blob by the work done here. The caller (M3g-1d) must still require the owner to
    be the pending session's user and agency."""
    found = _call("SELECT guard.auth_lookup_credential(%s)", credential_id)
    opened = open_credential(found, credential_id)
    return None if opened is None else CredentialOwner(*opened)
