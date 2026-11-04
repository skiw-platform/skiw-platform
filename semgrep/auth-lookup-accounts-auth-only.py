# Fixture for `semgrep --test semgrep/` (rule auth-lookup-accounts-auth-only).
from psycopg import sql
from psycopg.sql import Identifier


def banned(cursor, email, credential):
    # ruleid: auth-lookup-accounts-auth-only
    cursor.execute("SELECT guard.auth_lookup_login(%s)", [email])
    # ruleid: auth-lookup-accounts-auth-only
    cursor.execute("select\n  GUARD.AUTH_LOOKUP_LOGIN(%s)", [email])
    # ruleid: auth-lookup-accounts-auth-only
    cursor.execute("SELECT 1; SELECT * FROM guard.auth_lookup_credential(%s)", [credential])
    # ruleid: auth-lookup-accounts-auth-only
    query = sql.SQL("SELECT {}(%s)").format(sql.Identifier("guard", "auth_lookup_login"))
    cursor.execute(query, [email])
    # ruleid: auth-lookup-accounts-auth-only
    cursor.callproc("guard.auth_lookup_login", [email])
    # ruleid: auth-lookup-accounts-auth-only
    cursor.callproc("AUTH_LOOKUP_CREDENTIAL", [credential])
    # ruleid: auth-lookup-accounts-auth-only
    name = Identifier("guard", "auth_lookup_credential")
    return name


def allowed(cursor, email):
    """Mentions guard.auth_lookup_login, as a docstring may."""
    # ok: auth-lookup-accounts-auth-only
    cursor.execute("SELECT guard.current_agency()")
    # ok: auth-lookup-accounts-auth-only
    note = "the decoy guard.auth_lookup_login returns has the blob length"
    # ok: auth-lookup-accounts-auth-only
    cursor.callproc("guard.auth_lookup_logins", [email])
    return note
