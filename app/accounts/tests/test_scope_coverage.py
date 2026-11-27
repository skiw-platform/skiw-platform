"""The scope coverage meta-test (slice spec Decision 10, as TEN-08's coverage check; plan row
M4r-4, M4r-4a): every concrete `ScopedModel` has a scope case and passes its system checks, and the
check names a model that has none."""

import sys
from types import ModuleType

import pytest
from django.db import models
from django.test.utils import isolate_apps

from accounts.access.scope import ScopedModel
from accounts.tests.scope_harness import ScopeCase, registry, scoped_models, uncovered
from tenancy.models import TenantModel


def test_every_scoped_model_has_a_scope_case_and_passes_its_checks() -> None:
    assert uncovered() == []
    assert [error for model in scoped_models() for error in model.check()] == []


def test_the_coverage_check_names_an_unregistered_model(monkeypatch: pytest.MonkeyPatch) -> None:
    with isolate_apps("accounts"):

        class Probe(ScopedModel):
            id = models.UUIDField(primary_key=True)
            owner_user_id = models.UUIDField()
            SCOPE_OWNER = "owner_user_id"
            SCOPE_LINE = None

        class Plain(TenantModel):
            id = models.UUIDField(primary_key=True)

        isolated = Probe._meta.apps
        assert scoped_models(isolated) == [Probe]
        assert uncovered(isolated) == ["accounts.Probe"]

        cases = ModuleType("accounts.tests.scope_cases")
        vars(cases)["CASES"] = [ScopeCase(Probe)]
        monkeypatch.setitem(sys.modules, cases.__name__, cases)
        assert registry() == {Probe: ScopeCase(Probe)}
        assert uncovered(isolated) == []

        vars(cases)["CASES"] = [ScopeCase(Probe), ScopeCase(Probe)]
        with pytest.raises(ValueError, match="registered twice"):
            registry()
