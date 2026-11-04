"""`app_user` (spec §4.1; plan M3 §3 M3d): tenant-owned, RLS through tenancy/template. No
password-hash column: the Argon2id hash lives only inside `login_blob_ct` (accounts.auth.blob).
`email` is unique across agencies, because login happens before the tenant is known."""

import uuid

from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models.functions import Length
from django.db.models.lookups import Exact

from accounts.auth.blob import LOGIN_SIZE, OVERHEAD
from tenancy.models import TenantModel

STATUSES = ("invited", "active", "disabled")
LOGIN_BLOB_LENGTH = OVERHEAD + LOGIN_SIZE  # 222, the fixed sealed length


class CIText(models.TextField):  # type: ignore[type-arg]
    """Postgres `citext` (accounts.0004 installs it): equal and unique regardless of case."""

    def db_type(self, connection: BaseDatabaseWrapper) -> str:
        return "citext"


class AppUser(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = CIText(unique=True)
    display_name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, db_default="invited")
    login_blob_ct = models.BinaryField(null=True)  # NULL until the user sets a password
    last_login_at = models.DateTimeField(null=True)

    class Meta(TenantModel.Meta):
        db_table = "app_user"
        constraints = (
            *TenantModel.Meta.constraints,
            models.CheckConstraint(
                condition=models.Q(status__in=STATUSES), name="app_user_status_known"
            ),
            models.CheckConstraint(
                condition=Exact(Length("login_blob_ct"), LOGIN_BLOB_LENGTH),
                name="app_user_login_blob_ct_length",
            ),
        )

    def __str__(self) -> str:
        return "app_user row"  # no email or name in reprs or logs (UNI-09)
