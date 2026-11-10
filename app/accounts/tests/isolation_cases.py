"""TEN-08 isolation cases for the accounts tenant tables (plan M3 §3 M3d; the harness is
tenancy/tests/isolation.py, M4c-7a). `commands` repeat the RLS migrations' grants; each insert
names only the columns the row needs."""

import uuid
from collections.abc import Mapping

from django.db.backends.utils import CursorWrapper

from accounts.factor_model import TOTP_SECRET_CT_LENGTH
from accounts.stepup_model import EVIDENCE_LENGTH
from tenancy.tests.isolation import IsolationCase


def _app_user(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.app_user (id, agency_id, email, display_name) VALUES (%s, %s, %s, %s)",
        [row, agency, f"{row}@isolation.test", "Isolation user"],
    )
    return row


def _user_factor(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.user_factor (id, agency_id, user_id, kind, secret_ct)"
        " VALUES (%s, %s, %s, 'totp', %s)",
        [row, agency, parents["user_id"], b"\x00" * TOTP_SECRET_CT_LENGTH],  # accounts.0010
    )
    return row


def _session_revocation(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
) -> uuid.UUID:
    row = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.session_revocation (id, agency_id, user_id) VALUES (%s, %s, %s)",
        [row, agency, parents["user_id"]],
    )
    return row


def _auth_stepup(
    cursor: CursorWrapper, agency: uuid.UUID, parents: Mapping[str, uuid.UUID]
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
]
