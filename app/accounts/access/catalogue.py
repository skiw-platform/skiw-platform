"""The permission catalogue (slice spec §6.1 v2.5 = main spec §6 v1.23; Decisions 4, 6, 34).

Fixed in code: an admin ticks a `(code, scope)` pair on a role, never invents one. Each code maps
its allowed scopes to the step-up purpose the wrapper requires for that pair, or None.
Step-up is per pair, not per code: `device.revoke` needs it at `agency` only (Decision 4).
`drive.file` has none here because D25 checks it at the Drive writer, not the wrapper.

The `permission` table holds exactly these pairs (accounts.0019; a live test asserts equality), and
`role_permission`'s FK to it refuses any other pair. A new pair needs a migration that adds it.
"""

from collections.abc import Mapping
from typing import Final, Literal

Scope = Literal["own", "team", "agency"]
SCOPES: Final[tuple[Scope, ...]] = ("own", "team", "agency")


def _same(purpose: str | None, *scopes: Scope) -> dict[Scope, str | None]:
    return dict.fromkeys(scopes, purpose)


CATALOGUE: Final[Mapping[str, Mapping[Scope, str | None]]] = {
    "client.view": _same(None, *SCOPES),
    "client.edit": _same(None, *SCOPES),
    "outbox.draft": _same(None, *SCOPES),
    "outbox.approve": _same("outbox.approve", *SCOPES),
    "drive.file": _same(None, *SCOPES),
    "connector.connect": _same("connector.connect", "own"),
    "bridge.run": _same(None, "own"),
    "ai.chat": _same(None, "own"),
    "settings.manage": _same("settings.change", "agency"),
    "staff.manage": _same("role_change", "agency"),
    "staff.view": _same(None, "team", "agency"),
    "audit.view": _same(None, *SCOPES),
    "data.export": _same("export", *SCOPES),
    "device.revoke": {"own": None, "agency": "device.revoke"},
    "jobs.admin": _same("jobs.admin", "agency"),
}

PAIRS: Final[frozenset[tuple[str, Scope]]] = frozenset(
    (code, scope) for code, scopes in CATALOGUE.items() for scope in scopes
)

# Decision 6: route permissions every active user with a second factor holds, with or without a
# role. Not catalogue codes: they cannot be ticked or unticked.
SELF_SERVICE: Final[frozenset[str]] = frozenset(
    {"auth.logout", "auth.password", "auth.factors", "auth.factor-change", "auth.stepup"}
)

# What `authorized_action(permission=...)` accepts: a catalogue code or a self-service one.
ROUTE_CODES: Final[frozenset[str]] = frozenset(CATALOGUE) | SELF_SERVICE

# Decision 26: the business line an action declares. `any` = in no module the §6 line split
# names. An assignment's line (tables.Line) is matched against it by the wrapper's LINE_MATCHES.
ActionLine = Literal["insurance", "investment", "any"]
ACTION_LINES: Final[tuple[ActionLine, ...]] = ("insurance", "investment", "any")
