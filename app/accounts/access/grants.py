"""Grant evaluation (slice spec Decisions 6, 7 (ii)-(iii), 8, 36; plan row M4r-2a).

`grants(user_id, code)` reads the user's grants for one catalogue code from the stored ticks: one
statement, `user_role ⨝ role_permission` on (agency_id, role_id), in the caller's with_agency()
transaction, so RLS limits it to the bound agency. Every call reads the tables again (nothing is
cached), so a tick, untick or unassignment takes effect on the next call (AUTH-12). The statement
never reads `role`: a role's name and system flag are not authorization input (Decision 36).

One grant per (assignment, tick) pair, never merged (Decision 8): the scope from the tick,
org_unit_id and line from the assignment, step-up from the code catalogue for (code, scope). A
stored pair the code catalogue lacks is dropped and logged (fail closed; the FK to `permission`
and the live catalogue test make it unreachable). Matching the action's line and the step-up
check are the wrapper's role step.
"""

import logging
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from django.db import connection

from accounts.access.catalogue import CATALOGUE, Scope
from accounts.access.tables import Line
from accounts.auth.transactions import require_open

log = logging.getLogger("django.security.grants")
QUERY: Final = (
    "SELECT rp.scope, ur.org_unit_id, ur.line FROM user_role ur"
    " JOIN role_permission rp ON rp.agency_id = ur.agency_id AND rp.role_id = ur.role_id"
    " WHERE ur.user_id = %s AND rp.permission_code = %s"
)


@dataclass(frozen=True)
class Grant:
    scope: Scope
    org_unit_id: UUID
    line: Line
    stepup: str | None  # the step-up purpose the wrapper requires, or None


def grants(user_id: UUID, code: str) -> frozenset[Grant]:
    """The user's grants for `code` in the bound agency; empty for a user with no assignment.
    Raises ValueError for a code outside the catalogue (the self-service `auth.*` codes are not
    in it: every user holds them, Decision 6), and outside an atomic block."""
    if code not in CATALOGUE:
        raise ValueError("grants() takes a permission catalogue code")
    require_open("grants()")
    allowed = CATALOGUE[code]
    with connection.cursor() as cursor:
        cursor.execute(QUERY, [user_id, code])
        rows: list[tuple[str, UUID, str]] = cursor.fetchall()
    found = set[Grant]()
    for scope, org_unit_id, line in rows:
        if scope not in allowed:
            log.warning("grant dropped: %s %s is not a catalogue pair", code, scope)
            continue
        tick = cast(Scope, scope)
        found.add(Grant(tick, org_unit_id, cast(Line, line), allowed[tick]))
    return frozenset(found)
