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
    # ruleid: auth-tables-accounts-only
    Row._default_manager.all().delete()
    # ruleid: auth-tables-accounts-only
    models.SecurityEvent._base_manager.all().delete()
    with connection.cursor() as cursor:
        # ruleid: auth-tables-accounts-only
        cursor.execute("UPDATE auth_throttle SET count = 0 WHERE key_hmac = %s", [key])
        # ruleid: auth-tables-accounts-only
        cursor.execute("insert into security_event (id, kind) values (%s, %s)", [key, kind])
        # ruleid: auth-tables-accounts-only
        cursor.execute("DELETE FROM auth_stepup")
        # ruleid: auth-tables-accounts-only
        cursor.execute("TRUNCATE security_event")
        # ruleid: auth-tables-accounts-only
        cursor.execute("""
            UPDATE auth_throttle SET count = 0
        """)
        # ruleid: auth-tables-accounts-only
        cursor.execute(" DELETE FROM auth_throttle")
        # ruleid: auth-tables-accounts-only
        cursor.execute("WITH d AS (DELETE FROM auth_throttle RETURNING 1) SELECT count(*) FROM d")
        # ruleid: auth-tables-accounts-only
        cursor.execute("SELECT 1; UPDATE auth_throttle SET count = 0")
        # ruleid: auth-tables-accounts-only
        cursor.execute("-- reset\nUPDATE auth_throttle SET count = 0")


def allowed():
    # ok: auth-tables-accounts-only
    tables = {"auth_throttle": {"SELECT", "INSERT", "UPDATE"}, "security_event": {"SELECT"}}
    # ok: auth-tables-accounts-only
    query = "SELECT to_regclass('security_event') IS NOT NULL"
    # ok: auth-tables-accounts-only
    other = "DELETE FROM django_session WHERE session_key = %s"
    # ok: auth-tables-accounts-only
    name = Row._meta.db_table
    return tables, query, other, name
