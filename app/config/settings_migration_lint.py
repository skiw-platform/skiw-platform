# Used only by `make migrate` for the migration-linter gate (spec D16). The linter is a dev
# dependency that must be an installed app, so it never joins the runtime INSTALLED_APPS.
from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "django_migration_linter"]  # noqa: F405
