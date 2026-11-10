# RLS for accounts.0011's `auth_stepup` (spec §4.2; plan M3 §3 M3h, design M3h-1), through
# tenancy.template.tenant_table(): FK to agency, the composite FK to app_user, ENABLE + FORCE, the
# policies and skiw_app's grant. SELECT and INSERT only: the evidence is append-only (TEN-03).
# Runs as skiw_migrator.
#
# The composite FK (agency_id, factor_id) -> user_factor is added here, not by the template, with
# the default NO ACTION: a factor that a step-up names cannot be deleted, so the evidence keeps
# verifying and keeps saying which factor proved it, for the later consumers (the M9 executor, the
# M16 drive_writer) that check it outside the session. Factors are retired, not deleted (M3h-6
# TOTP, M3g passkeys). Review R1 on PR 136 replaced an earlier ON DELETE SET NULL (factor_id).

from django.db import migrations

from tenancy.template import tenant_table


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_auth_stepup"),
    ]

    operations = [
        *tenant_table(
            "auth_stepup",
            commands={"SELECT", "INSERT"},
            composite_fks=[("user_id", "app_user")],
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE auth_stepup ADD CONSTRAINT auth_stepup_factor_id_fk"
                " FOREIGN KEY (agency_id, factor_id) REFERENCES user_factor(agency_id, id)"
            ),
            reverse_sql="ALTER TABLE auth_stepup DROP CONSTRAINT auth_stepup_factor_id_fk",
        ),
    ]
