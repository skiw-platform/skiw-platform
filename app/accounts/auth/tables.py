"""The global pre-tenant tables `auth_throttle` and `security_event` (spec §4.1 "Global tables";
plan M3c). Models for the schema only: accounts.auth.throttle and accounts.auth.events write
them by SQL, and only accounts.auth may (Semgrep auth-tables-accounts-only).
Every key and HMAC is a 32-byte HMAC-SHA-256 value, so no raw email or IP fits a column.

`security_event.agency_id` (slice spec Decisions 30, 33; M4r-1c): NULL for every pre-tenant kind,
the changed row's agency for the ten role and org change kinds, which carry no HMAC. Its FK to
`agency` and its RLS are in accounts.0024."""

from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import Exact


def _hmac_length(table: str, field: str) -> models.CheckConstraint:
    return models.CheckConstraint(condition=Exact(Length(field), 32), name=f"{table}_{field}_32")


class AuthThrottle(models.Model):
    pk = models.CompositePrimaryKey("key_hmac", "window_start")
    key_hmac = models.BinaryField()
    window_start = models.DateTimeField()
    count = models.IntegerField()

    class Meta:
        db_table = "auth_throttle"
        constraints = (
            _hmac_length("auth_throttle", "key_hmac"),
            models.CheckConstraint(
                condition=models.Q(count__gte=0), name="auth_throttle_count_gte_0"
            ),
        )

    def __str__(self) -> str:
        return "auth_throttle row"  # no key, window or count in reprs or logs


# Decision 30: the closed list of change kinds, written only by the M4r-1e audit triggers.
CHANGE_KINDS = (
    "role.created",
    "role.renamed",
    "role.deleted",
    "permission.set",
    "permission.unset",
    "role.assigned",
    "role.unassigned",
    "org.added",
    "org.moved",
    "org.renamed",
)
_CHANGE = models.Q(kind__in=CHANGE_KINDS)


class SecurityEvent(models.Model):
    id = models.UUIDField(primary_key=True)
    at = models.DateTimeField()
    kind = models.CharField(max_length=64)
    email_hmac = models.BinaryField(null=True)
    ip_hmac = models.BinaryField(null=True)
    details_json = models.JSONField()
    agency_id = models.UUIDField(null=True)

    class Meta:
        db_table = "security_event"
        constraints = (
            _hmac_length("security_event", "email_hmac"),
            _hmac_length("security_event", "ip_hmac"),
            # A change kind if and only if it names an agency.
            models.CheckConstraint(
                condition=(_CHANGE & models.Q(agency_id__isnull=False))
                | (~_CHANGE & models.Q(agency_id__isnull=True)),
                name="security_event_change_kind_agency",
            ),
            models.CheckConstraint(
                condition=~_CHANGE | models.Q(email_hmac__isnull=True, ip_hmac__isnull=True),
                name="security_event_change_kind_no_hmac",
            ),
        )
        # The RLS predicate's agency_id branch and the FK (tenancy test_row_level_live [A5]).
        indexes = (models.Index(fields=["agency_id"], name="security_event_agency_id"),)

    def __str__(self) -> str:
        return f"security_event {self.kind}"
