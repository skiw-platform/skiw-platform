# INSERT on `security_event` for `skiw_auth_lookup` (plan M4c-2b; M3 plan §0): the NOLOGIN owner of
# `guard.auth_lookup_login` (M3e), a SECURITY DEFINER function that writes one event per call.
# INSERT only (TEN-03: append-only evidence, no SELECT, UPDATE, DELETE or TRUNCATE). It lives in
# `accounts`: Semgrep `auth-tables-accounts-only` flags the grant anywhere else.
# Only RunSQL: migration_labels counts any other Operation class as a contract migration.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_auth_throttle_security_event"),
    ]

    operations = [
        migrations.RunSQL(
            sql=["GRANT INSERT ON TABLE security_event TO skiw_auth_lookup"],
            reverse_sql=["REVOKE INSERT ON TABLE security_event FROM skiw_auth_lookup"],
        ),
    ]
