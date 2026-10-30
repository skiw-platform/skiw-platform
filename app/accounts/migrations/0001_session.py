# The session table (spec §4.1 `django_session`, D6) and skiw_app's privileges on it. Runs as
# skiw_migrator, which owns it (TEN-01/02). DELETE: revocation, flush and cycle_key delete rows
# (D6 "Revocation is a row delete"). No TRUNCATE, no column grants, no default privileges exist.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Session",
            fields=[
                ("session_data", models.TextField(verbose_name="session data")),
                ("expire_date", models.DateTimeField(db_index=True, verbose_name="expire date")),
                (
                    "session_key",
                    models.CharField(
                        max_length=64, primary_key=True, serialize=False, verbose_name="session key"
                    ),
                ),
            ],
            options={
                "verbose_name": "session",
                "verbose_name_plural": "sessions",
                "db_table": "django_session",
                "abstract": False,
            },
        ),
        migrations.RunSQL(
            sql="GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE django_session TO skiw_app",
            reverse_sql=(
                "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE django_session FROM skiw_app"
            ),
        ),
    ]
