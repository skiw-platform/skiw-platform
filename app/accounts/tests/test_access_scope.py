"""`ScopedModel` (slice spec Decisions 9, 10, 27; plan row M4r-4, M4r-4a): one manager, the two
declarations refused when wrong, the system checks on the owner field and on relations, and
Django's readers of every row refused (PR 197 review R1).
The models live in an isolated registry, so the app's own stays unchanged."""

import importlib
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import QuerySet
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404
from django.test.utils import isolate_apps
from django.views.generic import DetailView, ListView

from accounts.access.scope import ORG_MAX_DEPTH, ScopedModel, Unscoped
from accounts.user_model import AppUser
from tenancy.models import TenantModel

H = "scope__hidden"


def scope_errors(model: type[ScopedModel]) -> list[str]:
    return sorted(str(e.id) for e in model.check() if str(e.id).startswith("scope."))


@isolate_apps("accounts")
def test_a_scoped_model_has_only_the_unscoped_manager() -> None:
    class Row(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Extra(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        objects = models.Manager()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    declared = {"_unscoped": models.Manager(), "SCOPE_OWNER": "owner_user_id", "SCOPE_LINE": None}
    fields = {"__module__": __name__, "owner_user_id": models.UUIDField()}
    swapped = cast(type[ScopedModel], type("Swapped", (ScopedModel,), {**fields, **declared}))

    assert not hasattr(Row, "objects")
    assert scope_errors(Row) == []
    assert scope_errors(Extra) == ["scope.E001"]
    assert scope_errors(swapped) == ["scope.E001"]


@pytest.mark.parametrize("line", ["insurance", "investment", "both", "", False, "missing"])
@isolate_apps("accounts")
def test_a_scope_line_other_than_none_is_refused(line: object) -> None:
    declared = {} if line == "missing" else {"SCOPE_LINE": line}
    with pytest.raises(ImproperlyConfigured, match="SCOPE_LINE"):
        type("Row", (ScopedModel,), {"__module__": __name__, "SCOPE_OWNER": "id", **declared})


@pytest.mark.parametrize("owner", ["", None, 1, "missing"])
@isolate_apps("accounts")
def test_scope_owner_must_be_declared(owner: object) -> None:
    declared = {} if owner == "missing" else {"SCOPE_OWNER": owner}
    with pytest.raises(ImproperlyConfigured, match="SCOPE_OWNER"):
        type("Row", (ScopedModel,), {"__module__": __name__, "SCOPE_LINE": None, **declared})


@pytest.mark.parametrize(
    ("name", "errors"),
    [
        ("owner_user_id", []),
        ("owner", []),
        ("owner_id", []),
        ("nobody", ["scope.E002"]),
        ("label", ["scope.E002"]),
        ("unit", ["scope.E002"]),
    ],
)
@isolate_apps("accounts")
def test_scope_owner_must_name_a_user_id_field(name: str, errors: list[str]) -> None:
    class Unit(TenantModel):
        id = models.UUIDField(primary_key=True)

    class Row(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        owner = models.ForeignKey(AppUser, models.PROTECT, related_name="+", related_query_name=H)
        unit = models.ForeignKey(Unit, models.PROTECT, related_name="+", related_query_name=H)
        label = models.TextField()
        SCOPE_OWNER = name
        SCOPE_LINE = None

    assert scope_errors(Row) == errors


@isolate_apps("accounts")
def test_a_join_to_a_scoped_model_is_refused() -> None:
    class Target(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        parent = models.ForeignKey("self", models.PROTECT, related_name="+", related_query_name=H)
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Peer(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        target = models.ForeignKey(Target, models.PROTECT, related_name="+", related_query_name=H)
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Note(TenantModel):
        id = models.UUIDField(primary_key=True)
        row = models.ForeignKey(Target, models.PROTECT, related_name="+")
        one = models.OneToOneField(Target, models.PROTECT, related_name="+", related_query_name=H)
        many = models.ManyToManyField(Target, related_name="+")

    class Child(Peer):
        pass

    assert scope_errors(Target) == ["scope.E003"] * 6
    assert scope_errors(Peer) == ["scope.E003"]
    assert scope_errors(Child) == ["scope.E004"]

    class Plain(TenantModel):
        id = models.UUIDField(primary_key=True)
        links: "models.ManyToManyField[Plain, Link]" = models.ManyToManyField(
            "self", through="Link", symmetrical=False, related_name="+"
        )
        twin: "models.ManyToManyField[Plain, Plain]" = models.ManyToManyField(
            "self", db_table="accounts_link"
        )

    class Link(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        a = models.ForeignKey(Plain, models.PROTECT, related_name="+", related_query_name="s__a")
        b = models.ForeignKey(Plain, models.PROTECT, related_name="+", related_query_name="s__b")
        pairs: "models.ManyToManyField[Link, Pair]" = models.ManyToManyField(
            "self", through="Pair", symmetrical=False, related_name="+", related_query_name=H
        )
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Pair(ScopedModel):
        owner_user_id = models.UUIDField()
        a = models.ForeignKey(Link, models.PROTECT, related_name="+", related_query_name="s__a")
        b = models.ForeignKey(Link, models.PROTECT, related_name="+", related_query_name="s__b")
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Spy(TenantModel):
        id = models.UUIDField(primary_key=True)

        class Meta(TenantModel.Meta):
            db_table = '"public"."accounts_link"'

    class Mirror(Link):
        class Meta:
            proxy = True

    assert scope_errors(Link) == ["scope.E003"] * 6
    assert scope_errors(Pair) == ["scope.E003"]
    assert scope_errors(Mirror) == ["scope.E003"] * 5


@isolate_apps("accounts")
def test_a_relation_from_a_scoped_model_needs_a_query_name_no_lookup_can_name() -> None:
    class Unit(TenantModel):
        id = models.UUIDField(primary_key=True)

    class Named(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner = models.ForeignKey(AppUser, models.PROTECT, related_name="+")
        suffixed = models.ForeignKey(Unit, models.PROTECT, related_name="named+")
        queried = models.ForeignKey(Unit, models.PROTECT, related_name="+", related_query_name="r")
        accessor = models.ForeignKey(Unit, models.PROTECT, related_query_name="scope__accessor")
        SCOPE_OWNER = "owner"
        SCOPE_LINE = None

    class Base(TenantModel):
        id = models.UUIDField(primary_key=True)
        _unscoped = Unscoped()

    class Sub(Base, ScopedModel):
        base_ptr = models.OneToOneField(
            Base, models.PROTECT, parent_link=True, related_name="+", related_query_name=H
        )
        owner_user_id = models.UUIDField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    assert scope_errors(Named) == ["scope.E004"] * 4
    assert scope_errors(Sub) == ["scope.E004"]


@isolate_apps("accounts")
def test_django_readers_of_every_row_refuse_a_scoped_model_not_a_queryset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Unit(TenantModel):
        id = models.UUIDField(primary_key=True)

    class Row(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        unit = models.ForeignKey(Unit, models.PROTECT, related_name="+", related_query_name=H)
        at = models.DateTimeField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

        class Meta(TenantModel.Meta):
            order_with_respect_to = "unit"

    row = Row(id=uuid4(), at=datetime.now(UTC), unit=Unit(id=uuid4()))
    readers = [
        lambda: get_object_or_404(Row, pk=row.id),
        lambda: get_list_or_404(Row),
        ListView(model=Row).get_queryset,
        DetailView(model=Row).get_queryset,
        *(getattr(row, name) for name in ("get_next_by_at", "get_previous_in_order")),
    ]
    for reader in readers:
        with pytest.raises(TypeError, match="only through scoped"):
            reader()

    monkeypatch.setattr(QuerySet, "_fetch_all", lambda rows: setattr(rows, "_result_cache", []))
    # Stands in for M4r-4b's scoped(), which starts from this queryset; the one suppression.
    # nosemgrep: scoped-only
    rows = Row._unscoped.get_queryset()
    for source in (Unit, rows):
        with pytest.raises(Http404):
            get_object_or_404(source, pk=row.id)
        with pytest.raises(Http404):
            get_list_or_404(source)


def test_org_max_depth_is_the_tree_guards() -> None:
    guard = importlib.import_module("accounts.migrations.0027_tree_system_role_guards")
    assert ORG_MAX_DEPTH == guard.ORG_MAX_DEPTH == 32
