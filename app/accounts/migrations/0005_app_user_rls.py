# RLS for accounts.0004's `app_user` (spec §4.2; plan M3 §3 M3d, split M3d-1a), through
# tenancy.template.tenant_table(): FK to agency, ENABLE + FORCE, the policies and skiw_app's
# grant. Runs as skiw_migrator. No DELETE: an account is disabled, not removed.

from django.db import migrations

from tenancy.template import tenant_table


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_app_user"),
    ]

    operations = [
        *tenant_table("app_user", commands={"SELECT", "INSERT", "UPDATE"}),
    ]
