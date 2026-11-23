# The 31 catalogue pairs of slice spec §6.1 v2.5 (main spec §6 v1.23) into `permission` (Decision 4;
# plan row M4r-1a). Runs as skiw_migrator, which owns the table (no RLS on this global table).
# The pairs are frozen here, not read from accounts.access.catalogue at run time, so this migration
# means the same thing on every database whatever the catalogue becomes; a catalogue change needs
# its own migration, and test_catalogue_migration_seeds_the_catalogue plus the live equality test
# fail until it exists. The reverse keeps the rows (a tick may name them; accounts.0017's reverse
# drops the table), and ON CONFLICT DO NOTHING makes a re-apply after it insert nothing twice.

from django.db import migrations

PAIRS = (
    ("client.view", ("own", "team", "agency")),
    ("client.edit", ("own", "team", "agency")),
    ("outbox.draft", ("own", "team", "agency")),
    ("outbox.approve", ("own", "team", "agency")),
    ("drive.file", ("own", "team", "agency")),
    ("connector.connect", ("own",)),
    ("bridge.run", ("own",)),
    ("ai.chat", ("own",)),
    ("settings.manage", ("agency",)),
    ("staff.manage", ("agency",)),
    ("staff.view", ("team", "agency")),
    ("audit.view", ("own", "team", "agency")),
    ("data.export", ("own", "team", "agency")),
    ("device.revoke", ("own", "agency")),
    ("jobs.admin", ("agency",)),
)
ROWS = ", ".join(f"('{code}', '{scope}')" for code, scopes in PAIRS for scope in scopes)
INSERT = f"INSERT INTO permission (code, scope) VALUES {ROWS} ON CONFLICT DO NOTHING"  # noqa: S608 (constants above)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_permission_role_rls"),
    ]

    operations = [
        migrations.RunSQL(
            sql=INSERT,
            reverse_sql=migrations.RunSQL.noop,  # the rows stay (above)
        ),
    ]
