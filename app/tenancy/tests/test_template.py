"""The tenant-table template (plan M4c-6a): the SQL is the spec §4.2 text, each step reverses
exactly, and names are checked."""

import re
from pathlib import Path

import pytest
from django_migration_linter.sql_analyser.analyser import analyse_sql_statements
from django_migration_linter.sql_analyser.postgresql import PostgresqlAnalyser

from tenancy.template import PREDICATE, Step, tenant_table, tenant_table_sql

SPEC = Path(__file__).resolve().parents[3] / "docs/specs/2026-10-05-skiw-platform-stack-design.md"
ALL = {"SELECT", "INSERT", "UPDATE", "DELETE"}


def steps(table: str, **kwargs: object) -> list[tuple[list[str], list[str]]]:
    pairs: list[Step] = tenant_table_sql(table, **kwargs)  # type: ignore[arg-type]
    return [(list(forward), list(reverse)) for forward, reverse in pairs]


def spec_policy_block() -> list[str]:
    """The §4.2 code block for table `t`, one statement per item, whitespace collapsed and the
    `(…same…)` shorthand written out."""
    text = SPEC.read_text()
    section = text[text.index("### 4.2 RLS policy") :]
    start = section.index("```sql") + len("```sql")
    block = section[start : section.index("```", start)]
    code = " ".join(line.split("--")[0] for line in block.splitlines())
    code = code.replace("(…same…)", f"({PREDICATE})")
    return [re.sub(r"\s+", " ", s).strip() for s in code.split(";") if s.strip()]


def test_the_rls_statements_are_the_spec_text() -> None:
    sql = [statement for forward, _ in steps("t", commands=ALL) for statement in forward]
    rls = [s for s in sql if "ROW LEVEL SECURITY" in s or s.startswith("CREATE POLICY")]
    assert rls == spec_policy_block()


def test_every_step_and_its_exact_reverse() -> None:
    p = PREDICATE
    assert steps("client_note", commands=ALL, composite_fks=[("client_id", "client")]) == [
        (
            [
                "ALTER TABLE client_note ADD CONSTRAINT client_note_agency_fk"
                " FOREIGN KEY (agency_id) REFERENCES agency(id)"
            ],
            ["ALTER TABLE client_note DROP CONSTRAINT client_note_agency_fk"],
        ),
        (
            [
                "ALTER TABLE client_note ADD CONSTRAINT client_note_client_id_fk"
                " FOREIGN KEY (agency_id, client_id) REFERENCES client(agency_id, id)"
            ],
            ["ALTER TABLE client_note DROP CONSTRAINT client_note_client_id_fk"],
        ),
        (
            [
                "ALTER TABLE client_note ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE client_note FORCE ROW LEVEL SECURITY",
                "CREATE POLICY client_note_tenant ON client_note AS RESTRICTIVE FOR ALL"
                f" TO skiw_app USING ({p}) WITH CHECK ({p})",
            ],
            [
                "DROP POLICY client_note_tenant ON client_note",
                "ALTER TABLE client_note NO FORCE ROW LEVEL SECURITY",
                "ALTER TABLE client_note DISABLE ROW LEVEL SECURITY",
            ],
        ),
        (
            [f"CREATE POLICY client_note_sel ON client_note FOR SELECT TO skiw_app USING ({p})"],
            ["DROP POLICY client_note_sel ON client_note"],
        ),
        (
            [
                "CREATE POLICY client_note_ins ON client_note FOR INSERT TO skiw_app"
                f" WITH CHECK ({p})"
            ],
            ["DROP POLICY client_note_ins ON client_note"],
        ),
        (
            [
                "CREATE POLICY client_note_upd ON client_note FOR UPDATE TO skiw_app"
                f" USING ({p}) WITH CHECK ({p})"
            ],
            ["DROP POLICY client_note_upd ON client_note"],
        ),
        (
            [f"CREATE POLICY client_note_del ON client_note FOR DELETE TO skiw_app USING ({p})"],
            ["DROP POLICY client_note_del ON client_note"],
        ),
        (
            ["GRANT SELECT, INSERT, UPDATE, DELETE ON client_note TO skiw_app"],
            ["REVOKE SELECT, INSERT, UPDATE, DELETE ON client_note FROM skiw_app"],
        ),
    ]


def test_an_append_only_table_gets_no_update_or_delete_policy_or_grant() -> None:
    sql = " ".join(
        s for forward, _ in steps("audit_event", commands=["INSERT", "SELECT"]) for s in forward
    )
    assert "audit_event_sel" in sql and "audit_event_ins" in sql
    assert "FOR UPDATE" not in sql and "FOR DELETE" not in sql
    assert "GRANT SELECT, INSERT ON audit_event TO skiw_app" in sql


@pytest.mark.parametrize(
    ("table", "kwargs"),
    [
        ("Client", {}),
        ("client; DROP TABLE agency", {}),
        ("x" * 64, {}),
        ("x" * 56, {}),  # the table fits, "<table>_agency_fk" does not
        ("agency", {}),
        ("client", {"commands": []}),
        ("client", {"commands": ["SELECT", "TRUNCATE"]}),
        ("client", {"composite_fks": [("agency_id", "client")]}),
        ("client", {"composite_fks": [("owner_id", "agency")]}),
        ("client", {"composite_fks": [("owner_id", "app_user"), ("owner_id", "org_unit")]}),
        ("client", {"composite_fks": [("owner_id", "app_user(id); --")]}),
    ],
)
def test_bad_names_and_arguments_are_refused(table: str, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="tenant_table"):
        tenant_table(table, **{"commands": ALL, **kwargs})  # type: ignore[arg-type]


def test_the_migration_linter_passes_both_directions() -> None:
    pairs = steps("client_note", commands=ALL, composite_fks=[("client_id", "client")])
    for forward, reverse in pairs:
        for statements in (forward, reverse):
            errors, ignored, warnings = analyse_sql_statements(PostgresqlAnalyser, statements)
            assert (errors, ignored, warnings) == ([], [], [])
            assert all("%" not in s and "\n" not in s for s in statements)


def test_tenant_table_wraps_each_step_in_one_reversible_runsql() -> None:
    kwargs = {"commands": ALL, "composite_fks": [("client_id", "client")]}
    operations = tenant_table("client_note", **kwargs)  # type: ignore[arg-type]
    assert [(list(op.sql), list(op.reverse_sql)) for op in operations] == steps(  # type: ignore[arg-type]
        "client_note", **kwargs
    )
    assert all(op.reversible for op in operations)
