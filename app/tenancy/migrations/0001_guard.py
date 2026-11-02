# The `guard` schema and `pgcrypto` (spec §4.1, §4.2 "Tenant binding"; plan M4c-2a). Runs as
# skiw_migrator, which owns the schema (TEN-01). USAGE goes to the two NOLOGIN owners only;
# skiw_app gets USAGE with `guard.current_agency()` (M4c-4a), its first object here.
# Only RunSQL: migration_labels counts any other Operation class as a contract migration.
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    operations = [
        migrations.RunSQL(
            sql=[
                "CREATE SCHEMA guard",
                "GRANT USAGE ON SCHEMA guard TO skiw_tenant_guard, skiw_auth_lookup",
            ],
            reverse_sql=["DROP SCHEMA guard"],
        ),
        # Trusted extension: the migrator (database owner) may install it. hmac() for
        # guard.current_agency() (M4c-4a) and the decoy (M3e).
        migrations.RunSQL(
            sql=["CREATE EXTENSION pgcrypto WITH SCHEMA guard"],
            reverse_sql=["DROP EXTENSION pgcrypto"],
        ),
    ]
