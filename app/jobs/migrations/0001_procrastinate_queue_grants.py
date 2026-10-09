# skiw_app's privileges on the Procrastinate queue objects: exactly spec §4.1
# "Procrastinate queue grants". Runs as skiw_migrator, which owns the objects (TEN-01/02).
from django.db import migrations

APP_ROLE = "skiw_app"
TABLES = {
    "procrastinate_jobs": "SELECT, INSERT, UPDATE",
    "procrastinate_events": "INSERT",
    "procrastinate_periodic_defers": "SELECT, INSERT, UPDATE, DELETE",
    "procrastinate_workers": "SELECT, INSERT, UPDATE, DELETE",
}
SEQUENCES = (
    "procrastinate_jobs_id_seq, procrastinate_events_id_seq, procrastinate_periodic_defers_id_seq"
)
FUNCTIONS = (
    "procrastinate_defer_jobs_v1, procrastinate_defer_periodic_job_v2,"
    " procrastinate_fetch_job_v2, procrastinate_finish_job_v1, procrastinate_retry_job_v2,"
    " procrastinate_register_worker_v1, procrastinate_unregister_worker_v1,"
    " procrastinate_update_heartbeat_v1, procrastinate_prune_stalled_workers_v1"
)


def public_execute(statement: str) -> str:
    """Apply `statement` (with %s for the signature) to every procrastinate_* function in the
    queue schema; PostgreSQL gives PUBLIC EXECUTE on new functions by default."""
    # S608: only this module's constant statements are interpolated, never input.
    return f"""
DO $$
DECLARE fn regprocedure;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure FROM pg_proc p
        WHERE starts_with(p.proname, 'procrastinate_')
          AND p.pronamespace = (SELECT relnamespace FROM pg_class
                                WHERE oid = 'procrastinate_jobs'::regclass)
    LOOP
        EXECUTE format('{statement}', fn);
    END LOOP;
END $$"""  # noqa: S608


def workers_identity_sequence(statement: str) -> str:
    """Apply `statement` (with %s for the name) to the identity sequence of
    procrastinate_workers.id, whose name PostgreSQL chooses."""
    return f"""
DO $$
BEGIN
    EXECUTE format('{statement}', pg_get_serial_sequence('procrastinate_workers', 'id'));
END $$"""


class Migration(migrations.Migration):
    dependencies = [("procrastinate", "0041_post_retry_failed_job")]

    operations = [
        migrations.RunSQL(
            sql=[
                public_execute("REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC"),
                *(f"GRANT {privs} ON TABLE {t} TO {APP_ROLE}" for t, privs in TABLES.items()),
                f"GRANT USAGE ON SEQUENCE {SEQUENCES} TO {APP_ROLE}",
                workers_identity_sequence(f"GRANT USAGE ON SEQUENCE %s TO {APP_ROLE}"),
                f"GRANT EXECUTE ON FUNCTION {FUNCTIONS} TO {APP_ROLE}",
                # Startup gate (D16, §4.1): skiw_app reads, never writes, the migration record.
                f"GRANT SELECT ON TABLE django_migrations TO {APP_ROLE}",
            ],
            reverse_sql=[
                f"REVOKE SELECT ON TABLE django_migrations FROM {APP_ROLE}",  # noqa: S608
                f"REVOKE EXECUTE ON FUNCTION {FUNCTIONS} FROM {APP_ROLE}",
                workers_identity_sequence(f"REVOKE USAGE ON SEQUENCE %s FROM {APP_ROLE}"),
                f"REVOKE USAGE ON SEQUENCE {SEQUENCES} FROM {APP_ROLE}",
                *(f"REVOKE {privs} ON TABLE {t} FROM {APP_ROLE}" for t, privs in TABLES.items()),
                public_execute("GRANT EXECUTE ON FUNCTION %s TO PUBLIC"),
            ],
        )
    ]
