"""The scope test harness (slice spec Decision 10; plan row M4r-4, M4r-4a). Apps list their
`ScopedModel` subclasses as `CASES` in `<app>/tests/scope_cases.py`, found by name as the TEN-08
cases are; the coverage test fails for a concrete `ScopedModel` without a case. The per-grant
visibility checks a case runs are M4r-4b's."""

from dataclasses import dataclass

from django.apps import apps
from django.apps.registry import Apps

from accounts.access.scope import ScopedModel
from tenancy.tests.isolation import case_modules


@dataclass(frozen=True)
class ScopeCase:
    model: type[ScopedModel]


def registry() -> dict[type[ScopedModel], ScopeCase]:
    """Every project app's `tests.scope_cases.CASES`, by model."""
    found: dict[type[ScopedModel], ScopeCase] = {}
    for module in case_modules("scope_cases"):
        for case in module.CASES:
            if case.model in found:
                raise ValueError(f"scope case {case.model._meta.label} is registered twice")
            found[case.model] = case
    return found


def scoped_models(registered: Apps = apps) -> list[type[ScopedModel]]:
    return [model for model in registered.get_models() if issubclass(model, ScopedModel)]


def uncovered(registered: Apps = apps) -> list[str]:
    cases = registry()
    return sorted(model._meta.label for model in scoped_models(registered) if model not in cases)
