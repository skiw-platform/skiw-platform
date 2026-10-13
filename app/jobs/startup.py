from concurrent.futures import ThreadPoolExecutor

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor

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


def database_ready() -> bool:
    """`/readyz` (spec §8.3): the database answers as skiw_app and no migration is unapplied."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            row = cursor.fetchone()
        return row == (APP_ROLE,) and not pending_migrations()
    except (DatabaseError, ImproperlyConfigured):
        return False
