# Passkey rows and guard.auth_lookup_credential (spec §4.1 "Pre-tenant lookups", Flow 5.1; plan M3
# §3 M3g, split M3g-1b; docs/DECISIONS.md "M3g-1b"). Expand only (UNI-15): no passkey row exists
# in any environment and the previous release writes none, so the three passkey rules validate an
# empty set; TOTP and recovery rows already leave the passkey columns empty.
#   - `last_challenge_at`, nullable: the issue time of the challenge the last accepted assertion
#     answered (M3g-1d's conditional update, PR 154 R1 P2 #2). Reversing keeps the column and its
#     values (only the Django state drops it), as accounts.0014 does: a reverse and re-apply must
#     not clear the replay guard. The re-apply finds it (IF NOT EXISTS).
#   - The function, like guard.auth_lookup_login (accounts.0009): SECURITY DEFINER, owned by
#     skiw_auth_lookup through `as_owner`, `search_path = pg_catalog, pg_temp`, every object
#     schema-qualified, EXECUTE for skiw_app only. It returns exactly one bytea: the passkey's
#     `lookup_blob_ct`, or for an unknown or retired credential id a 60-byte decoy, HMAC-SHA-256 in
#     counter mode over the id under the OLDEST `guard.lookup_decoy_key` version. The decoy is
#     built before the lookup and every call writes the same `passkey.lookup` event, so known and
#     unknown ids do the same work; no key is a SQL error for both. The owner reads three columns
#     of `user_factor` (a column grant). Each statement is one line with no `%` (as 0009).
from django.db import migrations, models
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual

from tenancy.ddl import as_owner

FUNCTION = "guard.auth_lookup_credential(bytea)"
# Literals, so a later change of the model's constants cannot rewrite this migration; a test pins
# each to its accounts.factor_model constant (LOOKUP_BLOB_LENGTH and the two bounds).
DECOY_LENGTH = 60
CREDENTIAL_ID_MAX = 1023
SIGN_COUNT_MAX = 4294967295
BLOCKS = 2  # 2 x 32 bytes of HMAC-SHA-256 >= DECOY_LENGTH
COLUMNS = "SELECT (credential_id, lookup_blob_ct, retired_at) ON TABLE user_factor"
BODY = " ".join(
    [
        "DECLARE stored bytea; secret bytea; decoy bytea := ''::bytea; block integer;",
        "BEGIN",
        "SELECT k.key INTO secret FROM guard.lookup_decoy_key k ORDER BY k.version LIMIT 1;",
        "IF secret IS NULL THEN",
        "RAISE EXCEPTION 'guard.auth_lookup_credential: no lookup_decoy_key'; END IF;",
        f"FOR block IN 1..{BLOCKS} LOOP",
        "decoy := decoy || guard.hmac(pg_catalog.convert_to('skiw-decoy-credential-v1', 'UTF8')",
        "|| pg_catalog.int4send(block) || credential, secret, 'sha256');",
        "END LOOP;",
        "SELECT f.lookup_blob_ct INTO stored FROM public.user_factor f",
        "WHERE f.credential_id OPERATOR(pg_catalog.=) credential AND f.retired_at IS NULL;",
        "INSERT INTO public.security_event (id, at, kind, details_json) VALUES",
        "(pg_catalog.gen_random_uuid(), pg_catalog.statement_timestamp(), 'passkey.lookup',",
        "'{}'::pg_catalog.jsonb);",
        f"IF stored IS NULL THEN RETURN pg_catalog.substr(decoy, 1, {DECOY_LENGTH}); END IF;",
        "RETURN stored;",
        "END",
    ]
)
CREATE = (
    "CREATE FUNCTION guard.auth_lookup_credential(credential bytea) RETURNS bytea"
    " LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path = pg_catalog, pg_temp"
    f" AS $fn${BODY}$fn$"
)


def _constraint(name: str, condition: models.Q) -> migrations.AddConstraint:
    return migrations.AddConstraint(
        model_name="userfactor", constraint=models.CheckConstraint(condition=condition, name=name)
    )


PASSKEY = models.Q(kind="passkey")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_factor_retired"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="userfactor",
                    name="last_challenge_at",
                    field=models.DateTimeField(null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "user_factor" ADD COLUMN IF NOT EXISTS'
                    ' "last_challenge_at" timestamp with time zone NULL',
                    reverse_sql=migrations.RunSQL.noop,  # the column stays (above)
                ),
            ],
        ),
        _constraint(
            "user_factor_passkey_shape",
            ~PASSKEY
            | models.Q(
                GreaterThanOrEqual(Length("credential_id"), 1),
                LessThanOrEqual(Length("credential_id"), CREDENTIAL_ID_MAX),
                credential_id__isnull=False,
                secret_ct__isnull=True,
                sign_count__lte=SIGN_COUNT_MAX,
            ),
        ),
        _constraint(
            "user_factor_passkey_in_use",
            ~PASSKEY
            | models.Q(retired_at__isnull=False)
            | models.Q(public_key__isnull=False, lookup_blob_ct__isnull=False),
        ),
        _constraint(
            "user_factor_passkey_only_columns",
            PASSKEY
            | models.Q(
                credential_id__isnull=True,
                public_key__isnull=True,
                lookup_blob_ct__isnull=True,
                last_challenge_at__isnull=True,
            ),
        ),
        migrations.RunSQL(
            sql=[f"GRANT {COLUMNS} TO skiw_auth_lookup"],
            reverse_sql=[f"REVOKE {COLUMNS} FROM skiw_auth_lookup"],
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
