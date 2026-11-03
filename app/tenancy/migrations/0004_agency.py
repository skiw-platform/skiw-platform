# The tenant root `agency` (spec §4.1, §4.2 schema check (2); plan M4c-5). Created by the migrator,
# which owns it, so the migrate-time seed (tenancy.seed) can lift FORCE inside its own transaction.
# RLS: ENABLE + FORCE, the restrictive tenant policy on `id` and one permissive SELECT policy with
# the same predicate (spec §4.2 "uses the same pattern on `id`, SELECT only"); skiw_app may only
# SELECT. Writes outside the seed wait for ADMIN_TX_HELPER (M5). Each statement is one line (the
# linter reads sqlmigrate output line by line) with no `%`.
from django.db import migrations, models

PREDICATE = "id = (SELECT guard.current_agency())"
POLICIES: tuple[str, ...] = (
    "ALTER TABLE agency ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE agency FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY agency_tenant ON agency AS RESTRICTIVE FOR ALL TO skiw_app USING ({PREDICATE})"
    f" WITH CHECK ({PREDICATE})",
    f"CREATE POLICY agency_sel ON agency FOR SELECT TO skiw_app USING ({PREDICATE})",
    "GRANT SELECT ON agency TO skiw_app",
)
REVERSE: tuple[str, ...] = (
    "REVOKE ALL ON agency FROM skiw_app",
    "DROP POLICY agency_sel ON agency",
    "DROP POLICY agency_tenant ON agency",
    "ALTER TABLE agency NO FORCE ROW LEVEL SECURITY",
    "ALTER TABLE agency DISABLE ROW LEVEL SECURITY",
)


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0003_current_agency"),
    ]

    operations = [
        migrations.CreateModel(
            name="Agency",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("timezone", models.CharField(db_default="Asia/Kuala_Lumpur", max_length=64)),
                ("data_region", models.CharField(db_default="MY", max_length=8)),
            ],
            options={
                "db_table": "agency",
            },
        ),
        migrations.RunSQL(sql=POLICIES, reverse_sql=REVERSE),
    ]
