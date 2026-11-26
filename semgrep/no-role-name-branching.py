# Fixture for `semgrep --test semgrep/` (rule no-role-name-branching).
from django.db import connection, models
from django.db.models import F, Q

from accounts.access.grants import grants
from accounts.access.tables import OrgUnit, Role, UserRole


def banned(role, assignment, user, name, kind):
    # ruleid: no-role-name-branching
    seen = [name == "owner"]
    # ruleid: no-role-name-branching
    seen.append("Owner" != name)  # noqa: SIM300
    # ruleid: no-role-name-branching
    seen.append(name.lower() == "unit_manager")
    # ruleid: no-role-name-branching
    seen.append(name.strip() == "Unit manager")
    # ruleid: no-role-name-branching
    seen.append(name in ("Adviser", "x"))
    # ruleid: no-role-name-branching
    seen.append(name not in ["STAFF"])
    # ruleid: no-role-name-branching
    seen.append(name in {"general"})
    # ruleid: no-role-name-branching
    seen.append("owner" in kind)
    match name:
        # ruleid: no-role-name-branching
        case "Owner":
            seen.append(True)
        # ruleid: no-role-name-branching
        case "x" | "adviser":
            seen.append(True)
        # ruleid: no-role-name-branching
        case {"role": "Owner"}:
            seen.append(True)
    # ruleid: no-role-name-branching
    seen.append(role.name)
    # ruleid: no-role-name-branching
    seen.append(assignment.role.name)
    # ruleid: no-role-name-branching
    seen.append(user.owner_role.name)
    # ruleid: no-role-name-branching
    seen.append(getattr(role, "name", None))
    # ruleid: no-role-name-branching
    seen.append(Role.objects.get(id=kind).name)
    # ruleid: no-role-name-branching
    seen.append(Role.objects.filter(id=kind).first().name)
    # ruleid: no-role-name-branching
    seen.append(Role._default_manager.get(id=kind).name)
    # ruleid: no-role-name-branching
    seen.append(Role._base_manager.all()[0].name)
    # ruleid: no-role-name-branching
    seen.append([r.name for r in Role.objects.all()])
    # ruleid: no-role-name-branching
    seen.append({r.name for r in Role._default_manager.filter(agency_id=kind)})
    # ruleid: no-role-name-branching
    seen.append({r.id: r.name for r in Role.objects.all()})
    # ruleid: no-role-name-branching
    seen.extend(r.name for r in Role._base_manager.all())
    for r in Role.objects.filter(agency_id=kind):
        # ruleid: no-role-name-branching
        seen.append(r.name)
    r = Role.objects.get(id=kind)
    # ruleid: no-role-name-branching
    seen.append(r.name)
    # ruleid: no-role-name-branching
    seen.append(role.is_system)
    # ruleid: no-role-name-branching
    seen.append(assignment.role.is_system)
    # ruleid: no-role-name-branching
    seen.append(getattr(assignment, "is_system", False))
    # ruleid: no-role-name-branching
    Role.objects.filter(name=name)
    # ruleid: no-role-name-branching
    Role.objects.get(name__iexact=name)
    # ruleid: no-role-name-branching
    Role.objects.all().exclude(name__in=[name])
    # ruleid: no-role-name-branching
    Role.objects.filter(is_system=True)
    # ruleid: no-role-name-branching
    Role.objects.filter(Q(is_system=kind))
    # ruleid: no-role-name-branching
    Role.objects.values("name")
    # ruleid: no-role-name-branching
    Role.objects.filter(agency_id=kind).values_list("id", "is_system")
    # ruleid: no-role-name-branching
    Role.objects.order_by("-name")
    # ruleid: no-role-name-branching
    UserRole.objects.filter(role__name=name)
    # ruleid: no-role-name-branching
    UserRole.objects.filter(user=user, role__is_system=True)
    # ruleid: no-role-name-branching
    UserRole.objects.values_list("role__name", flat=True)
    # ruleid: no-role-name-branching
    UserRole.objects.annotate(label=F("role__name"))
    with connection.cursor() as cursor:
        # ruleid: no-role-name-branching
        cursor.execute("SELECT id FROM role WHERE is_system AND agency_id = %s", [kind])
    return seen


CONSTRAINTS = (
    # ok: no-role-name-branching
    models.UniqueConstraint(fields=["x"], condition=Q(is_system=True), name="one_system"),
)


def allowed(user, code, name, unit):
    # ok: no-role-name-branching
    seen = [code == "staff.manage", code in ("staff.view", "client.view"), name == "owners"]
    # ok: no-role-name-branching
    seen.append(unit.name == name)
    # ok: no-role-name-branching
    seen.append(OrgUnit.objects.get(id=code).name)
    # ok: no-role-name-branching
    seen.append([u.name for u in OrgUnit.objects.all()])
    for u in OrgUnit._default_manager.all():
        # ok: no-role-name-branching
        seen.append(u.name)
    r = Role.objects.get(id=code)
    r = unit
    # ok: no-role-name-branching
    seen.append(r.name)
    # ok: no-role-name-branching
    seen.append([r.id for r in Role.objects.all()])
    # ok: no-role-name-branching
    Role.objects.filter(agency_id=unit.agency_id).values("id")
    # ok: no-role-name-branching
    UserRole.objects.filter(role__id=code, org_unit__name=name)
    return seen, grants(user, code)
