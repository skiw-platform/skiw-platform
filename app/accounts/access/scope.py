"""The scope boundary (slice spec Decisions 9, 10, 27; plan row M4r-4, M4r-4a). `scoped()`, the
subtree walk and the line filter come in M4r-4b and M4r-4c.

A `ScopedModel` has one manager, `_unscoped`, so Django adds no `objects`; Semgrep `scoped-only`
rejects `_unscoped`, `_default_manager`, `_base_manager`, the manager attributes of `_meta` and a
direct `QuerySet(...)` outside this module, where `scoped()` builds its `QuerySet`. Every read
through `_unscoped` raises, so Django's own (shortcuts, generic views, model forms and formsets,
`full_clean`, `get_next_by_<field>`) do too; save, delete and refresh use Django's base manager. A
subclass declares `SCOPE_OWNER`, the owner id field, and `SCOPE_LINE`, None until M4r-4c (else
ImproperlyConfigured). `check()` (run by `migrate` and the coverage test) refuses another manager,
an owner that is neither a UUID field nor a foreign key to `app_user`, any join to its rows (a
relation into it, a `through` use, another model on its table, a concrete parent) and a relation
from it unless `related_name="+"` and `related_query_name` holds `__` (Django resolves `+`)."""

from typing import ClassVar, Final, Literal, NoReturn

from django.core import checks
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import models
from django.db.models import ForeignObjectRel
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related import RelatedField

from accounts.user_model import AppUser
from tenancy.models import TenantModel

ORG_MAX_DEPTH: Final = 32  # slice spec §8; the same cap as the tree guard (accounts.0027)
REFUSED: Final = "a ScopedModel is read only through scoped(), never every row of the agency"


class ScopeIntegrityError(Exception):
    """The org-unit tree under a team grant has a cycle or is deeper than ORG_MAX_DEPTH (Decision
    27): `scoped()` raises it and returns no rows."""


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
