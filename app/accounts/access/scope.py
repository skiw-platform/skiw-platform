"""The scope boundary (slice spec Decisions 9, 10, 27; plan row M4r-4, M4r-4a). `scoped()`, the
subtree walk and the line filter come in M4r-4b and M4r-4c.

A `ScopedModel` has one manager, `_unscoped`, so Django adds no `objects`; Semgrep `scoped-only`
rejects `_unscoped`, `_default_manager`, `_base_manager`, the manager attributes of `_meta` and a
direct `QuerySet(...)` outside this module. A subclass declares `SCOPE_OWNER`, the field holding the
owner user's id, and `SCOPE_LINE`, which must be None until the line filter lands (M4r-4c); a bad
declaration raises ImproperlyConfigured when the class is defined. `check()` (run by `migrate` and
by the scope coverage test) refuses a second manager, an owner that is neither a UUID field nor a
foreign key to `app_user`, and any relation on or into the model with a reverse accessor
(related_name not '+'), since a reverse accessor reads rows without `scoped()`."""

from typing import ClassVar, Final, Literal

from django.core import checks
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import models
from django.db.models import ForeignObjectRel

from accounts.user_model import AppUser
from tenancy.models import TenantModel

ORG_MAX_DEPTH: Final = 32  # slice spec §8; the same cap as the tree guard (accounts.0027)


class ScopeIntegrityError(Exception):
    """The org-unit tree under a team grant has a cycle or is deeper than ORG_MAX_DEPTH (Decision
    27): `scoped()` raises it and returns no rows."""


class ScopedModel(TenantModel):
    SCOPE_OWNER: ClassVar[str]
    SCOPE_LINE: ClassVar[Literal["insurance", "investment"] | None]

    _unscoped = models.Manager()

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
    if [manager.name for manager in model._meta.managers] != ["_unscoped"]:
        errors.append(
            checks.Error("a scoped model has no manager but _unscoped", obj=model, id="scope.E001")
        )
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
        relation = field if isinstance(field, ForeignObjectRel) else field.remote_field
        if relation is not None and not relation.hidden:
            message = f"{field.name} has a reverse accessor"
            errors.append(checks.Error(message, obj=model, id="scope.E003"))
    return errors
