"""The tenancy schema check (spec §4.2 "Schema check (M4)"; plan M4c-6b; DECISIONS "M4c-6b-1").

Every relation of kind r, p, v, m or f outside `pg_*` and `information_schema` is a listed global
(tested first, so `bridge_session` with its `agency_id` is global), the tenant root `public.agency`,
or a tenant table (an `agency_id` column) of the `tenant_table()` shape. Anything else fails, and so
does any PUBLIC, `true` or `current_setting` policy. Predicates are compared as `pg_get_expr`
deparses them (plan A4; `guard` is never on `search_path`, so it stays qualified). The listed global
`security_event` has a named rule of its own (slice spec Decision 33). All relations
are classified, so an FK is judged by its target; `schemas` limits only what is reported. Reasons
name tables, policies and constraints, never data.
"""

from collections import Counter
from collections.abc import Set
from dataclasses import dataclass, field
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

# Decision 33 (M4r-1c): security_event is global with an optional agency. Exactly these policies,
# all TO skiw_app, as (permissive, command, USING, WITH CHECK): no UPDATE or DELETE policy.
SECURITY_EVENT = "public.security_event"
EVENT_DEPARSED = (
    "((agency_id IS NULL) OR (agency_id = ( SELECT guard.current_agency() AS current_agency)))"
)
EVENT_POLICIES = Counter(
    [
        (False, "ALL", EVENT_DEPARSED, EVENT_DEPARSED),
        (True, "SELECT", EVENT_DEPARSED, None),
        (True, "INSERT", None, EVENT_DEPARSED),
    ]
)
# The ten change kinds of Decision 30 (accounts.auth.tables.CHANGE_KINDS), as the CHECKs deparse.
_KINDS = (
    "role.created", "role.renamed", "role.deleted", "permission.set", "permission.unset",
    "role.assigned", "role.unassigned", "org.added", "org.moved", "org.renamed",
)  # fmt: skip
_CHANGE = (
    "((kind)::text = ANY ((ARRAY["
    + ", ".join(f"'{kind}'::character varying" for kind in _KINDS)
    + "])::text[]))"
)
EVENT_CHECKS = {
    "security_event_change_kind_agency": (
        f"CHECK ((({_CHANGE} AND (agency_id IS NOT NULL)) OR"
        f" ((NOT {_CHANGE}) AND (agency_id IS NULL))))"
    ),
    "security_event_change_kind_no_hmac": (
        f"CHECK (((NOT {_CHANGE}) OR ((email_hmac IS NULL) AND (ip_hmac IS NULL))))"
    ),
}
# Decision 32 (M4r-1c-ii): the BEFORE INSERT row trigger security_event_shape, enabled ('O': fires
# in the normal session_replication_role), on its SECURITY INVOKER function, as
# (tgenabled, tgtype, function, prosecdef); tgtype 7 = ROW (1) | BEFORE (2) | INSERT (4).
EVENT_TRIGGER = ("security_event_shape", ("O", 7, "public.security_event_shape", False))

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
CHECKS = """
    SELECT conrelid, conname::text, pg_get_constraintdef(oid)
    FROM pg_constraint WHERE contype = 'c' AND convalidated
"""
TRIGGERS = """
    SELECT t.tgrelid, t.tgname::text, t.tgenabled::text, t.tgtype::int,
           n.nspname || '.' || p.proname, p.prosecdef
    FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE NOT t.tgisinternal
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
    checks: dict[str, str] = field(default_factory=dict)  # validated CHECKs, as deparsed
    triggers: dict[str, tuple[str, int, str, bool]] = field(default_factory=dict)  # user triggers


def check(
    conn: "psycopg.Connection[Any]",
    schemas: list[str] | None = None,
    extra_allowed: tuple[str, ...] = (),
) -> list[Violation]:
    """Every violation in `schemas` (all schemas when None), sorted. `extra_allowed` adds
    schema-qualified globals for tests only (`public.jobs_probe`, `public.files_probe`)."""
    relations = _load(conn)
    allowed = GLOBAL_TABLES | set(extra_allowed)
    tenant = _tenant_oids(relations, allowed)
    root = next((oid for oid, rel in relations.items() if rel.name == ROOT_TABLE), None)
    found: list[Violation] = []
    for oid, rel in relations.items():
        if schemas is not None and rel.schema not in schemas:
            continue
        reasons = _policy_rules(rel)
        if rel.name == SECURITY_EVENT:
            reasons += _security_event(rel, root)
        elif rel.name in allowed:
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


def tenant_tables(conn: "psycopg.Connection[Any]", extra_allowed: tuple[str, ...] = ()) -> set[str]:
    """The schema-qualified names `check()` classifies as tenant tables (the TEN-08 coverage list,
    plan M4c-7a), compliant or not."""
    relations = _load(conn)
    allowed = GLOBAL_TABLES | set(extra_allowed)
    return {relations[oid].name for oid in _tenant_oids(relations, allowed)}


def _tenant_oids(relations: dict[int, "_Relation"], allowed: Set[str]) -> set[int]:
    return {
        oid
        for oid, rel in relations.items()
        if rel.name not in allowed and rel.name != ROOT_TABLE and "agency_id" in rel.columns
        and rel.kind not in ("v", "m")
    }  # fmt: skip


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
    for oid, name, definition in conn.execute(CHECKS).fetchall():
        if oid in relations:
            relations[oid].checks[name] = definition
    for oid, name, enabled, kind, function, definer in conn.execute(TRIGGERS).fetchall():
        if oid in relations:
            relations[oid].triggers[name] = (enabled, kind, function, definer)
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


def _security_event(rel: _Relation, root: int | None) -> list[str]:
    """Decision 33: RLS forced, a nullable agency_id with its FK, the change-kind CHECKs and
    exactly the three policies, so a missing IS NULL branch or an extra policy is a finding;
    Decision 32: the shape trigger, enabled."""
    reasons = _rls(rel)
    if rel.columns.get("agency_id") != ("uuid", False):
        reasons.append("agency_id is not nullable uuid")
    if not any(
        (fk.target, fk.columns, fk.target_columns) == (root, ["agency_id"], ["id"])
        for fk in rel.fks
    ):
        reasons.append("no FK (agency_id) to agency(id)")
    reasons += [
        f"CHECK {name} missing or changed"
        for name, definition in EVENT_CHECKS.items()
        if rel.checks.get(name) != definition
    ]
    shapes = Counter(
        (p.permissive, p.command, p.using, p.check) for p in rel.policies if p.roles == [APP_ROLE]
    )
    if shapes != EVENT_POLICIES or len(rel.policies) != len(EVENT_POLICIES):
        reasons.append("policies are not exactly the Decision 33 set")
    name, shape = EVENT_TRIGGER
    if rel.triggers.get(name) != shape:
        reasons.append(f"trigger {name} missing, not enabled or changed")
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
