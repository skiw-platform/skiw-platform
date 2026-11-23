"""`permission`, `role` and `role_permission` (slice spec §4, Decisions 1, 4; main spec §4.1 v1.23).
Models for the schema only: skiw_app holds SELECT and nothing else (M4r-1a); the write grants, the
roles lock, the system-role guards and the audit triggers come in M4r-1c to M4r-1g.

`permission` is global (spec §4.1 list) with the composite primary key (code, scope); accounts.0019
fills it with the catalogue pairs. `role` and `role_permission` are tenant tables (accounts.0018):
`role_permission` has the composite FK (agency_id, role_id) -> role ON DELETE RESTRICT and the plain
FK (permission_code, scope) -> permission, so the database refuses an unknown code or a scope the
code does not allow. Both FKs are SQL only: Django models no FK to a composite key."""

import uuid

from django.db import models
from django.db.models.functions import Length, Lower, Now
from django.db.models.lookups import Range

from accounts.access.catalogue import SCOPES
from tenancy.models import TenantModel

NAME_LENGTH = (1, 64)
# No C0 or C1 control character (Unicode Cc). Postgres regex escapes, not Python ones.
NAME_NO_CONTROL = r"^[^\x01-\x1f\x7f-\x9f]*$"


class Permission(models.Model):
    pk = models.CompositePrimaryKey("code", "scope")
    code = models.TextField()
    scope = models.TextField()

    class Meta:
        db_table = "permission"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(scope__in=SCOPES), name="permission_scope_known"
            ),
        )

    def __str__(self) -> str:
        return f"{self.code} {self.scope}"


class Role(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    is_system = models.BooleanField(db_default=False)
    created_at = models.DateTimeField(db_default=Now())

    class Meta(TenantModel.Meta):
        db_table = "role"
        constraints = (
            *TenantModel.Meta.constraints,
            # uq(agency_id, lower(name)); the expression first, because django-migration-linter
            # 6.0 misreads the table name of an index whose expression is not the first column.
            models.UniqueConstraint(Lower("name"), "agency_id", name="role_agency_name_uq"),
            models.UniqueConstraint(
                fields=["agency_id"],
                condition=models.Q(is_system=True),
                name="role_one_system_per_agency",
            ),
            models.CheckConstraint(
                condition=Range(Length("name"), NAME_LENGTH), name="role_name_length"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=NAME_NO_CONTROL), name="role_name_no_control"
            ),
        )

    def __str__(self) -> str:
        return "role row"  # names are admin-typed text, kept out of reprs and logs


class RolePermission(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # Composite FK (agency_id, role_id) -> role ON DELETE RESTRICT (accounts.0018).
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, db_constraint=False, db_index=False, related_name="+"
    )
    permission_code = models.TextField()
    scope = models.TextField()
    created_at = models.DateTimeField(db_default=Now())

    class Meta(TenantModel.Meta):
        db_table = "role_permission"
        constraints = (
            *TenantModel.Meta.constraints,
            models.UniqueConstraint(
                fields=["agency_id", "role", "permission_code", "scope"],
                name="role_permission_tick_uq",
            ),
        )

    def __str__(self) -> str:
        return "role_permission row"
