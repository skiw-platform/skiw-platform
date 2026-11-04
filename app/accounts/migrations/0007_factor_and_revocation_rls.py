# RLS for accounts.0006's tables (spec §4.2; plan M3 §3 M3d, split M3d-1b), through
# tenancy.template.tenant_table(): FK to agency, composite FKs to app_user, ENABLE + FORCE, the
# policies and skiw_app's grant. Runs as skiw_migrator. user_factor: DELETE (factor removal,
# recovery-code use, plan M3d); session_revocation: SELECT, INSERT only (append-only, TEN-03).

from django.db import migrations

from tenancy.template import tenant_table


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_factor_and_revocation"),
    ]

    operations = [
        *tenant_table(
            "user_factor",
            commands={"SELECT", "INSERT", "UPDATE", "DELETE"},
            composite_fks=[("user_id", "app_user")],
        ),
        *tenant_table(
            "session_revocation",
            commands={"SELECT", "INSERT"},
            composite_fks=[("user_id", "app_user")],
        ),
    ]
