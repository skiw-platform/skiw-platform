"""The `django_session` table (spec §4.1, D6). Only accounts.session reads or writes it (TEN-10;
import-linter and the Semgrep rule sessions-store-only)."""

from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.base_session import AbstractBaseSession
from django.db import models


class Session(AbstractBaseSession):
    # Django's model holds 40 characters; the primary key is sha256(cookie).hexdigest().
    session_key = models.CharField("session key", max_length=64, primary_key=True)

    class Meta:
        db_table = "django_session"
        verbose_name = "session"
        verbose_name_plural = "sessions"

    @classmethod
    def get_session_store_class(cls) -> type[SessionBase]:
        from accounts.session import SessionStore  # here: accounts.session imports this module

        return SessionStore
