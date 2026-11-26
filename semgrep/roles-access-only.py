# Fixture for `semgrep --test semgrep/` (rule roles-access-only).
from django.apps import apps
from django.db import connection
from psycopg import sql

import accounts.access.tables
from accounts import models
from accounts.access import grants, tables
from accounts.access.tables import OrgUnit, Permission, Role, RolePermission, UserRole
from accounts.models import Role as Alias
from accounts.models import UserRole as Assigned


def orm(agency, user):
    # ruleid: roles-access-only
    Role.objects.filter(agency_id=agency)
    # ruleid: roles-access-only
    RolePermission.objects.all()
    # ruleid: roles-access-only
    UserRole.objects.filter(user_id=user).delete()
    # ruleid: roles-access-only
    OrgUnit._default_manager.get(parent=None)
    # ruleid: roles-access-only
    Permission._base_manager.count()
    # ruleid: roles-access-only
    Role._meta.default_manager.all()
    # ruleid: roles-access-only
    models.UserRole.objects.create(user_id=user)
    # ruleid: roles-access-only
    tables.OrgUnit.objects.all()
    # ruleid: roles-access-only
    accounts.access.tables.Role.objects.all()
    # ruleid: roles-access-only
    Alias.objects.update(name="x")
    # ruleid: roles-access-only
    Assigned.objects.bulk_create([])
    # ruleid: roles-access-only
    getattr(Role, "objects").all()  # noqa: B009
    # ruleid: roles-access-only
    Role(agency_id=agency, name="x").save()
    # ruleid: roles-access-only
    RolePermission(role_id=1, permission_code="client.view", scope="own")
    # ruleid: roles-access-only
    models.OrgUnit(kind="team")
    # ruleid: roles-access-only
    Alias(name="x")
    # ruleid: roles-access-only
    apps.get_model("accounts", "Role")
    # ruleid: roles-access-only
    apps.get_model("accounts", "userrole")
    # ruleid: roles-access-only
    apps.get_model("accounts.OrgUnit")


def passed_in(Role, Permission, RolePermission):
    # A model handed in (from apps.get_model, say) shadows the import: matched by its name.
    # ruleid: roles-access-only
    Role.objects.all()
    # ruleid: roles-access-only
    print(Permission._meta.db_table)
    # ruleid: roles-access-only
    RolePermission(role_id=1)


def raw():
    with connection.cursor() as cursor:
        # ruleid: roles-access-only
        cursor.execute("SELECT id FROM role WHERE agency_id = %s", [1])
        # ruleid: roles-access-only
        cursor.execute("select r.id from public.role r")
        # ruleid: roles-access-only
        cursor.execute('SELECT 1 FROM "role"')
        # ruleid: roles-access-only
        cursor.execute('SELECT 1 FROM "public"."permission"')
        # ruleid: roles-access-only
        cursor.execute("SELECT 1 FROM app_user u JOIN user_role ur ON ur.user_id = u.id")
        # ruleid: roles-access-only
        cursor.execute("SELECT 1 FROM app_user u, role r WHERE r.id = u.id")
        # ruleid: roles-access-only
        cursor.execute("INSERT INTO role_permission (role_id) VALUES (%s)", [1])
        # ruleid: roles-access-only
        cursor.execute("UPDATE role SET name = %s", ["x"])
        # ruleid: roles-access-only
        cursor.execute("UPDATE ONLY public.org_unit SET name = %s", ["x"])
        # ruleid: roles-access-only
        cursor.execute("DELETE FROM user_role WHERE id = %s", [1])
        # ruleid: roles-access-only
        cursor.execute("DELETE FROM ONLY permission")
        # ruleid: roles-access-only
        cursor.execute("TRUNCATE role")
        # ruleid: roles-access-only
        cursor.execute("TRUNCATE TABLE permission")
        # ruleid: roles-access-only
        cursor.execute("COPY role TO STDOUT")
        # ruleid: roles-access-only
        cursor.execute("MERGE INTO role r USING (VALUES (1)) v(id) ON r.id = v.id DO NOTHING")
        # ruleid: roles-access-only
        cursor.execute("LOCK TABLE role IN SHARE MODE")
        # ruleid: roles-access-only
        cursor.execute("lock role")
        # ruleid: roles-access-only
        cursor.execute("TABLE permission")
        # ruleid: roles-access-only
        cursor.execute("WITH t AS (SELECT 1) SELECT * FROM t JOIN Role ON true")
        # ruleid: roles-access-only
        cursor.execute("  -- the roles\n  SELECT 1 FROM role")
        # ruleid: roles-access-only
        cursor.execute("/* c */ select 1 from org_unit")
        cursor.execute(
            # ruleid: roles-access-only
            "SELECT 1 "  # one literal split over two lines; Semgrep also sees the second part
            # ruleid: roles-access-only
            "FROM role"
        )
    # ruleid: roles-access-only
    Role.objects.raw("SELECT * FROM role")
    # ruleid: roles-access-only
    query = "SELECT code, scope FROM permission"
    with connection.cursor() as cursor:
        # Semgrep's constant propagation: the variable holding the SQL is flagged where used.
        # ruleid: roles-access-only
        cursor.execute(query)
    # ruleid: roles-access-only
    sql.SQL("SELECT 1 FROM {}").format(sql.Identifier("role"))
    # ruleid: roles-access-only
    sql.Identifier("public", "user_role")


def allowed(agency, user):
    # The door: accounts.access functions, never the tables.
    # ok: roles-access-only
    grants.grants(user, "client.view")
    # Another model, a name only, a type or a manager-free attribute.
    # ok: roles-access-only
    models.AppUser.objects.filter(id=user)
    # ok: roles-access-only
    isinstance(agency, Role)
    # ok: roles-access-only
    print(Role.__name__)
    # ok: roles-access-only
    Roles.objects.all()  # noqa: F821
    # ok: roles-access-only
    apps.get_model("accounts", "AppUser")
    with connection.cursor() as cursor:
        # Another table whose name contains a role table's.
        # ok: roles-access-only
        cursor.execute("SELECT 1 FROM roles")
        # ok: roles-access-only
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", ["x"])
        # ok: roles-access-only
        cursor.execute("SELECT 1 FROM role_x")
        # ok: roles-access-only
        cursor.execute("SELECT 1 FROM org_units JOIN app_user_role ON true")
        # ok: roles-access-only
        cursor.execute("SELECT 1 FROM app_user WHERE role_id = %s", [1])
        # Role statements and catalog lookups, not the role table.
        # ok: roles-access-only
        cursor.execute("SET ROLE skiw_migrator")
        # ok: roles-access-only
        cursor.execute("SELECT has_table_privilege('role', 'SELECT')")
    # English prose naming the tables is not SQL, even when it starts with an SQL word.
    # ok: roles-access-only
    print("Remove the user from role Owner first, then update role names.")
    # ok: roles-access-only
    print("Grants come from permission ticks joined into user_role rows.")
    # ok: roles-access-only
    print("Copy permission lists by hand; lock role edits while a move runs.")
    # ok: roles-access-only
    print("Update role names from the M5 screen.")
    # ok: roles-access-only
    print("Delete user_role rows only through accounts.access.")
