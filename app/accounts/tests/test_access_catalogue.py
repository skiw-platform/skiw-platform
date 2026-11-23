"""Golden test of the permission catalogue against slice spec §6.1 v2.5 (= main spec §6 v1.23):
codes, allowed scopes and step-up per pair (plan row M4r-1a; AUTH-03 as read by Decision 34). The
table below is copied from the spec by hand, not derived from the code, so a code change that
drifts from the spec fails here."""

import importlib

from accounts.access.catalogue import CATALOGUE, PAIRS, SCOPES, SELF_SERVICE

ALL = ("own", "team", "agency")
# code: {scope: step-up purpose or None}, row by row from §6.1.
SPEC_6_1 = {
    "client.view": dict.fromkeys(ALL),
    "client.edit": dict.fromkeys(ALL),
    "outbox.draft": dict.fromkeys(ALL),
    "outbox.approve": dict.fromkeys(ALL, "outbox.approve"),
    "drive.file": dict.fromkeys(ALL),  # S by D25 at the writer, not the wrapper
    "connector.connect": {"own": "connector.connect"},
    "bridge.run": {"own": None},
    "ai.chat": {"own": None},
    "settings.manage": {"agency": "settings.change"},
    "staff.manage": {"agency": "role_change"},
    "staff.view": {"team": None, "agency": None},
    "audit.view": dict.fromkeys(ALL),
    "data.export": dict.fromkeys(ALL, "export"),
    "device.revoke": {"own": None, "agency": "device.revoke"},
    "jobs.admin": {"agency": "jobs.admin"},
}


def test_the_catalogue_is_spec_6_1() -> None:
    assert {code: dict(scopes) for code, scopes in CATALOGUE.items()} == SPEC_6_1
    assert len(CATALOGUE) == 15
    assert len(PAIRS) == 31
    assert SCOPES == ALL


def test_the_self_service_group_is_fixed_and_not_tickable() -> None:
    expected = {"auth.logout", "auth.password", "auth.factors", "auth.factor-change", "auth.stepup"}
    assert expected == SELF_SERVICE
    assert not SELF_SERVICE & set(CATALOGUE)


def test_catalogue_migration_seeds_the_catalogue() -> None:
    """accounts.0019 freezes the pairs; it must hold exactly the catalogue's."""
    seed = importlib.import_module("accounts.migrations.0019_permission_catalogue")
    frozen = {(code, scope) for code, scopes in seed.PAIRS for scope in scopes}
    assert frozen == PAIRS
