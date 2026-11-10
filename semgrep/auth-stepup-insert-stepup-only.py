# Fixture for `semgrep --test semgrep/` (rule auth-stepup-insert-stepup-only).
from django.apps import apps
from django.db import connection

import accounts.stepup_model
from accounts import models
from accounts.stepup_model import AuthStepup
from accounts.stepup_model import AuthStepup as Row


def banned(row, key_hash):
    # ruleid: auth-stepup-insert-stepup-only
    AuthStepup.objects.create(id=row, session_key_hash=key_hash)
    # ruleid: auth-stepup-insert-stepup-only
    Row(id=row).save(force_insert=True)
    # ruleid: auth-stepup-insert-stepup-only
    models.AuthStepup.objects.bulk_create([])
    # ruleid: auth-stepup-insert-stepup-only
    accounts.stepup_model.AuthStepup._base_manager.filter(id=row).exists()
    # ruleid: auth-stepup-insert-stepup-only
    Row._default_manager.all()
    # ruleid: auth-stepup-insert-stepup-only
    models.AuthStepup(id=row)
    # ruleid: auth-stepup-insert-stepup-only
    apps.get_model("accounts", "AuthStepup").objects.all()
    # ruleid: auth-stepup-insert-stepup-only
    apps.get_model("accounts.authstepup")
    with connection.cursor() as cursor:
        # ruleid: auth-stepup-insert-stepup-only
        cursor.execute("INSERT INTO auth_stepup (id) VALUES (%s)", [row])
        # ruleid: auth-stepup-insert-stepup-only
        cursor.execute("insert into public.auth_stepup select * from x")
        # ruleid: auth-stepup-insert-stepup-only
        cursor.execute("""
            INSERT INTO auth_stepup (id) SELECT id FROM auth_throttle
        """)
        # ruleid: auth-stepup-insert-stepup-only
        cursor.execute("COPY auth_stepup FROM STDIN")
        # ruleid: auth-stepup-insert-stepup-only
        cursor.execute("WITH d AS (SELECT 1) INSERT INTO auth_stepup SELECT * FROM d")


def allowed(cursor, row):
    # ok: auth-stepup-insert-stepup-only
    tables = {"auth_stepup": {"SELECT", "INSERT"}}
    # ok: auth-stepup-insert-stepup-only
    query = "SELECT to_regclass('auth_stepup') IS NOT NULL"
    # ok: auth-stepup-insert-stepup-only
    name = AuthStepup._meta.db_table
    # ok: auth-stepup-insert-stepup-only
    other = "INSERT INTO session_revocation (id) VALUES (%s)"
    # ok: auth-stepup-insert-stepup-only
    model = apps.get_model("accounts", "UserFactor")
    return tables, query, name, other, model
