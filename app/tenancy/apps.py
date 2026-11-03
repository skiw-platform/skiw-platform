from typing import Any

from django.apps import AppConfig
from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import post_migrate


def after_migrate(sender: AppConfig, using: str = DEFAULT_DB_ALIAS, **kwargs: Any) -> None:
    """The guard key writes (plan M4c-3), then the agency seed (M4c-5), each in its own
    transaction, in this order: the seed's own checks do not need the keys, but a failed key
    write stops `migrate` before any agency row is written."""
    # Imported here: both reach the migration recorder, which needs the registry.
    from tenancy.keys import write_guard_keys
    from tenancy.seed import seed_after_migrate

    write_guard_keys(using)
    seed_after_migrate(using)


class TenancyConfig(AppConfig):
    name = "tenancy"

    def ready(self) -> None:
        # Sender tenancy only: one run per `migrate`, not one per app (plan M4c-3).
        post_migrate.connect(after_migrate, sender=self, dispatch_uid="tenancy.after_migrate")
