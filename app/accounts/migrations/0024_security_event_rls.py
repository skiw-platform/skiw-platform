# Agency isolation of security_event (slice spec Decision 33, owner Q6; plan row M4r-1c). Runs as
# skiw_migrator. P = agency_id IS NULL OR agency_id = (SELECT guard.current_agency()): skiw_app sees
# and inserts pre-tenant rows (NULL agency) in every context, and a change row only inside its own
# agency; with no token, pre-tenant rows only. No UPDATE or DELETE policy and no grant change
# (TEN-03; accounts.0002, 0003). FORCE binds the owner too: no policy names skiw_migrator, so it
# reads and writes nothing here without a transaction-local NO FORCE (the tenancy.seed pattern).
# skiw_auth_lookup (the guard.auth_lookup_* definers) and skiw_backup have BYPASSRLS
# (infra/host/db/roles.sql), so RLS does not apply to them.
# The schema check's named rule (tenancy.check) pins this exact set.

from django.db import migrations

P = "agency_id IS NULL OR agency_id = (SELECT guard.current_agency())"
TABLE = "security_event"


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0023_security_event_agency_index"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"ALTER TABLE {TABLE} ADD CONSTRAINT {TABLE}_agency_fk"
            " FOREIGN KEY (agency_id) REFERENCES agency(id)",
            reverse_sql=f"ALTER TABLE {TABLE} DROP CONSTRAINT {TABLE}_agency_fk",
        ),
        migrations.RunSQL(
            sql=[
                f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY",
                f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY",
                f"CREATE POLICY {TABLE}_tenant ON {TABLE} AS RESTRICTIVE FOR ALL TO skiw_app"
                f" USING ({P}) WITH CHECK ({P})",
                f"CREATE POLICY {TABLE}_sel ON {TABLE} FOR SELECT TO skiw_app USING ({P})",
                f"CREATE POLICY {TABLE}_ins ON {TABLE} FOR INSERT TO skiw_app WITH CHECK ({P})",
            ],
            reverse_sql=[
                f"DROP POLICY {TABLE}_ins ON {TABLE}",
                f"DROP POLICY {TABLE}_sel ON {TABLE}",
                f"DROP POLICY {TABLE}_tenant ON {TABLE}",
                f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY",
                f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY",
            ],
        ),
    ]
