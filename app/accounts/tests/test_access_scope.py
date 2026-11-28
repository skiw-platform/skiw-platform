"""`ScopedModel` (slice spec Decisions 9, 10, 27; plan row M4r-4, M4r-4a, M4r-4b): one manager, the
two declarations refused when wrong, the system checks on the owner field and on relations,
Django's readers of every row refused (PR 197 review R1, R2), and what `scoped()` refuses before
it reads.
The models live in an isolated registry, so the app's own stays unchanged."""

import importlib
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import F, Q, QuerySet
from django.db.transaction import TransactionManagementError
from django.forms import modelform_factory, modelformset_factory
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404
from django.test.utils import isolate_apps
from django.views.generic import DetailView, ListView

from accounts.access.grants import Grant
from accounts.access.scope import ORG_MAX_DEPTH, ScopedModel, Unscoped, scoped
from accounts.tests.scope_harness import Sly, signed
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


@pytest.mark.parametrize(
    "line", ["both", "any", "Insurance", "", False, Sly("x", "insurance"), "missing"]
)
@isolate_apps("accounts")
def test_a_scope_line_other_than_a_line_or_none_is_refused(line: object) -> None:
    declared = {} if line == "missing" and type(line) is str else {"SCOPE_LINE": line}
    with pytest.raises(ImproperlyConfigured, match="SCOPE_LINE"):
        type("Row", (ScopedModel,), {"__module__": __name__, "SCOPE_OWNER": "id", **declared})


@pytest.mark.parametrize("line", ["insurance", "investment", None])
@isolate_apps("accounts")
def test_a_scope_line_of_insurance_investment_or_none_is_accepted(line: str | None) -> None:
    fields = {"__module__": __name__, "SCOPE_LINE": line}
    row = cast(type[ScopedModel], type("Row", (ScopedModel,), {**fields, "SCOPE_OWNER": "id"}))
    assert row.SCOPE_LINE is line


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


E5, KEY, DEFERRED = ["scope.E005"], ["agency_id", "id"], models.Deferrable.DEFERRED


class Unvalidated(models.UniqueConstraint):
    def validate(self, *args: object, **kwargs: object) -> None:
        pass


@pytest.mark.parametrize(
    ("declared", "errors"),
    [
        (TenantModel.Meta.constraints, []),
        ((models.UniqueConstraint(fields=["id", "agency_id"], name="r"),), []),
        ((models.UniqueConstraint(fields=["owner_user_id"], name="o"),), ["scope.E005"]),
        ((models.UniqueConstraint(fields=[*KEY, "owner_user_id"], name="w"),), ["scope.E005"]),
        ((models.UniqueConstraint(fields=KEY, condition=~Q(id=None), name="c"),), E5),
        ((models.UniqueConstraint(F("agency_id"), F("id"), name="e"),), ["scope.E005"]),
        ((models.UniqueConstraint(fields=KEY, deferrable=DEFERRED, name="d"),), E5),
        ((), ["scope.E005"]),
        ((models.CheckConstraint(condition=~Q(id=None), name="agency_id_id_uq"),), ["scope.E005"]),
        ((Unvalidated(fields=["agency_id", "id"], name="u"),), ["scope.E005"]),
    ],
)
@isolate_apps("accounts")
def test_the_tenant_key(declared: tuple[models.BaseConstraint, ...], errors: list[str]) -> None:
    class Row(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

        class Meta(TenantModel.Meta):
            constraints = declared

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

    monkeypatch.setattr(QuerySet, "_fetch_all", lambda rows: setattr(rows, "_result_cache", []))
    # Stands in for scoped(), built in scope.py the same way; the one suppression.
    # nosemgrep: scoped-only
    rows = cast("QuerySet[Row]", QuerySet(Row)).filter(owner_user_id=uuid4())
    row = Row(id=uuid4(), at=datetime.now(UTC), unit=Unit(id=uuid4()))
    posted = {"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-0-id": str(row.id)}
    readers = [
        lambda: get_object_or_404(Row, pk=row.id),
        lambda: get_list_or_404(Row),
        ListView(model=Row).get_queryset,
        DetailView(model=Row).get_queryset,
        *(getattr(row, n) for n in ("get_next_by_at", "get_previous_in_order", "validate_unique")),
        lambda: modelform_factory(Row, fields=["at"])(data={"at": "2026-11-27 10:00"}).is_valid(),
        lambda: modelformset_factory(Row, fields=["at"])().forms,
        lambda: modelformset_factory(Row, fields=["at"])(queryset=rows).forms,
        lambda: modelformset_factory(Row, fields=["id", "at"])(posted, queryset=rows).is_valid(),
    ]
    for reader in readers:
        with pytest.raises(TypeError, match="only through scoped"):
            reader()

    assert len(modelformset_factory(Unit, fields=["id"])().forms) == 1
    for source in (Unit, rows):
        with pytest.raises(Http404):
            get_object_or_404(source, pk=row.id)
        with pytest.raises(Http404):
            get_list_or_404(source)


def test_org_max_depth_is_the_tree_guards() -> None:
    guard = importlib.import_module("accounts.migrations.0027_tree_system_role_guards")
    assert ORG_MAX_DEPTH == guard.ORG_MAX_DEPTH == 32


@isolate_apps("accounts")
def test_scoped_takes_a_concrete_scoped_model_and_the_wrappers_signed() -> None:
    class Owned(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    good = signed(uuid4(), uuid4(), Grant("own", uuid4(), "both", None))
    # Any: every argument below is deliberately the wrong type.
    bad: list[tuple[Any, Any]] = [(m, good) for m in (AppUser, ScopedModel, Owned(), "Owned")]
    for change in (
        {"access": set(good.access)},
        {"access": type("Frozen", (frozenset,), {})(good.access)},  # may override iteration
        {"access": frozenset({("own", uuid4(), "both", None)})},
        {"user_id": str(good.user_id)},
        {"agency_id": str(good.agency_id)},
    ):
        bad.append((Owned, replace(good, **change)))
    fields = ("access", "user_id", "agency_id")
    for gone in fields:  # PR 198 review R1: a missing field is a TypeError too, before any read
        kept = {name: getattr(good, name) for name in fields if name != gone}
        bad.append((Owned, SimpleNamespace(**kept)))
    bad += [(Owned, None), (Owned, object())]
    for model, wrong in bad:
        with pytest.raises(TypeError, match="scoped"):
            scoped(model, wrong)
    with pytest.raises(TransactionManagementError, match="scoped"):
        scoped(Owned, good)
