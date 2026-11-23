# Grants and RLS for accounts.0017 (slice spec §4, Decisions 1, 3; plan row M4r-1a). Runs as
# skiw_migrator. skiw_app gets SELECT only on all three tables: the write grants land in M4r-1g,
# after the roles lock, the system-role guards and the audit triggers (Decision 32).
#   - `permission` is global (tenancy.schema): no RLS, the same rows for every agency, changed by
#     migration only.
#   - `role`, `role_permission`: tenant tables through tenancy.template.tenant_table().
#   - The composite FK (agency_id, role_id) -> role is added here, not by the template, because the
#     spec asks for ON DELETE RESTRICT; the FK (permission_code, scope) -> permission is plain.

from django.db import migrations

from tenancy.template import tenant_table

FKS = (
    (
        "role_permission_role_id_fk",
        "FOREIGN KEY (agency_id, role_id) REFERENCES role(agency_id, id) ON DELETE RESTRICT",
    ),
    (
        "role_permission_permission_fk",
        "FOREIGN KEY (permission_code, scope) REFERENCES permission(code, scope)",
    ),
)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_permission_role"),
    ]

    operations = [
        migrations.RunSQL(
            sql="GRANT SELECT ON permission TO skiw_app",
            reverse_sql="REVOKE SELECT ON permission FROM skiw_app",
        ),
        *tenant_table("role", commands={"SELECT"}),
        *tenant_table("role_permission", commands={"SELECT"}),
        *(
            migrations.RunSQL(
                sql=f"ALTER TABLE role_permission ADD CONSTRAINT {name} {definition}",
                reverse_sql=f"ALTER TABLE role_permission DROP CONSTRAINT {name}",
            )
            for name, definition in FKS
        ),
    ]
