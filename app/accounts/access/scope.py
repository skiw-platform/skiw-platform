"""The scope boundary and `scoped()` (slice spec Decisions 9, 10, 27, flow 5.2; plan row M4r-4,
M4r-4a, M4r-4b). The line filter comes in M4r-4c.

`scoped(model, signed)` is the one read of a `ScopedModel`: the OR over `signed.access` of each
grant's scope filter, always within `signed.agency_id`; no grant, no rows. `agency` is every row of
the agency, `own` the rows `SCOPE_OWNER` names as the signed-in user's, `team` the rows owned by a
user with any assignment in the subtree of the grant's unit (the unit itself included). One
statement walks every team grant's subtree, eagerly, under RLS, never reading `role` or ticks; a
cycle, a walk past ORG_MAX_DEPTH levels below the unit (the unit is level 1) or a unit RLS cannot
see raises ScopeIntegrityError, logged with the ids only. A grant whose scope or line is outside
the catalogue's gives nothing. It is evaluated in the caller's with_agency(); RLS returns nothing
once that has closed. What it does not bound (writes by key, a cached QuerySet): DECISIONS M4r-4b.

A `ScopedModel` has one manager, `_unscoped`, so Django adds no `objects`; Semgrep `scoped-only`
rejects `_unscoped`, `_default_manager`, `_base_manager`, the manager attributes of `_meta` and a
directly built `QuerySet` (also `QuerySet[X](...)`) outside this module, where `scoped()` builds
its own. Every read through `_unscoped` raises, so Django's own (shortcuts, generic views,
`full_clean`, `get_next_by_<field>`) do too, and a model form or formset raises before it reads
another row or saves (a bound one through `TenantModel`'s `unique (agency_id, id)`, whose `validate`
reads the manager first); it may display a record already fetched (owner, 2026-11-27). Save, delete
and refresh use Django's base manager. A subclass declares `SCOPE_OWNER`, the owner id field, and
`SCOPE_LINE`, None until M4r-4c (else ImproperlyConfigured). `check()` (run by `migrate` and the
coverage test) refuses another manager, an owner that is neither a UUID field nor a foreign key to
`app_user`, a model without that constraint (stock, unconditional, field-based, not deferrable, on
it or a parent), any join to its rows (a relation into it, a `through` use, another model on its
table, a concrete parent) and a relation from it unless `related_name="+"` and `related_query_name`
holds `__` (Django resolves `+`)."""

import functools
import logging
import operator
from typing import TYPE_CHECKING, ClassVar, Final, Literal, NoReturn
from uuid import UUID

from django.core import checks
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import connection, models
from django.db.models import ForeignObjectRel, Q, QuerySet
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related import RelatedField

from accounts.access.grants import Grant
from accounts.access.tables import LINES
from accounts.auth.transactions import require_open
from accounts.user_model import AppUser
from tenancy.models import TenantModel

if TYPE_CHECKING:  # the wrapper imports accounts.access
    from accounts.auth.wrapper import Signed

log = logging.getLogger("django.security.scope")
ORG_MAX_DEPTH: Final = 32  # slice spec §8; the same cap as the tree guard (accounts.0027)
REFUSED: Final = "a ScopedModel is read only through scoped(), never every row of the agency"
# Every team grant's subtree in one walk, one level past the cap, so a deeper tree shows.
SUBTREE: Final = (
    "WITH RECURSIVE walk(anchor, id, n) AS ("
    "SELECT u.id, u.id, 1 FROM org_unit u WHERE u.agency_id = %(a)s AND u.id = ANY(%(anchors)s)"
    " UNION ALL SELECT w.anchor, u.id, w.n + 1 FROM walk w"
    " JOIN org_unit u ON u.agency_id = %(a)s AND u.parent_id = w.id WHERE w.n <= %(cap)s"
    ") CYCLE id SET is_cycle USING path"
    " SELECT w.anchor, bool_or(w.is_cycle), max(w.n),"
    " array_agg(DISTINCT ur.user_id) FILTER (WHERE ur.user_id IS NOT NULL) FROM walk w"
    " LEFT JOIN user_role ur ON ur.agency_id = %(a)s AND ur.org_unit_id = w.id GROUP BY w.anchor"
)


class ScopeIntegrityError(Exception):
    """The org-unit tree under a team grant has a cycle, is deeper than ORG_MAX_DEPTH or its unit
    cannot be seen (Decision 27): `scoped()` raises it and returns no rows."""


class Unscoped(models.Manager["ScopedModel"]):
    def get_queryset(self) -> NoReturn:
        raise TypeError(REFUSED)


class ScopedModel(TenantModel):
    SCOPE_OWNER: ClassVar[str]
    SCOPE_LINE: ClassVar[Literal["insurance", "investment"] | None]

    _unscoped = Unscoped()

    class Meta(TenantModel.Meta):
        abstract = True

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        owner = getattr(cls, "SCOPE_OWNER", None)
        if not isinstance(owner, str) or not owner:
            raise ImproperlyConfigured(f"{cls.__qualname__}: declare SCOPE_OWNER, the owner field")
        if getattr(cls, "SCOPE_LINE", "") is not None:
            raise ImproperlyConfigured(
                f"{cls.__qualname__}: SCOPE_LINE must be declared None until the line filter"
            )

    @classmethod
    def check(cls, **kwargs: object) -> list[checks.CheckMessage]:
        return [*super().check(**kwargs), *_scope_errors(cls)]


