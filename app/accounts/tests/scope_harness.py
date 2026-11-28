"""The scope test harness (slice spec Decision 10; plan row M4r-4, M4r-4a, M4r-4b). Apps list their
`ScopedModel` subclasses as `CASES` in `<app>/tests/scope_cases.py`, found by name as the TEN-08
cases are; the coverage test fails for a concrete `ScopedModel` without a case. A case's
`insert(cursor, agency_id, owner)` adds one row as skiw_app and returns its id; `visibility(case)`
is the generated check each case runs (test_access_scope_live)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from django.apps import apps
from django.apps.registry import Apps
from django.utils import timezone

from accounts.access.grants import Grant
from accounts.access.scope import ScopedModel, scoped
from accounts.auth.wrapper import Signed
from accounts.tests.test_access_audit_live import app, fresh_agency
from tenancy.binding import with_agency
from tenancy.tests.isolation import Executes, case_modules


@dataclass(frozen=True)
class ScopeCase:
    model: type[ScopedModel]
    insert: Callable[[Executes, uuid.UUID, uuid.UUID | None], uuid.UUID]


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


# The standard tree: unit -> parent, and user -> the unit of their one assignment (any role: the
# role has no tick at all, since scoped() never reads one).
UNITS = {"R": None, "U": "R", "V": "R", "X": "U", "Y": "U", "X1": "X"}
PEOPLE = {"me": "X", "mate": "X1", "sib": "Y", "boss": "U", "other": "V"}
UNIT = "INSERT INTO org_unit (id, agency_id, parent_id, kind, name) VALUES (%s, %s, %s, %s, 'U')"
USER = "INSERT INTO app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, 'U')"
ROLE = "INSERT INTO role (id, agency_id, name) VALUES (%s, %s, 'Scope test')"
HOLD = (
    "INSERT INTO user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
    " VALUES (gen_random_uuid(), %s, %s, %s, %s, 'both')"
)


def tree(agency: uuid.UUID) -> dict[str, uuid.UUID]:
    """The standard tree in `agency`, committed as skiw_app; every unit's and user's id by name."""
    ids = {name: uuid.uuid4() for name in [*UNITS, *PEOPLE, "role"]}
    with app(agency) as cursor:
        for unit, parent in UNITS.items():
            kind = "unit" if parent else "agency"
            cursor.execute(UNIT, [ids[unit], agency, parent and ids[parent], kind])
        cursor.execute(ROLE, [ids["role"], agency])
        for person, unit in PEOPLE.items():
            cursor.execute(USER, [ids[person], agency, f"{ids[person]}@scope.test"])
            cursor.execute(HOLD, [agency, ids[person], ids["role"], ids[unit]])
    return ids


def signed(user: uuid.UUID, agency: uuid.UUID, *access: Grant) -> Signed:
    now = timezone.now()
    return Signed(user, agency, "totp", now, now, frozenset(access))


def grant(scope: object, unit: object, line: object = "both") -> Grant:
    return Grant(scope, unit, line, None)  # type: ignore[arg-type]  # tampered values too


def visibility(case: ScopeCase) -> None:
    """Decision 9 on the standard tree: a row owned by each person, one with no owner and one in
    another agency; each access sees exactly its rows, in the caller's with_agency() only."""
    a, b = fresh_agency(), fresh_agency()
    ids, elsewhere = tree(a), tree(b)
    with app(a) as cursor:
        rows = {person: case.insert(cursor, a, ids[person]) for person in PEOPLE}
        rows["nobody"] = case.insert(cursor, a, None)
    with app(b) as cursor:
        case.insert(cursor, b, elsewhere["me"])
    team = {unit: grant("team", ids[unit]) for unit in UNITS}
    own, agency = grant("own", ids["X"]), grant("agency", ids["X"])
    tampered = (
        [grant(s, ids["X"]) for s in ("Agency", "all", None)]
        + [grant("agency", ids["X"], line) for line in ("any", "Both", None)]
        + [grant("team", str(ids["X"]))]
    )
    expected: list[tuple[list[Grant], set[str]]] = [
        ([], set()),
        (tampered, set()),
        ([own], {"me"}),
        ([team["X"]], {"me", "mate"}),
        ([team["X1"]], {"mate"}),
        ([team["U"]], {"me", "mate", "sib", "boss"}),
        ([team["R"]], set(PEOPLE)),
        ([own, team["V"]], {"me", "other"}),
        ([team["X"], team["Y"], *tampered], {"me", "mate", "sib"}),
        ([agency], {*PEOPLE, "nobody"}),
        ([own, agency, team["V"]], {*PEOPLE, "nobody"}),
    ]
    for access, people in expected:
        with with_agency(a):
            found = scoped(case.model, signed(ids["me"], a, *access))
            assert set(found.values_list("pk", flat=True)) == {rows[p] for p in people}, access
        assert list(found.values_list("pk", flat=True)) == []  # RLS: no binding any more
    for access in ([own], [agency]):  # the same user's access read in another agency's binding
        with with_agency(b):
            assert list(scoped(case.model, signed(ids["me"], a, *access))) == []
