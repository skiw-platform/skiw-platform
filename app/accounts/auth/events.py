"""The `security_event` writer (spec §4.1: pre-tenant security events, append-only, only
accounts.auth; owner Q4 (a)). An event carries HMACs, never a raw email or IP (UNI-09): `details`
takes only whole-number or yes/no values under short names, so no text can reach it."""

import json
import re
import uuid
from collections.abc import Mapping

from django.db import connection
from django.utils import timezone

# login.lookup and passkey.lookup are written by guard.auth_lookup_login and
# guard.auth_lookup_credential themselves (accounts.0009, 0015), not from here.
KINDS = frozenset({"account.locked", "factor.locked", "login.failed"})
DETAIL_NAME = re.compile(r"[a-z_]{1,32}", re.ASCII)


def record_event(
    kind: str, email_hmac: bytes | None, ip_hmac: bytes | None, details: Mapping[str, int]
) -> None:
    if kind not in KINDS:
        raise ValueError("unknown security event kind")
    if not all(DETAIL_NAME.fullmatch(k) and type(v) in (int, bool) for k, v in details.items()):
        raise ValueError("security event details take short names and int or bool values only")
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO security_event (id, at, kind, email_hmac, ip_hmac, details_json)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [uuid.uuid4(), timezone.now(), kind, email_hmac, ip_hmac, json.dumps(dict(details))],
        )
