"""TEN-08 isolation cases for the accounts tenant tables (plan M3 §3 M3d; the harness is
tenancy/tests/isolation.py, M4c-7a). `commands` repeat the RLS migrations' grants; each insert
names only the columns the row needs."""

import json
import uuid
from collections.abc import Callable, Mapping

from accounts.factor_model import TOTP_SECRET_CT_LENGTH
from accounts.stepup_model import EVIDENCE_LENGTH
from accounts.tests import event_probe
from tenancy.tests.isolation import Executes, IsolationCase


def _app_user(cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, %s)",
        [row, agency, f"{row}@isolation.test", "Isolation user"],
    )
    return row


def _user_factor(
    cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.user_factor (id, agency_id, user_id, kind, secret_ct)"
        " VALUES (%s, %s, %s, 'totp', %s)",
        [row, agency, parents["user_id"], b"\x00" * TOTP_SECRET_CT_LENGTH],  # accounts.0010
    )
    return row


def _session_revocation(
    cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.session_revocation (id, agency_id, user_id) VALUES (%s, %s, %s)",
        [row, agency, parents["user_id"]],
    )
    return row


def _auth_stepup(
    cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.auth_stepup (id, agency_id, user_id, factor_id, purpose, verified_at,"
        " session_key_hash, evidence_mac) VALUES (%s, %s, %s, %s, 'factor.change', now(), %s, %s)",
        [
            row,
            agency,
            parents["user_id"],
            parents["factor_id"],
            "0" * 64,
            b"\x00" * EVIDENCE_LENGTH,
        ],
    )
    return row


def _role(cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.role (id, agency_id, name) VALUES (%s, %s, %s)",
        [row, agency, f"Isolation role {row}"],
    )
    return row


def _role_permission(
    cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.role_permission (id, agency_id, role_id, permission_code, scope)"
        " VALUES (%s, %s, %s, 'client.view', 'own')",
        [row, agency, parents["role_id"]],
    )
    return row


def _org_unit(cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    """With no parent: the agency's one root, made on first use and kept. Else a unit under it."""
    if "parent_id" not in parents:
        cursor.execute(
            "INSERT INTO public.org_unit (id, agency_id, kind, name)"
            " VALUES (gen_random_uuid(), %s, 'agency', 'Isolation agency') ON CONFLICT DO NOTHING",
            [agency],
        )
        cursor.execute(
            "SELECT id FROM public.org_unit WHERE agency_id = %s AND parent_id IS NULL", [agency]
        )
        return uuid.UUID(str(cursor.fetchone()[0]))
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.org_unit (id, agency_id, parent_id, kind, name)"
        " VALUES (%s, %s, %s, 'unit', 'Isolation unit')",
        [row, agency, parents["parent_id"]],
    )
    return row


type Insert = Callable[[Executes, uuid.UUID, Mapping[str, uuid.UUID]], uuid.UUID]


def _audited(insert: Insert) -> Insert:
    """For the roles tables, written by the owner until M4r-1g: their audit triggers (accounts.0028)
    need a skiw.operator and write security_event as the owner, so its FORCE is lifted around the
    insert and set again before the harness commits."""

    def run(cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
        cursor.execute("SELECT set_config('skiw.operator', 'test-operator', true)", [])
        cursor.execute("ALTER TABLE public.security_event NO FORCE ROW LEVEL SECURITY", [])
        row = insert(cursor, agency, parents)
        cursor.execute("ALTER TABLE public.security_event FORCE ROW LEVEL SECURITY", [])
        return row

    return run


def _change_event(
    cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    """Through the probe trigger (event_probe): only a trigger may write a change kind."""
    row = uuid.uuid4()
    details = json.dumps(event_probe.details("role.created"))
    cursor.execute(event_probe.INSERT, [row, "role.created", agency, None, None, details])
    return row


def _user_role(cursor: Executes, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.user_role (id, agency_id, user_id, role_id, org_unit_id, line)"
        " VALUES (%s, %s, %s, %s, %s, 'both')",
        [row, agency, parents["user_id"], parents["role_id"], parents["org_unit_id"]],
    )
    return row


USER = {"user_id": "public.app_user"}
CASES = [
    IsolationCase("public.app_user", _app_user, frozenset({"SELECT", "INSERT", "UPDATE"})),
    IsolationCase(
        "public.user_factor",
        _user_factor,
        frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
        USER,
    ),
    IsolationCase(
        "public.session_revocation", _session_revocation, frozenset({"SELECT", "INSERT"}), USER
    ),
    IsolationCase(
        "public.auth_stepup",
        _auth_stepup,
        frozenset({"SELECT", "INSERT"}),
        {**USER, "factor_id": "public.user_factor"},
    ),
    # SELECT only until M4r-1g: the harness writes their rows as the owner (tenancy isolation.py).
    # org_unit's self-FK: its parent is the agency root, made by `_org_unit` with no parents.
    IsolationCase("public.role", _audited(_role), frozenset({"SELECT"})),
    IsolationCase(
        "public.role_permission",
        _audited(_role_permission),
        frozenset({"SELECT"}),
        {"role_id": "public.role"},
    ),
    IsolationCase(
        "public.org_unit", _org_unit, frozenset({"SELECT"}), {"parent_id": "public.org_unit"}
    ),
    IsolationCase(
        "public.user_role",
        _audited(_user_role),
        frozenset({"SELECT"}),
        {**USER, "role_id": "public.role", "org_unit_id": "public.org_unit"},
    ),
    # Hand-registered (slice spec Decision 33, M4r-1c): security_event is a listed global, so the
    # coverage test does not ask for it; its change rows carry an agency and get these checks.
    IsolationCase("public.security_event", _change_event, frozenset({"SELECT", "INSERT"})),
]
