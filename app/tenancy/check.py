"""The tenancy schema check (spec §4.2 "Schema check (M4)"; plan M4c-6b; DECISIONS "M4c-6b-1").

Every relation of kind r, p, v, m or f outside `pg_*` and `information_schema` is a listed global
(tested first, so `bridge_session` with its `agency_id` is global), the tenant root `public.agency`,
or a tenant table (an `agency_id` column) of the `tenant_table()` shape. Anything else fails, and so
does any PUBLIC, `true` or `current_setting` policy. Predicates are compared as `pg_get_expr`
deparses them (plan A4; `guard` is never on `search_path`, so it stays qualified). All relations
are classified, so an FK is judged by its target; `schemas` limits only what is reported. Reasons
name tables, policies and constraints, never data.
"""

from dataclasses import dataclass
from typing import Any

import psycopg

from tenancy.schema import GLOBAL_TABLES, ROOT_TABLE
from tenancy.template import APP_ROLE

DEPARSED = "(agency_id = ( SELECT guard.current_agency() AS current_agency))"
ROOT_DEPARSED = "(id = ( SELECT guard.current_agency() AS current_agency))"
# Permissive (USING, WITH CHECK) per command, as `tenant_table()` writes them.
TEMPLATE = {
    "SELECT": (DEPARSED, None),
    "INSERT": (None, DEPARSED),
    "UPDATE": (DEPARSED, DEPARSED),
    "DELETE": (DEPARSED, None),
}
COMMANDS = {"r": "SELECT", "a": "INSERT", "w": "UPDATE", "d": "DELETE", "*": "ALL"}

RELATIONS = """
    SELECT c.oid, n.nspname, n.nspname || '.' || c.relname, c.relkind::text,
           c.relrowsecurity, c.relforcerowsecurity
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND NOT starts_with(n.nspname, 'pg_') AND n.nspname <> 'information_schema'
"""
COLUMNS = """
    SELECT attrelid, attname::text, format_type(atttypid, atttypmod), attnotnull
    FROM pg_attribute
    WHERE attnum > 0 AND NOT attisdropped AND attname IN ('id', 'agency_id')
"""
CONSTRAINTS = """
    SELECT con.conrelid, con.conname::text, con.contype::text, con.confrelid,
           ARRAY(SELECT a.attname::text FROM unnest(con.conkey) WITH ORDINALITY k(num, i)
                 JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.num
                 ORDER BY k.i),
           ARRAY(SELECT a.attname::text FROM unnest(con.confkey) WITH ORDINALITY k(num, i)
                 JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.num
                 ORDER BY k.i)
    FROM pg_constraint con WHERE con.contype IN ('p', 'u', 'f')
"""
POLICIES = """
    SELECT p.polrelid, p.polname::text, p.polpermissive, p.polcmd::text,
           ARRAY(SELECT CASE WHEN r = 0 THEN 'PUBLIC' ELSE r::regrole::text END
                 FROM unnest(p.polroles) r ORDER BY 1),
           pg_get_expr(p.polqual, p.polrelid), pg_get_expr(p.polwithcheck, p.polrelid)
    FROM pg_policy p
"""


@dataclass(frozen=True, order=True)
class Violation:
    table: str
    reason: str

    def __str__(self) -> str:
        return f"{self.table}: {self.reason}"


@dataclass(frozen=True)
class _Policy:
    name: str
    permissive: bool
    command: str
    roles: list[str]
    using: str | None
    check: str | None


@dataclass(frozen=True)
class _ForeignKey:
    name: str
    target: int
    columns: list[str]
    target_columns: list[str]


@dataclass
class _Relation:
    schema: str
    name: str
    kind: str
    rls: bool
    forced: bool
    columns: dict[str, tuple[str, bool]]
    keys: list[tuple[str, list[str]]]  # (contype, columns) of p and u constraints
    fks: list[_ForeignKey]
    policies: list[_Policy]


def check(
    conn: "psycopg.Connection[Any]",
    schemas: list[str] | None = None,
    extra_allowed: tuple[str, ...] = (),
) -> list[Violation]:
    """Every violation in `schemas` (all schemas when None), sorted. `extra_allowed` adds
    schema-qualified globals for tests only (`public.jobs_probe`, `public.files_probe`)."""
    relations = _load(conn)
    allowed = GLOBAL_TABLES | set(extra_allowed)
    tenant = {
        oid
        for oid, rel in relations.items()
        if rel.name not in allowed and rel.name != ROOT_TABLE and "agency_id" in rel.columns
        and rel.kind not in ("v", "m")
    }  # fmt: skip
    root = next((oid for oid, rel in relations.items() if rel.name == ROOT_TABLE), None)
    found: list[Violation] = []
    for oid, rel in relations.items():
        if schemas is not None and rel.schema not in schemas:
            continue
        reasons = _policy_rules(rel)
        if rel.name in allowed:
            pass
        elif rel.name == ROOT_TABLE:
            reasons += _root(rel)
        elif rel.kind in ("v", "m"):
            reasons.append("unlisted view")
        elif oid in tenant:
            reasons += _tenant(rel, relations, tenant, root)
        else:
            reasons.append("not on the global list and has no agency_id column")
        found += [Violation(rel.name, reason) for reason in reasons]
    return sorted(found)