def _scope_errors(model: type[ScopedModel]) -> list[checks.CheckMessage]:
    errors: list[checks.CheckMessage] = []
    if [(m.name, type(m)) for m in model._meta.managers] != [("_unscoped", Unscoped)]:
        errors.append(checks.Error("a manager other than _unscoped", obj=model, id="scope.E001"))
    try:
        owner = model._meta.get_field(model.SCOPE_OWNER)
    except FieldDoesNotExist:
        owner = None
    if not (
        isinstance(owner, models.UUIDField)
        or (isinstance(owner, models.ForeignKey) and owner.related_model is AppUser)
    ):
        errors.append(
            checks.Error("SCOPE_OWNER names no user id field", obj=model, id="scope.E002")
        )
    validated = (c for m in (model, *model._meta.get_parent_list()) for c in m._meta.constraints)
    if not any(
        isinstance(c, models.UniqueConstraint)
        and getattr(type(c), "validate", None) is vars(models.UniqueConstraint)["validate"]
        and sorted(c.fields) == ["agency_id", "id"]
        and not (c.condition or c.deferrable)
        for c in validated
    ):
        message = "no TenantModel unique (agency_id, id), so a model form could save"
        errors.append(checks.Error(message, obj=model, id="scope.E005"))
    for field in model._meta.get_fields(include_hidden=True):
        if isinstance(field, ForeignObjectRel):
            message = f"{field.remote_field.model._meta.label}.{field.remote_field.name} joins it"
            errors.append(checks.Error(message, obj=model, id="scope.E003"))
        elif isinstance(field, RelatedField) and (
            field.remote_field.parent_link
            or not field.remote_field.hidden
            or LOOKUP_SEP not in field.related_query_name()
        ):
            message = f"{field.name}: a lookup on the related model can name it"
            errors.append(checks.Error(message, obj=model, id="scope.E004"))
    for other in model._meta.apps.get_models(include_auto_created=True):
        tables = {m._meta.db_table.strip('"').rpartition('"."')[2] for m in (model, other)}
        if len(tables) == 1 and other._meta.concrete_model is not model._meta.concrete_model:
            errors.append(checks.Error(f"{other._meta.label} reads it", obj=model, id="scope.E003"))
        for m2m in other._meta.local_many_to_many:
            if m2m.remote_field.through is model:
                message = f"{other._meta.label}.{m2m.name} joins it as a through model"
                errors.append(checks.Error(message, obj=model, id="scope.E003"))
    return errors


def scoped[M: ScopedModel](model: type[M], signed: "Signed") -> QuerySet[M, M]:
    """The rows of `model` that `signed.access` grants (flow 5.2). TypeError for a model that is
    not a concrete ScopedModel or a malformed `signed`; TransactionManagementError outside
    atomic()."""
    if not (isinstance(model, type) and issubclass(model, ScopedModel)) or model._meta.abstract:
        raise TypeError("scoped() takes a concrete ScopedModel")
    access, user, agency = signed.access, signed.user_id, signed.agency_id
    if not (isinstance(user, UUID) and isinstance(agency, UUID) and isinstance(access, frozenset)):
        raise TypeError("scoped() takes the wrapper's Signed")
    if not all(isinstance(g, Grant) for g in access):
        raise TypeError("scoped() takes the wrapper's Signed")
    require_open("scoped()")
    kept = [g for g in access if isinstance(g.line, str) and g.line in LINES]  # 4c: LINE_MATCHES
    rows = QuerySet[M, M](model=model).filter(agency_id=agency)
    if any(g.scope == "agency" for g in kept):
        return rows
    owner = model.SCOPE_OWNER
    match = [Q(**{owner: user})] if any(g.scope == "own" for g in kept) else []
    anchors = {g.org_unit_id for g in kept if g.scope == "team" and isinstance(g.org_unit_id, UUID)}
    if anchors:
        match.append(Q(**{f"{owner}__in": _subtree_users(agency, anchors)}))
    return rows.filter(functools.reduce(operator.or_, match)) if match else rows.none()


def _subtree_users(agency: UUID, anchors: set[UUID]) -> set[UUID]:
    """The users with any assignment in the subtrees of `anchors`, or ScopeIntegrityError."""
    with connection.cursor() as cursor:
        cursor.execute(SUBTREE, {"a": agency, "anchors": list(anchors), "cap": ORG_MAX_DEPTH})
        walked = {row[0]: row[1:] for row in cursor.fetchall()}
    users = set[UUID]()
    for anchor in sorted(anchors):
        looped, depth, held = walked.get(anchor, (None, 0, None))
        reason = "anchor" if looped is None else "cycle" if looped else "depth"
        if looped is not False or depth > ORG_MAX_DEPTH:
            log.error("scope integrity: %s, agency %s, unit %s", reason, agency, anchor)
            raise ScopeIntegrityError(reason)
        users.update(held or ())
    return users
