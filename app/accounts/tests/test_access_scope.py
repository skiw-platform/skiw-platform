"""`ScopedModel` (slice spec Decisions 9, 10, 27; plan row M4r-4, M4r-4a): one manager, the two
declarations refused when wrong, and the system checks on the owner field and reverse accessors.
The models live in an isolated registry, so the app's own stays unchanged."""

import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test.utils import isolate_apps

from accounts.access.scope import ORG_MAX_DEPTH, ScopedModel
from accounts.user_model import AppUser
from tenancy.models import TenantModel


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

    assert not hasattr(Row, "objects")
    assert scope_errors(Row) == []
    assert scope_errors(Extra) == ["scope.E001"]


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
        owner = models.ForeignKey(
            AppUser, on_delete=models.PROTECT, db_constraint=False, related_name="+"
        )
        unit = models.ForeignKey(
            Unit, on_delete=models.PROTECT, db_constraint=False, related_name="+"
        )
        label = models.TextField()
        SCOPE_OWNER = name
        SCOPE_LINE = None

    assert scope_errors(Row) == errors


@isolate_apps("accounts")
def test_a_relation_on_or_into_a_scoped_model_has_no_reverse_accessor() -> None:
    class Hidden(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner = models.ForeignKey(
            AppUser, on_delete=models.PROTECT, db_constraint=False, related_name="+"
        )
        parent = models.ForeignKey("self", models.PROTECT, null=True, related_name="+")
        SCOPE_OWNER = "owner"
        SCOPE_LINE = None

    class Outward(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner = models.ForeignKey(AppUser, on_delete=models.PROTECT, db_constraint=False)
        SCOPE_OWNER = "owner"
        SCOPE_LINE = None

    class Inward(ScopedModel):
        id = models.UUIDField(primary_key=True)
        owner_user_id = models.UUIDField()
        SCOPE_OWNER = "owner_user_id"
        SCOPE_LINE = None

    class Note(TenantModel):
        id = models.UUIDField(primary_key=True)
        row = models.ForeignKey(Inward, models.PROTECT)
        hidden = models.ForeignKey(Hidden, models.PROTECT, related_name="+")

    assert scope_errors(Hidden) == []
    assert scope_errors(Outward) == ["scope.E003"]
    assert scope_errors(Inward) == ["scope.E003"]


def test_org_max_depth_is_the_tree_guards() -> None:
    guard = importlib.import_module("accounts.migrations.0027_tree_system_role_guards")
    assert ORG_MAX_DEPTH == guard.ORG_MAX_DEPTH == 32
