"""Pin the path excludes of semgrep/tenancy-boundaries.yml (plan M4c-2a-2; PR 84 review notes).

`semgrep --test` runs fixtures from semgrep/, outside app/, so it cannot see a `paths.exclude`
list. Widening one (for example to `/app/`) would turn a boundary off and every check would stay
green. These tests read the rule file as text and compare each exclude list with the plan's table.
The reader refuses any line under a rule's `paths:` that it does not know (an `include:` key, a
flow list such as `exclude: [/app/]`), so those ways to turn a rule off cannot pass either
(PR 85 review R1 P3).
"""

import re
from pathlib import Path

import pytest

RULES = Path(__file__).resolve().parents[2] / "semgrep" / "tenancy-boundaries.yml"

# Allowed paths per rule: plan docs/plans/2026-11-01-m4-core.md §3 M4c-2a, "Semgrep" table (M4c-4b
# rows added there). Spec TEN-09 row: both with_agency() and async_with_agency() set the token, so
# async_binding.py is allowed for the token rules. tenancy/tests sets forged tokens on purpose
# (PR 91 review R1 P3). Only settings, keys and the binding modules read the token key (PR 92
# review R1 P3). accounts/migrations is there on purpose: M3e's and M3g's lookup functions read
# lookup_decoy_key.
EXPECTED: dict[str, list[str]] = {
    "tenancy-guard-key-sql": [
        "/app/tenancy/keys.py",
        "/app/tenancy/migrations/",
        "/app/accounts/migrations/",
        "/app/tenancy/tests/",
        "/app/accounts/tests/",
    ],
    "tenancy-token-setting": [
        "/app/tenancy/binding.py",
        "/app/tenancy/async_binding.py",
        "/app/tenancy/tests/",
    ],
    "tenancy-set-config-name": [],
    "tenancy-token-mint-import": [
        "/app/tenancy/binding.py",
        "/app/tenancy/async_binding.py",
        "/app/tenancy/tests/",
    ],
    "tenancy-token-key-reader": [
        "/app/config/settings.py",
        "/app/tenancy/keys.py",
        "/app/tenancy/binding.py",
        "/app/tenancy/async_binding.py",
        "/app/tenancy/tests/",
    ],
    "tenancy-async-pool": ["/app/tenancy/async_binding.py"],
    "tenancy-no-session-setting": [],
}


def _excludes(text: str | None = None) -> dict[str, list[str]]:
    """Map each rule id to its `paths.exclude` entries, read line by line (no YAML library).

    A `paths` key must be exactly `    paths:` (a flow value, a quoted key or trailing text fails).
    Inside a `paths:` block only `exclude:` and its `- /app/...` items (and comments) are known.
    Anything else raises AssertionError, so a new key or a flow-style list cannot slip by.
    """
    found: dict[str, list[str]] = {}
    rule = None
    in_paths = False
    in_exclude = False
    for line in (RULES.read_text() if text is None else text).splitlines():
        if re.match(r"\s*(#|$)", line):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if in_paths and indent <= 4:
            in_paths = in_exclude = False
        if (m := re.match(r"  - id: (\S+)$", line)) is not None:
            rule = m.group(1)
            found[rule] = []
            in_paths = in_exclude = False
        elif (m := re.match(r"    [\"']?paths[\"']?\s*:(.*)$", line)) is not None:
            # Any other spelling (flow value, quoted key, trailing text) would turn the rule off
            # without the reader seeing it.
            assert line == "    paths:", f"paths must be a plain block key in {rule}: {line!r}"
            in_paths = True
        elif in_paths and line == "      exclude:":
            in_exclude = True
        elif (
            in_paths and in_exclude and (m := re.match(r"        - (/app/\S+)$", line)) is not None
        ):
            assert rule is not None
            found[rule].append(m.group(1))
        else:
            assert not in_paths, f"unknown line under paths: in {rule}: {line!r}"
    return found


def test_the_rule_set_is_exactly_the_planned_boundaries() -> None:
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


def _with_paths_block(block: str) -> str:
    return RULES.read_text().replace(
        "    paths:\n      exclude:\n        - /app/tenancy/async_binding.py\n    pattern-regex",
        f"    paths:\n{block}\n    pattern-regex",
    )


def test_the_reader_refuses_a_flow_style_exclude() -> None:
    text = _with_paths_block("      exclude: [/app/]")
    assert text != RULES.read_text()
    with pytest.raises(AssertionError, match="unknown line under paths"):
        _excludes(text)


def test_the_reader_refuses_an_include_key() -> None:
    text = _with_paths_block(
        "      include:\n        - /app/nothing/\n"
        "      exclude:\n        - /app/tenancy/async_binding.py"
    )
    assert text != RULES.read_text()
    with pytest.raises(AssertionError, match="unknown line under paths"):
        _excludes(text)


def test_the_reader_refuses_a_second_paths_key() -> None:
    text = _with_paths_block(
        "      exclude:\n        - /app/tenancy/async_binding.py\n      foo: bar"
    )
    with pytest.raises(AssertionError, match="unknown line under paths"):
        _excludes(text)


@pytest.mark.parametrize(
    "line",
    [
        "    paths: {exclude: [/app/]}",
        '    "paths":',
        "    'paths':",
        "    paths:   ",
        "    paths: # note",
        "    paths: null",
    ],
)
def test_the_reader_refuses_any_other_spelling_of_the_paths_key(line: str) -> None:
    text = RULES.read_text().replace(
        "    paths:\n      exclude:\n        - /app/tenancy/async_binding.py\n", f"{line}\n", 1
    )
    assert text != RULES.read_text()
    with pytest.raises(AssertionError, match="paths must be a plain block key"):
        _excludes(text)
