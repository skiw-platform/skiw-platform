"""Pin the path excludes of semgrep/tenancy-boundaries.yml (plan M4c-2a-2; PR 84 review notes).

`semgrep --test` runs fixtures from semgrep/, outside app/, so it cannot see a `paths.exclude`
list. Widening one (for example to `/app/`) would turn a boundary off and every check would stay
green. These tests read the rule file as text and compare each exclude list with the plan's table.
"""

import re
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "semgrep" / "tenancy-boundaries.yml"

# Allowed paths per rule: plan docs/plans/2026-11-01-m4-core.md §3 M4c-2a, "Semgrep" table.
# accounts/migrations is there on purpose: M3e's and M3g's lookup functions read lookup_decoy_key.
EXPECTED: dict[str, list[str]] = {
    "tenancy-guard-key-sql": [
        "/app/tenancy/keys.py",
        "/app/tenancy/migrations/",
        "/app/accounts/migrations/",
        "/app/tenancy/tests/",
        "/app/accounts/tests/",
    ],
    "tenancy-token-setting": ["/app/tenancy/binding.py", "/app/tenancy/async_binding.py"],
    "tenancy-async-pool": ["/app/tenancy/async_binding.py"],
    "tenancy-no-session-setting": [],
}


def _excludes() -> dict[str, list[str]]:
    """Map each rule id to its `paths.exclude` entries, read line by line (no YAML library)."""
    found: dict[str, list[str]] = {}
    rule = None
    in_exclude = False
    for line in RULES.read_text().splitlines():
        if (m := re.match(r"  - id: (\S+)$", line)) is not None:
            rule = m.group(1)
            found[rule] = []
            in_exclude = False
        elif re.match(r"      exclude:$", line):
            in_exclude = True
        elif in_exclude and (m := re.match(r"        - (\S+)$", line)) is not None:
            assert rule is not None
            found[rule].append(m.group(1))
        elif not re.match(r"\s*#", line) and not re.match(r"        - ", line):
            in_exclude = False
    return found


def test_the_rule_set_is_exactly_the_four_boundaries() -> None:
    assert set(_excludes()) == set(EXPECTED)


def test_every_exclude_list_is_exactly_the_plans_allowed_paths() -> None:
    assert _excludes() == EXPECTED


def test_no_exclude_is_a_wide_path() -> None:
    wide = {"/app/", "/app", "/app/tenancy/", "/app/accounts/", "app/", "/"}
    for rule, paths in _excludes().items():
        assert not wide & set(paths), rule
        assert all(p.startswith("/app/") and len(p) > len("/app/x") for p in paths), rule


def test_accounts_migrations_is_allowed_only_for_the_key_sql_rule() -> None:
    for rule, paths in _excludes().items():
        assert ("/app/accounts/migrations/" in paths) == (rule == "tenancy-guard-key-sql"), rule
