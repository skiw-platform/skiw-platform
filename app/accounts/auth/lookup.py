"""The pre-tenant login lookup (spec §4.1 "Pre-tenant lookups", Flow 5.1 (0); plan M3 §3 M3e).
The only caller of `guard.auth_lookup_login` (Semgrep `auth-lookup-accounts-auth-only`, TEN-10,
TEN-12). It returns one opaque blob for any email, known or not: a real `login_blob_ct` opens with
`blob.open_login`, a decoy never does. Each call commits one `security_event` (the function's own
insert), so run it outside `with_agency()`: no tenant is known yet."""

from django.db import connection

from accounts.auth.blob import normalise_email


def lookup_login(email: str) -> bytes:
    with connection.cursor() as cursor:
        cursor.execute("SELECT guard.auth_lookup_login(%s)", [normalise_email(email)])
        row = cursor.fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("guard.auth_lookup_login returned no blob")
    return bytes(row[0])
