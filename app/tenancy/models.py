"""The tenant root (spec §4.1 `agency`; plan M4c-5) and the abstract tenant base (plan M4c-6a).
`agency`'s RLS policies and grant are in tenancy/0004; outside tests only the migrate-time seed
(tenancy.seed) writes it. Django sends `post_migrate` only for apps that have a models module, and
tenancy.keys and tenancy.seed need it."""

from django.db import models


class Agency(models.Model):
    # No default: the id comes from host config (SKIW_DEPLOYMENT_AGENCY_ID), never from the app.
    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64, db_default="Asia/Kuala_Lumpur")
    data_region = models.CharField(max_length=8, db_default="MY")

    class Meta:
        db_table = "agency"

    def __str__(self) -> str:
        return self.name


class TenantModel(models.Model):
    """Base of every tenant-owned model (spec §4 "Tenant key", "Tenant-consistent references").
    `unique (agency_id, id)` is a model constraint, so `makemigrations --check` fails if a subclass
    loses it. A subclass with its own Meta must inherit `TenantModel.Meta` (or repeat the
    constraint). FKs to tenant tables use `db_constraint=False`; the migration adds the composite
    FKs with `tenancy.template.tenant_table()`."""

    agency_id = models.UUIDField()

    class Meta:
        abstract = True
        constraints = (
            models.UniqueConstraint(
                fields=["agency_id", "id"], name="%(app_label)s_%(class)s_agency_id_id_uq"
            ),
        )
