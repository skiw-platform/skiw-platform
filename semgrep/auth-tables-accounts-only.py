# Fixture for `semgrep --test semgrep/` (rule auth-tables-accounts-only).
from django.db import connection

from accounts import models
from accounts.auth.tables import AuthThrottle as Row


def banned(key, window, kind):
    # ruleid: auth-tables-accounts-only
    Row.objects.filter(key_hmac=key).update(count=0)
    # ruleid: auth-tables-accounts-only
    models.SecurityEvent.objects.all().delete()
    # ruleid: auth-tables-accounts-only
    models.SecurityEvent(kind=kind).save()
    with connection.cursor() as cursor:
        # ruleid: auth-tables-accounts-only
        cursor.execute("UPDATE auth_throttle SET count = 0 WHERE key_hmac = %s", [key])
        # ruleid: auth-tables-accounts-only
        cursor.execute("insert into security_event (id, kind) values (%s, %s)", [key, kind])
        # ruleid: auth-tables-accounts-only
        cursor.execute("DELETE FROM auth_stepup")
        # ruleid: auth-tables-accounts-only
        cursor.execute("TRUNCATE security_event")


def allowed():
    # ok: auth-tables-accounts-only
    tables = {"auth_throttle": {"SELECT", "INSERT", "UPDATE"}, "security_event": {"SELECT"}}
    # ok: auth-tables-accounts-only
    query = "SELECT to_regclass('security_event') IS NOT NULL"
    return tables, query
