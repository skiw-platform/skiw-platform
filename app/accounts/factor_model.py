"""`user_factor` (spec §4.1; plan M3 §3 M3d): a user's passkeys, TOTP secret and recovery codes.
Secret material is encrypted or keyed (C3) by the PRs that write it (M3f, M3g). `credential_id`
is unique across agencies: the second factor's credential is resolved before the tenant is known
(guard.auth_lookup_credential, M3g).

`secret_ct` has one length per kind (M3f-3a), and a TOTP or recovery row must have one: a TOTP
secret is the 48-byte sealed blob (accounts.auth.blob.seal_factor_secret); a recovery row is the
`tenant_source_key` version that signed it, 4 bytes big-endian, then its 32-byte HMAC-SHA-256
(accounts.auth.recovery). Passkey rows are left to M3g."""

import uuid

from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import Exact

from accounts.auth.blob import CREDENTIAL_SIZE, FACTOR_SECRET_SIZE, OVERHEAD
from accounts.user_model import AppUser
from tenancy.models import TenantModel

KINDS = ("passkey", "totp", "recovery")
LOOKUP_BLOB_LENGTH = OVERHEAD + CREDENTIAL_SIZE  # 60, the fixed sealed length
TOTP_SECRET_CT_LENGTH = OVERHEAD + FACTOR_SECRET_SIZE  # 48
# tenant_source_key versions run to 999999 (config.env.versioned_keys): more than 1 or 2 bytes hold
RECOVERY_VERSION_BYTES = 4
RECOVERY_SECRET_CT_LENGTH = RECOVERY_VERSION_BYTES + 32  # version || HMAC-SHA-256: 36


def _secret_ct_length(kind: str, length: int) -> models.CheckConstraint:
    """A `kind` row has a `secret_ct` of exactly `length` bytes; other kinds are not checked."""
    return models.CheckConstraint(
        condition=~models.Q(kind=kind)
        | models.Q(Exact(Length("secret_ct"), length), secret_ct__isnull=False),
        name=f"user_factor_{kind}_secret_ct_length",
    )


class UserFactor(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # The composite FK (agency_id, user_id) -> app_user is added by tenant_table() (accounts.0007).
    user = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    kind = models.CharField(max_length=16)
    credential_id = models.BinaryField(null=True, unique=True)
    public_key = models.BinaryField(null=True)
    sign_count = models.BigIntegerField(db_default=0)
    secret_ct = models.BinaryField(null=True)
    lookup_blob_ct = models.BinaryField(null=True)

    class Meta(TenantModel.Meta):
        db_table = "user_factor"
        constraints = (
            *TenantModel.Meta.constraints,
            models.CheckConstraint(
                condition=models.Q(kind__in=KINDS), name="user_factor_kind_known"
            ),
            models.CheckConstraint(
                condition=models.Q(sign_count__gte=0), name="user_factor_sign_count_gte_0"
            ),
            models.CheckConstraint(
                condition=Exact(Length("lookup_blob_ct"), LOOKUP_BLOB_LENGTH),
                name="user_factor_lookup_blob_ct_length",
            ),
            _secret_ct_length("totp", TOTP_SECRET_CT_LENGTH),
            _secret_ct_length("recovery", RECOVERY_SECRET_CT_LENGTH),
        )

    def __str__(self) -> str:
        return "user_factor row"  # no key material in reprs or logs (UNI-09)
