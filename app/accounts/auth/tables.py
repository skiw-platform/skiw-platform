"""The global pre-tenant tables `auth_throttle` and `security_event` (spec §4.1 "Global tables";
plan M3c). Models for the schema only; no code writes them yet (the throttle and the event
writer come in a later PR), and only accounts.auth may (Semgrep auth-tables-accounts-only).
Every key and HMAC is a 32-byte HMAC-SHA-256 value, so no raw email or IP fits a column."""

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


class SecurityEvent(models.Model):
    id = models.UUIDField(primary_key=True)
    at = models.DateTimeField()
    kind = models.CharField(max_length=64)
    email_hmac = models.BinaryField(null=True)
    ip_hmac = models.BinaryField(null=True)
    details_json = models.JSONField()

    class Meta:
        db_table = "security_event"
        constraints = (
            _hmac_length("security_event", "email_hmac"),
            _hmac_length("security_event", "ip_hmac"),
        )

    def __str__(self) -> str:
        return f"security_event {self.kind}"
