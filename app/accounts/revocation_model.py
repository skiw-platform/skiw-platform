"""`session_revocation` (plan M3 §3 M3d; carry-over (b), owner PR 74 Q2 = A): an append-only
marker (TEN-03: skiw_app may SELECT and INSERT only). A row with `session_key_hash` revokes that
one session; a row without it revokes every session of the user that signed in at or before
`revoked_at` (AUTH-07). A deleted session row put back by SQL stays revoked, because the marker
cannot be removed. accounts.auth.revoke writes and checks it."""

import uuid

from django.db import models
from django.db.models.functions import Now

from accounts.user_model import AppUser
from tenancy.models import TenantModel


class SessionRevocation(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # The composite FK (agency_id, user_id) -> app_user is added by tenant_table() (accounts.0007).
    user = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_constraint=False, db_index=False, related_name="+"
    )
    # NULL is meaningful: a user-wide marker. Else accounts.session.stored_key of one session.
    session_key_hash = models.CharField(max_length=64, null=True)  # noqa: DJ001
    revoked_at = models.DateTimeField(db_default=Now())

    class Meta(TenantModel.Meta):
        db_table = "session_revocation"
        constraints = (
            *TenantModel.Meta.constraints,
            models.CheckConstraint(
                condition=models.Q(session_key_hash__regex=r"^[0-9a-f]{64}$"),
                name="session_revocation_key_hash_shape",
            ),
        )
        indexes = (
            models.Index(fields=["agency_id", "session_key_hash"], name="session_revocation_key"),
            models.Index(
                fields=["agency_id", "user", "revoked_at"], name="session_revocation_user"
            ),
        )

    def __str__(self) -> str:
        return "session_revocation row"
