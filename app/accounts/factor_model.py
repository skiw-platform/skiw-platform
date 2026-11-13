"""`user_factor` (spec §4.1; plan M3 §3 M3d): a user's passkeys, TOTP secret and recovery codes.
Secret material is encrypted or keyed (C3) by the PRs that write it (M3f, M3g). `credential_id`
is unique across agencies: the second factor's credential is resolved before the tenant is known
(guard.auth_lookup_credential, M3g).

`secret_ct` has one length per kind (M3f-3a), and a TOTP or recovery row must have one: a TOTP
secret is the 48-byte sealed blob (accounts.auth.blob.seal_factor_secret); a recovery row is the
`tenant_source_key` version that signed it, 4 bytes big-endian, then its 32-byte HMAC-SHA-256
(accounts.auth.recovery). Passkey rows are left to M3g.

A factor a step-up names is never deleted (`auth_stepup.factor_id` FK, NO ACTION; DECISIONS
M3h-1): replacing one sets `retired_at` and clears its secret material (M3h-6). Kind-agnostic, so
M3g retires a passkey the same way. A retired row holds no `secret_ct`, `public_key` or
`lookup_blob_ct` (`user_factor_retired_no_secret`), so it cannot verify anything even for code
that ignored the column; a recovery row is deleted, never retired (its length rule forbids NULL).

Passkey rows (M3g-1b, accounts.0015): a passkey has a credential id of 1 to 1 023 bytes (the
bound `accounts.auth.passkey` enforces on `rawId`), no `secret_ct`, and a count that fits the
WebAuthn 32-bit `signCount`; in use it has its public key and sealed lookup blob, retired it keeps
only the credential id, so the global unique key still refuses that id at registration (M3g-1c).
`last_challenge_at` is the issue time of the challenge the last accepted assertion answered
(M3g-1d compares it in the same conditional update as `sign_count`). No other kind holds a
passkey column."""

import uuid

from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual

from accounts.auth.blob import CREDENTIAL_SIZE, FACTOR_SECRET_SIZE, OVERHEAD
from accounts.user_model import AppUser
from tenancy.models import TenantModel

KINDS = ("passkey", "totp", "recovery")
LOOKUP_BLOB_LENGTH = OVERHEAD + CREDENTIAL_SIZE  # 60, the fixed sealed length
TOTP_SECRET_CT_LENGTH = OVERHEAD + FACTOR_SECRET_SIZE  # 48
# tenant_source_key versions run to 999999 (config.env.versioned_keys): more than 1 or 2 bytes hold
RECOVERY_VERSION_BYTES = 4
RECOVERY_SECRET_CT_LENGTH = RECOVERY_VERSION_BYTES + 32  # version || HMAC-SHA-256: 36
CREDENTIAL_ID_MAX = 1023  # accounts.auth.passkey.MAX_CREDENTIAL_ID; a test pins the two together
SIGN_COUNT_MAX = 2**32 - 1  # WebAuthn signCount is an unsigned 32-bit integer
PASSKEY = models.Q(kind="passkey")


def _secret_ct_length(kind: str, length: int, *, retirable: bool) -> models.CheckConstraint:
    """A `kind` row has a `secret_ct` of exactly `length` bytes, unless `retirable` and retired;
    other kinds are not checked."""
    exempt = ~models.Q(kind=kind)
    if retirable:
        exempt |= models.Q(retired_at__isnull=False)
    return models.CheckConstraint(
        condition=exempt | models.Q(Exact(Length("secret_ct"), length), secret_ct__isnull=False),
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
    retired_at = models.DateTimeField(null=True)  # set once, by factor_change.remove (M3h-6)
    last_challenge_at = models.DateTimeField(null=True)  # passkeys only (M3g-1d)

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
            _secret_ct_length("totp", TOTP_SECRET_CT_LENGTH, retirable=True),
            _secret_ct_length("recovery", RECOVERY_SECRET_CT_LENGTH, retirable=False),
            models.CheckConstraint(
                condition=models.Q(retired_at__isnull=True)
                | models.Q(
                    secret_ct__isnull=True, public_key__isnull=True, lookup_blob_ct__isnull=True
                ),
                name="user_factor_retired_no_secret",
            ),
            models.CheckConstraint(
                condition=~PASSKEY
                | models.Q(
                    GreaterThanOrEqual(Length("credential_id"), 1),
                    LessThanOrEqual(Length("credential_id"), CREDENTIAL_ID_MAX),
                    credential_id__isnull=False,
                    secret_ct__isnull=True,
                    sign_count__lte=SIGN_COUNT_MAX,
                ),
                name="user_factor_passkey_shape",
            ),
            models.CheckConstraint(
                condition=~PASSKEY
                | models.Q(retired_at__isnull=False)
                | models.Q(public_key__isnull=False, lookup_blob_ct__isnull=False),
                name="user_factor_passkey_in_use",
            ),
            models.CheckConstraint(
                condition=PASSKEY
                | models.Q(
                    credential_id__isnull=True,
                    public_key__isnull=True,
                    lookup_blob_ct__isnull=True,
                    last_challenge_at__isnull=True,
                ),
                name="user_factor_passkey_only_columns",
            ),
        )

    def __str__(self) -> str:
        return "user_factor row"  # no key material in reprs or logs (UNI-09)
