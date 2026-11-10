# RLS for accounts.0011's `auth_stepup` (spec §4.2; plan M3 §3 M3h, design M3h-1), through
# tenancy.template.tenant_table(): FK to agency, the composite FK to app_user, ENABLE + FORCE, the
# policies and skiw_app's grant. SELECT and INSERT only: the evidence is append-only (TEN-03).
# Runs as skiw_migrator.
#
# The composite FK (agency_id, factor_id) -> user_factor is added here, not by the template:
# it is ON DELETE SET NULL (factor_id), a column list (PostgreSQL 15+, the project runs 17) so
# agency_id, which is NOT NULL, is never touched. Removing a TOTP (M3h-6) then works even when a
# step-up was made with it. The referential action runs as the table owner, so skiw_app still has
# no UPDATE grant; the cleared row no longer verifies, because factor_id is inside evidence_mac.

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
                " ON DELETE SET NULL (factor_id)"
            ),
            reverse_sql="ALTER TABLE auth_stepup DROP CONSTRAINT auth_stepup_factor_id_fk",
        ),
    ]
