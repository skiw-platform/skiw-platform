"""Django-upgrade guard for the hashed store (plan M2b Risk 1, A1). A method Django adds or removes
on its session classes fails here until it is reviewed against accounts.session."""

from django.contrib.sessions.backends import db
from django.contrib.sessions.backends.base import SessionBase

from accounts.session import SessionStore

# Django 5.2.17 `backends/db.py` SessionStore, each with what keeps it off the raw key.
DB_STORE = {
    "__init__": "overridden (lifetime state)",
    "get_model_class": "overridden: accounts.session_model.Session",
    "model": "inherited: the cached get_model_class()",
    "_get_session_from_db": "overridden: queries by stored_key()",
    "_aget_session_from_db": "overridden: queries by stored_key()",
    "load": "overridden: also reads the row's deadline",
    "aload": "overridden: also reads the row's deadline",
    "exists": "overridden: queries by stored_key()",
    "aexists": "overridden: queries by stored_key()",
    "create_model_instance": "overridden: the instance pk is stored_key()",
    "acreate_model_instance": "overridden: the instance pk is stored_key()",
    "delete": "overridden: deletes by stored_key()",
    "adelete": "overridden: deletes by stored_key()",
    "create": "inherited: only exists() and save()",
    "acreate": "inherited: only aexists() and asave()",
    "save": "inherited: writes the instance from create_model_instance()",
    "asave": "inherited: writes the instance from acreate_model_instance()",
    "clear_expired": "inherited: by expire_date only, on get_model_class()",
    "aclear_expired": "inherited: by expire_date only, on get_model_class()",
}
# Django 5.2.17 `backends/base.py` SessionBase methods that set or read the key or the expiry.
LIFETIME_OVERRIDES = {
    "_validate_session_key",
    "get_expiry_age",
    "aget_expiry_age",
    "get_expiry_date",
    "aget_expiry_date",
    "set_expiry",
    "aset_expiry",
    "clear",
    "flush",
    "aflush",
}
SESSION_BASE = {
    *LIFETIME_OVERRIDES,
    *("__contains__", "__delitem__", "__getitem__", "__init__", "__setitem__"),
    *("_aget_new_session_key", "_aget_or_create_session_key", "_aget_session"),
    *("_get_new_session_key", "_get_or_create_session_key", "_get_session"),
    *("_get_session_key", "_session", "_session_key", "_set_session_key"),
    *("aclear_expired", "acreate", "acycle_key", "adelete", "adelete_test_cookie", "aexists"),
    *("aget", "aget_expire_at_browser_close", "ahas_key", "aitems", "akeys", "aload", "apop"),
    *("asave", "aset", "aset_test_cookie", "asetdefault", "atest_cookie_worked", "aupdate"),
    *("avalues", "clear_expired", "create", "cycle_key", "decode", "delete"),
    *("delete_test_cookie", "encode", "exists", "get", "get_expire_at_browser_close"),
    *("get_session_cookie_age", "has_key", "is_empty", "items", "key_salt", "keys", "load"),
    *("pop", "save", "session_key", "set_test_cookie", "setdefault", "test_cookie_worked"),
    *("update", "values"),
}


def members(cls: type) -> set[str]:
    return {name for name in vars(cls) if not name.startswith("__") or name == "__init__"}


def methods(cls: type) -> set[str]:
    return {
        name
        for name, value in vars(cls).items()
        if callable(value) or isinstance(value, property | classmethod)
    }


def test_django_db_store_methods_are_the_reviewed_list() -> None:
    assert members(db.SessionStore) == set(DB_STORE)


def test_django_session_base_methods_are_the_reviewed_list() -> None:
    assert methods(SessionBase) == SESSION_BASE


def test_every_method_marked_overridden_is_defined_on_the_hashed_store() -> None:
    overridden = {n for n, why in DB_STORE.items() if why.startswith("overridden")}
    assert overridden | LIFETIME_OVERRIDES <= set(vars(SessionStore))
    inherited = {n for n, why in DB_STORE.items() if why.startswith("inherited")}
    assert not inherited & set(vars(SessionStore))