def _load(conn: "psycopg.Connection[Any]") -> dict[int, _Relation]:
    relations = {
        oid: _Relation(schema, name, kind, rls, forced, {}, [], [], [])
        for oid, schema, name, kind, rls, forced in conn.execute(RELATIONS).fetchall()
    }
    for oid, column, type_name, not_null in conn.execute(COLUMNS).fetchall():
        if oid in relations:
            relations[oid].columns[column] = (type_name, not_null)
    for oid, name, kind, target, columns, target_columns in conn.execute(CONSTRAINTS).fetchall():
        if oid not in relations:
            continue
        if kind == "f":
            relations[oid].fks.append(_ForeignKey(name, target, columns, target_columns))
        else:
            relations[oid].keys.append((kind, columns))
    for oid, name, permissive, command, roles, using, check_ in conn.execute(POLICIES).fetchall():
        if oid in relations:
            policy = _Policy(name, permissive, COMMANDS[command], roles, using, check_)
            relations[oid].policies.append(policy)
    return relations


def _policy_rules(rel: _Relation) -> list[str]:
    reasons = []
    for policy in rel.policies:
        predicates = [p for p in (policy.using, policy.check) if p is not None]
        if "PUBLIC" in policy.roles:
            reasons.append(f"policy {policy.name} applies to PUBLIC")
        if any(p == "true" for p in predicates):
            reasons.append(f"policy {policy.name} has a true predicate")
        if any("current_setting" in p for p in predicates):
            reasons.append(f"policy {policy.name} reads current_setting directly")
    return reasons


def _rls(rel: _Relation) -> list[str]:
    if not rel.rls:
        return ["RLS not enabled"]
    return [] if rel.forced else ["RLS not forced"]


def _restrictive(rel: _Relation, predicate: str) -> list[str]:
    shape = ("ALL", [APP_ROLE], predicate, predicate)
    if any(
        (p.command, p.roles, p.using, p.check) == shape for p in rel.policies if not p.permissive
    ):
        return []
    return ["no restrictive tenant policy with USING and WITH CHECK"]


def _root(rel: _Relation) -> list[str]:
    reasons = []
    if ("p", ["id"]) not in rel.keys:
        reasons.append("id is not the primary key")
    if "agency_id" in rel.columns:
        reasons.append("the tenant root has an agency_id column")
    reasons += _rls(rel) + _restrictive(rel, ROOT_DEPARSED)
    permissive = [p for p in rel.policies if p.permissive]
    shape = ("SELECT", [APP_ROLE], ROOT_DEPARSED, None)
    if [(p.command, p.roles, p.using, p.check) for p in permissive] != [shape]:
        reasons.append("the tenant root needs exactly one permissive SELECT policy on id")
    return reasons


def _tenant(
    rel: _Relation, relations: dict[int, _Relation], tenant: set[int], root: int | None
) -> list[str]:
    reasons = []
    if "id" not in rel.columns:
        reasons.append("no id column")
    if rel.columns["agency_id"] != ("uuid", True):
        reasons.append("agency_id is not uuid not null")
    if not any(sorted(columns) == ["agency_id", "id"] for _, columns in rel.keys):
        reasons.append("no unique (agency_id, id)")
    reasons += _rls(rel) + _restrictive(rel, DEPARSED)
    for p in rel.policies:
        if p.permissive and (
            p.roles != [APP_ROLE] or TEMPLATE.get(p.command) != (p.using, p.check)
        ):
            reasons.append(f"permissive policy {p.name} is not template-shaped")
    agency_fk = (root, ["agency_id"], ["id"])
    if not any((fk.target, fk.columns, fk.target_columns) == agency_fk for fk in rel.fks):
        reasons.append("no FK (agency_id) to agency(id)")
    for fk in rel.fks:
        pairs = set(zip(fk.columns, fk.target_columns, strict=True))
        if fk.target in tenant and ("agency_id", "agency_id") not in pairs:
            target = relations[fk.target].name
            reasons.append(f"FK {fk.name} to tenant table {target} is not composite on agency_id")
    return reasons
