# Fixture for `semgrep --test semgrep/` (rule scoped-only).
# ruff: noqa: B009 -- getattr with a constant name is the shape under test.
from typing import cast

from django.db import models
from django.db.models import QuerySet
from django.db.models import QuerySet as AllRows
from django.db.models import query as queries
from django.db.models.query import QuerySet as Rows

from accounts.access import scope
from accounts.models import AppUser


def managers(Client, row):
    # ruleid: scoped-only
    Client._unscoped.all()
    # ruleid: scoped-only
    Client._unscoped.filter(owner_user_id=1)
    # ruleid: scoped-only
    type(row)._unscoped.get(pk=row.pk)
    # ruleid: scoped-only
    getattr(Client, "_unscoped").all()
    # ruleid: scoped-only
    getattr(Client, "_unscoped", None)
    # ruleid: scoped-only
    Client._default_manager.all()
    # ruleid: scoped-only
    row.__class__._base_manager.all()
    # ruleid: scoped-only
    getattr(Client, "_default_manager").count()
    # ruleid: scoped-only
    getattr(Client, "_base_manager")
    # ruleid: scoped-only
    Client._meta.default_manager.all()
    # ruleid: scoped-only
    Client._meta.base_manager.all()
    # ruleid: scoped-only
    Client._meta.managers[0].all()
    # ruleid: scoped-only
    Client._meta.managers_map["_unscoped"].all()
    # ruleid: scoped-only
    Client._meta.local_managers[0].all()
    # ruleid: scoped-only
    getattr(Client._meta, "default_manager").all()
    # ruleid: scoped-only
    AppUser._default_manager.all()


def querysets(Client):
    # ruleid: scoped-only
    QuerySet(model=Client)
    # ruleid: scoped-only
    models.QuerySet(Client)
    # ruleid: scoped-only
    queries.QuerySet(model=Client)
    # ruleid: scoped-only
    Rows(model=Client)
    # ruleid: scoped-only
    AllRows(model=Client)
    # ruleid: scoped-only
    QuerySet[Client, Client](Client)
    # ruleid: scoped-only
    models.QuerySet["Client"](Client)
    # ruleid: scoped-only
    Rows[Client](model=Client)
    # ruleid: scoped-only
    (AllRows[Client])(Client)
    # ruleid: scoped-only
    QuerySet[Client][Client](Client)
    # ruleid: scoped-only
    Rows.__class_getitem__(Client)(Client)
    # ruleid: scoped-only
    getattr(models, "QuerySet")(Client)
    # ruleid: scoped-only
    getattr(queries, "QuerySet")[Client](Client)


def passed_in(QuerySet, lib, Client):
    # Names Semgrep cannot resolve: a class handed in, a module it does not know.
    # ruleid: scoped-only
    QuerySet(model=Client)
    # ruleid: scoped-only
    lib.QuerySet(model=Client)
    # ruleid: scoped-only
    QuerySet[Client](model=Client)


def allowed(Client, signed):
    # The door, other models' managers, and the parts of _meta that hold no manager.
    # ok: scoped-only
    scope.ScopedModel.check()
    # ok: scoped-only
    AppUser.objects.filter(id=signed.user_id)
    # ok: scoped-only
    print(Client._meta.label, Client._meta.apps, Client._meta.get_fields())
    # ok: scoped-only
    print(Client.unscoped, Client.default_manager, getattr(Client, "managers"))
    # ok: scoped-only
    getattr(Client, "_meta")
    # ok: scoped-only
    print(list[AppUser](), QuerySet.__name__.lower(), getattr(models, "Q")(pk=1))


# ok: scoped-only
def typed(rows: QuerySet[AppUser]) -> QuerySet[AppUser]:
    # ok: scoped-only
    isinstance(rows, QuerySet)
    # ok: scoped-only
    return cast("QuerySet[AppUser]", cast(QuerySet[AppUser], rows))


# ok: scoped-only
class TypedRows(QuerySet[AppUser]):
    pass
