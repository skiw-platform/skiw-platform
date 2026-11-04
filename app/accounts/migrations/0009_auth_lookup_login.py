# guard.auth_lookup_login (spec §4.1 "Pre-tenant lookups", Flow 5.1 (0); plan M3 §3 M3e, split
# M3e-1b): the one way to find a login before the tenant is known. A SECURITY DEFINER function
# owned by skiw_auth_lookup (BYPASSRLS, NOLOGIN), made through `as_owner`, that returns exactly one
# bytea: the row's `login_blob_ct`, or for an unknown email or a user with no password yet a decoy
# of the same 220 bytes. The decoy is HMAC-SHA-256 in counter mode over the lower-cased email (the
# equality `citext` uses) under the OLDEST `guard.lookup_decoy_key` version, so adding a version
# changes no decoy (docs/DECISIONS.md "M3e-1b"). Every call writes one `security_event` with no HMAC
# and no detail, so the row tells nobody whether the email was known. With `search_path =
# pg_catalog, pg_temp` every object is schema-qualified, the citext equality included: an
# unqualified `=` would cast to text and compare case-sensitively. Each call works out the decoy
# before it looks, so a known and an unknown email do the same work; no key is a SQL error for
# both. The owner reads only `email` and `login_blob_ct` of `app_user` (a column grant).
# Each statement is one line (the linter reads sqlmigrate output line by line) with no `%`.
from django.db import migrations

from tenancy.ddl import as_owner

FUNCTION = "guard.auth_lookup_login(public.citext)"
DECOY_LENGTH = 220  # accounts.user_model.LOGIN_BLOB_LENGTH; a test pins the two together
BLOCKS = 7  # 7 x 32 bytes of HMAC-SHA-256 >= DECOY_LENGTH
BODY = " ".join(
    [
        "DECLARE found bytea; secret bytea; decoy bytea := ''::bytea; block integer;",
        "BEGIN",
        "SELECT k.key INTO secret FROM guard.lookup_decoy_key k ORDER BY k.version LIMIT 1;",
        "IF secret IS NULL THEN RAISE EXCEPTION 'guard.auth_lookup_login: no lookup_decoy_key';",
        "END IF;",
        f"FOR block IN 1..{BLOCKS} LOOP",
        "decoy := decoy || guard.hmac(pg_catalog.convert_to('skiw-decoy-login-v1', 'UTF8')",
        "|| pg_catalog.int4send(block)",
        "|| pg_catalog.convert_to(pg_catalog.lower(address::pg_catalog.text), 'UTF8'),",
        "secret, 'sha256');",
        "END LOOP;",
        "SELECT u.login_blob_ct INTO found FROM public.app_user u",
        "WHERE u.email OPERATOR(public.=) address;",
        "INSERT INTO public.security_event (id, at, kind, details_json) VALUES",
        "(pg_catalog.gen_random_uuid(), pg_catalog.statement_timestamp(), 'login.lookup',",
        "'{}'::pg_catalog.jsonb);",
        f"IF found IS NULL THEN RETURN pg_catalog.substr(decoy, 1, {DECOY_LENGTH}); END IF;",
        "RETURN found;",
        "END",
    ]
)
CREATE = (
    "CREATE FUNCTION guard.auth_lookup_login(address public.citext) RETURNS bytea"
    " LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path = pg_catalog, pg_temp"
    f" AS $fn${BODY}$fn$"
)
COLUMNS = "GRANT SELECT (email, login_blob_ct) ON TABLE app_user TO skiw_auth_lookup"


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_blob_lengths_without_header"),
        ("tenancy", "0003_current_agency"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[COLUMNS],
            reverse_sql=[
                "REVOKE SELECT (email, login_blob_ct) ON TABLE app_user FROM skiw_auth_lookup"
            ],
        ),
        as_owner(
            "skiw_auth_lookup",
            [
                CREATE,
                f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC",
                f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO skiw_app",
            ],
            [f"DROP FUNCTION {FUNCTION}"],
        ),
    ]
