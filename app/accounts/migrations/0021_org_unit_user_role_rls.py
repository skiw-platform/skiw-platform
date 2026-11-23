# Grants and RLS for accounts.0020 (slice spec §4, Decisions 2, 3; plan row M4r-1b). Runs as
# skiw_migrator. Both are tenant tables through tenancy.template.tenant_table(), and skiw_app gets
# SELECT only: the INSERT, UPDATE and DELETE grants land in M4r-1g, after the roles lock, the tree
# guard and the audit triggers (Decision 32).
# The composite FKs are added here, not by the template, because the spec asks for ON DELETE
# RESTRICT. A root's NULL parent_id skips its FK (MATCH SIMPLE); every other row's parent must be
# a unit of the same agency.

from django.db import migrations

from tenancy.template import tenant_table


def _restrict(column: str, parent: str) -> str:
    target = f"{parent}(agency_id, id)"
    return f"FOREIGN KEY (agency_id, {column}) REFERENCES {target} ON DELETE RESTRICT"


FKS = (
    ("org_unit", "org_unit_parent_id_fk", _restrict("parent_id", "org_unit")),
    ("user_role", "user_role_user_id_fk", _restrict("user_id", "app_user")),
    ("user_role", "user_role_role_id_fk", _restrict("role_id", "role")),
    ("user_role", "user_role_org_unit_id_fk", _restrict("org_unit_id", "org_unit")),
)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_org_unit_user_role"),
    ]

    operations = [
        *tenant_table("org_unit", commands={"SELECT"}),
        *tenant_table("user_role", commands={"SELECT"}),
        *(
            migrations.RunSQL(
                sql=f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition}",
                reverse_sql=f"ALTER TABLE {table} DROP CONSTRAINT {name}",
            )
            for table, name, definition in FKS
        ),
    ]
