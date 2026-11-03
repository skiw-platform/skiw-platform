"""The tenant root (spec §4.1 `agency`; plan M4c-5). Its RLS policies and grant are in
tenancy/0004. Outside tests only the migrate-time seed (tenancy.seed) writes it. Django sends
`post_migrate` only for apps that have a models module, and tenancy.keys and tenancy.seed need
it."""

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
