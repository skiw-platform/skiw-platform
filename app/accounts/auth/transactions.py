"""The one guard for accounts.auth functions that write in the caller's with_agency() transaction
(recovery codes, step-up evidence; PR 138 R1 P3)."""

from django.db import connection
from django.db.transaction import TransactionManagementError


def require_open(what: str) -> None:
    """Raises unless a transaction is open, so a call outside the caller's with_agency() fails
    loudly instead of by RLS's empty answer. It checks only that a transaction is open, NOT that
    the tenant binding is set or names the right agency: that is with_agency()'s job, and RLS
    refuses every row without it."""
    if not connection.in_atomic_block:
        raise TransactionManagementError(f"{what} run inside the caller's with_agency()")
