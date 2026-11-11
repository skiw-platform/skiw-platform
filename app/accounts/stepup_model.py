"""`auth_stepup` (spec §4.1; plan M3 §3 M3h, design M3h-1): the evidence that a session's user
re-verified a factor just now, for one purpose. Append-only (TEN-03: skiw_app may SELECT and
INSERT only). `evidence_mac` is a 4-byte `tenant_source_key` version, then an HMAC-SHA-256 over
every other column (accounts.auth.stepup, M3h-2), so a row written by SQL authorises nothing.

`factor_id` is the factor that proved it, never NULL (`auth_stepup_factor_named`, accounts.0013).
Its foreign key is NO ACTION (accounts.0012): a factor that a step-up names cannot be deleted, so
the row keeps verifying and keeps saying which factor proved it, for consumers that check it later
and outside the session (the M9 executor, the M16 drive_writer). Factors are retired, not deleted
(M3h-6 TOTP, M3g passkeys). The model says PROTECT, so the ORM refuses first (ProtectedError)
instead of the database."""

import uuid

from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import Exact

from accounts.factor_model import RECOVERY_VERSION_BYTES, UserFactor
from accounts.user_model import AppUser
from tenancy.models import TenantModel

EVIDENCE_LENGTH = RECOVERY_VERSION_BYTES + 32  # key version || HMAC-SHA-256: 36
KEY_HASH = r"^[0-9a-f]{64}$"  # accounts.session.stored_key()
# Shape only: `outbox.approve`, `drive.write`, `export`, `role_change`, `factor.change`. The closed
# list lives in accounts.auth.stepup, so a new purpose needs no migration.
PURPOSE = r"^[a-z]+(_[a-z]+)*(\.[a-z]+(_[a-z]+)*)?$"


class AuthStepup(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # Composite FKs (agency_id, user_id) -> app_user (tenant_table()) and (agency_id, factor_id)
    # -> user_factor, NO ACTION (accounts.0012).
    user = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_constraint=False, db_index=False, related_name="+"
    )
    factor = models.ForeignKey(
        UserFactor,
        on_delete=models.PROTECT,
        null=True,
        db_constraint=False,
        db_index=False,
        related_name="+",
    )
    purpose = models.CharField(max_length=64)
    # No db_default: the MAC covers the value, so the app sets it and signs what it set.
    verified_at = models.DateTimeField()
    session_key_hash = models.CharField(max_length=64)
    evidence_mac = models.BinaryField()

    class Meta(TenantModel.Meta):
        db_table = "auth_stepup"
        constraints = (
            *TenantModel.Meta.constraints,
            models.CheckConstraint(
                condition=models.Q(session_key_hash__regex=KEY_HASH),
                name="auth_stepup_key_hash_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(purpose__regex=PURPOSE), name="auth_stepup_purpose_shape"
            ),
            models.CheckConstraint(
                condition=Exact(Length("evidence_mac"), EVIDENCE_LENGTH),
                name="auth_stepup_evidence_mac_length",
            ),
            # Every step-up names the factor that proved it (accounts.0013, DECISIONS M3h-2). A
            # CHECK, not NOT NULL, so the migration only adds (UNI-15), as accounts.0010 did.
            models.CheckConstraint(
                condition=models.Q(factor__isnull=False), name="auth_stepup_factor_named"
            ),
        )
        indexes = (
            models.Index(
                fields=["agency_id", "session_key_hash", "purpose", "verified_at"],
                name="auth_stepup_recent",
            ),
            # The foreign key's check on deleting a factor scans by (agency_id, factor_id).
            models.Index(fields=["agency_id", "factor"], name="auth_stepup_factor"),
        )

    def __str__(self) -> str:
        return "auth_stepup row"  # no session or MAC material in reprs or logs (UNI-09)
