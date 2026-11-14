# `user_factor.created_at` (plan M3 §3 M3g, split M3g-2s-2; docs/DECISIONS.md "M3g-2s-2"): when a
# factor was added, so the passkey list can tell two passkeys apart and keep its order. Expand
# only (UNI-15): a nullable column the previous code never reads or writes.
#   - Two statements, so existing rows stay NULL ("unknown"): one ADD COLUMN with the default
#     would stamp every existing row with the migration's time (PG 11+ stores it as the missing
#     value), a made-up creation time. skiw_migrator sees no tenant rows under FORCE RLS, so no
#     true backfill exists. New rows get the default, STATEMENT_TIMESTAMP() (what Django's Now()
#     compiles to, as `session_revocation.revoked_at`): the insert's own time.
#   - Grants: skiw_app's table-level grants (accounts.0007) cover the column; the lookup owner
#     skiw_auth_lookup keeps its three-column SELECT (accounts.0015) and gets nothing on it.
#   - Reversing keeps the column, its default and its values (only the Django state drops it), as
#     accounts.0014 and 0015 do: a reverse and re-apply must not lose the times. The re-apply finds
#     the column (IF NOT EXISTS) and sets the same default again. Runs as skiw_migrator.
import django.db.models.functions.datetime
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_passkey_lookup"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="userfactor",
                    name="created_at",
                    field=models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now(), null=True
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        'ALTER TABLE "user_factor" ADD COLUMN IF NOT EXISTS'
                        ' "created_at" timestamp with time zone NULL',
                        'ALTER TABLE "user_factor" ALTER COLUMN "created_at"'
                        " SET DEFAULT STATEMENT_TIMESTAMP()",
                    ],
                    reverse_sql=migrations.RunSQL.noop,  # the column stays (above)
                ),
            ],
        ),
    ]
