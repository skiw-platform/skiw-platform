from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor

from tenancy.binding import with_agency

APP_ROLE = "skiw_app"


def require_migrated() -> None:
    """Fail closed when any migration is unapplied (spec D16). Runs as skiw_app, which may only
    read django_migrations (spec §4.1): nothing here changes the schema."""
    # The ASGI server imports the app inside a running event loop, where Django refuses
    # synchronous database calls. A short-lived thread has no loop and its own connection.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(pending_migrations).result()
    if pending:
        raise ImproperlyConfigured(f"unapplied migrations, refusing to start: {', '.join(pending)}")


def pending_migrations() -> list[str]:
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError as exc:
        raise ImproperlyConfigured(
            "cannot verify migrations (are they applied, and can skiw_app read django_migrations?)"
        ) from exc
    finally:
        connection.close()
    return [f"{migration.app_label}.{migration.name}" for migration, _ in plan]


def tenant_bound() -> bool:
    """`with_agency(<deployment agency>)` binds: the verifier gives that agency back and its row is
    visible (plan M4c-5). A tenant_token_key that differs from the stored one, or a missing seed,
    then fails the deploy check (and the deploy switches back) instead of every read silently
    returning no rows."""
    agency_id, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    with with_agency(agency_id), connection.cursor() as cursor:
        cursor.execute(
            "SELECT guard.current_agency(), (SELECT count(*) FROM agency WHERE id = %s)",
            [agency_id],
        )
        row: tuple[object, ...] | None = cursor.fetchone()
    return row == (agency_id, 1)


def database_ready() -> bool:
    """`/readyz` (spec §8.3): the database answers as skiw_app, no migration is unapplied, and
    the deployment agency binds."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            row = cursor.fetchone()
        return row == (APP_ROLE,) and not pending_migrations() and tenant_bound()
    except (DatabaseError, ImproperlyConfigured, RuntimeError):
        # RuntimeError: config.env's missing or invalid key errors.
        return False
