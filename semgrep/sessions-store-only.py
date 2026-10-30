# Fixture for `semgrep --test semgrep/` (rule sessions-store-only).
from django.db import connection

from accounts import models
from accounts.session_model import Session as Row


def banned(raw_key, expires):
    # ruleid: sessions-store-only
    Row.objects.filter(session_key=raw_key).delete()
    # ruleid: sessions-store-only
    models.Session.objects.save(raw_key, {}, expires)
    with connection.cursor() as cursor:
        # ruleid: sessions-store-only
        cursor.execute("SELECT session_data FROM django_session WHERE session_key = %s", [raw_key])
        # ruleid: sessions-store-only
        cursor.execute("delete from django_session")
        # ruleid: sessions-store-only
        cursor.execute("UPDATE django_session SET expire_date = %s", [expires])


def allowed(request):
    # ok: sessions-store-only
    request.session["probe"] = "x"
    # ok: sessions-store-only
    tables = {"procrastinate_workers", "django_session"}
    # ok: sessions-store-only
    note = "rows of django_session are deleted on logout"
    return tables, note
