from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TenancyConfig(AppConfig):
    name = "tenancy"

    def ready(self) -> None:
        # Imported here: tenancy.keys reaches the migration recorder, which needs the registry.
        from tenancy.keys import write_guard_keys_after_migrate

        # Sender tenancy only: one write per `migrate` run, not one per app (plan M4c-3).
        post_migrate.connect(
            write_guard_keys_after_migrate, sender=self, dispatch_uid="tenancy.write_guard_keys"
        )
