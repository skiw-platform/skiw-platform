"""Hashed-key database session store (spec D6, §4.1 `django_session`, §9 M2; plan M2b).

The cookie carries Django's random 32-character key; the database only ever sees
stored_key(cookie) = sha256(cookie).hexdigest(), so a dump of the table yields no usable cookie.
Every method of Django's db store that queries by key is overridden here, sync and async;
app/accounts/tests/test_session_store_surface.py pins that list against Django's.

Each session has one absolute deadline, now + SKIW_SESSION_ABSOLUTE_H when it starts. Saves and
key rotation (cycle_key) keep it; Django's sliding expiry is never used. Only
start_new_lifetime(), called by M3's successful login just before login()'s cycle_key, renews it.

session_data carries a MAC under tenant_source_key bound to the stored key and the row's
expire_date (accounts.source_key; plan M2c). A row that fails it loads like a missing one.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.sessions.backends import db
from django.contrib.sessions.backends.base import VALID_KEY_CHARS
from django.utils import timezone

from accounts import source_key
from accounts.session_model import Session

KEY_LENGTH = 32  # what Django's SessionBase._get_new_session_key mints (≈ 165 bits)
KEY_CHARS = frozenset(VALID_KEY_CHARS)
FIXED_DEADLINE = "the session deadline is fixed when the session starts (spec D6)"


def stored_key(raw: str) -> str:
    """The primary key for cookie value `raw`; also the session_key_hash of later tables."""
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


class SessionStore(db.SessionStore):
    def __init__(self, session_key: str | None = None) -> None:
        self._absolute_expiry: datetime | None = None
        self._renew_lifetime = False  # per store object, never saved
        super().__init__(session_key)

    @classmethod
    def get_model_class(cls) -> type[Session]:
        return Session

    def _validate_session_key(self, key: str | None) -> bool:
        # UNI-03: only a key this store could have minted; anything else is no session and is
        # never queried. Django checks only for 8 or more characters.
        return key is not None and len(key) == KEY_LENGTH and set(key) <= KEY_CHARS

    def _current_key(self) -> str:
        key = self.session_key
        if key is None:  # save() calls create() first, and create() always sets a key
            raise RuntimeError("the session has no key")
        return key

    # Lifetime.

    def _deadline_unknown(self) -> bool:
        """An existing session whose row has not been read yet."""
        known = self._absolute_expiry is not None or self._renew_lifetime
        return self.session_key is not None and not known

    def _ensure_deadline(self) -> datetime:
        if self._renew_lifetime or self._absolute_expiry is None:
            hours = timedelta(hours=settings.SKIW_SESSION_ABSOLUTE_H)
            self._absolute_expiry = timezone.now() + hours
            self._renew_lifetime = False
        return self._absolute_expiry

    def start_new_lifetime(self) -> None:
        """A new authentication: the next deadline made is now + SKIW_SESSION_ABSOLUTE_H. A
        later load() cannot put the old row's deadline back (login() loads before cycle_key)."""
        self._renew_lifetime = True

    async def astart_new_lifetime(self) -> None:
        self.start_new_lifetime()

    def get_expiry_date(self, **kwargs: Any) -> datetime:
        if kwargs:
            raise TypeError(FIXED_DEADLINE)
        if self._deadline_unknown():
            self.load()
        return self._ensure_deadline()

    async def aget_expiry_date(self, **kwargs: Any) -> datetime:
        if kwargs:
            raise TypeError(FIXED_DEADLINE)
        if self._deadline_unknown():
            await self.aload()
        return self._ensure_deadline()

    def get_expiry_age(self, **kwargs: Any) -> int:
        delta = self.get_expiry_date(**kwargs) - timezone.now()
        return delta.days * 86400 + delta.seconds

    async def aget_expiry_age(self, **kwargs: Any) -> int:
        delta = await self.aget_expiry_date(**kwargs) - timezone.now()
        return delta.days * 86400 + delta.seconds

    def set_expiry(self, value: datetime | timedelta | int | None) -> None:
        raise NotImplementedError(FIXED_DEADLINE)

    async def aset_expiry(self, value: datetime | timedelta | int | None) -> None:
        raise NotImplementedError(FIXED_DEADLINE)

    def clear(self) -> None:
        # Django's clear() skips the load, so the next save would give the existing row a fresh
        # deadline. flush() and aflush() empty the session without this check.
        if self._deadline_unknown():
            raise RuntimeError("load the session before clear(), or use flush()")
        super().clear()

    def flush(self) -> None:
        db.SessionStore.clear(self)
        self.delete()
        self._session_key = None
        self._absolute_expiry, self._renew_lifetime = None, False

    async def aflush(self) -> None:
        db.SessionStore.clear(self)
        await self.adelete()
        self._session_key = None
        self._absolute_expiry, self._renew_lifetime = None, False

    # Database access: always by stored_key(), never by the raw cookie value.

    def _get_session_from_db(self) -> Session | None:
        if self.session_key is None:
            return None
        try:
            return Session.objects.get(
                session_key=stored_key(self.session_key), expire_date__gt=timezone.now()
            )
        except Session.DoesNotExist:  # absent or past its deadline
            self._session_key = None
            return None

    async def _aget_session_from_db(self) -> Session | None:
        if self.session_key is None:
            return None
        try:
            return await Session.objects.aget(
                session_key=stored_key(self.session_key), expire_date__gt=timezone.now()
            )
        except Session.DoesNotExist:
            self._session_key = None
            return None

    def _loaded(self, row: Session | None) -> dict[str, Any]:
        if row is None:
            return {}
        blob = source_key.unseal(row.session_key, row.expire_date, row.session_data)
        if blob is None:
            # As Django's not-found path: the next save mints a new key, so the rejected row is
            # never updated in place, and its deadline is never taken (plan M2c Risk 2).
            self._session_key = None
            return {}
        if not self._renew_lifetime:
            self._absolute_expiry = row.expire_date
        return self.decode(blob)

    def load(self) -> dict[str, Any]:
        return self._loaded(self._get_session_from_db())

    async def aload(self) -> dict[str, Any]:
        return self._loaded(await self._aget_session_from_db())

    def exists(self, session_key: str) -> bool:
        return Session.objects.filter(session_key=stored_key(session_key)).exists()

    async def aexists(self, session_key: str) -> bool:
        return await Session.objects.filter(session_key=stored_key(session_key)).aexists()

    def create_model_instance(self, data: dict[str, Any]) -> Session:
        key, deadline = stored_key(self._current_key()), self._ensure_deadline()
        return Session(
            session_key=key,
            session_data=source_key.seal(key, deadline, self.encode(data)),
            expire_date=deadline,
        )

    async def acreate_model_instance(self, data: dict[str, Any]) -> Session:
        return self.create_model_instance(data)  # no I/O: the key and the deadline are in memory

    def delete(self, session_key: str | None = None) -> None:
        key = self.session_key if session_key is None else session_key
        if key is not None and self._validate_session_key(key):
            Session.objects.filter(session_key=stored_key(key)).delete()

    async def adelete(self, session_key: str | None = None) -> None:
        key = self.session_key if session_key is None else session_key
        if key is not None and self._validate_session_key(key):
            await Session.objects.filter(session_key=stored_key(key)).adelete()
