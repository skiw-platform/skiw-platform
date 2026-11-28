"""Pin the exemptions of semgrep/operator-setting-changes-only.yml and
semgrep/role-changes-commands-only.yml (slice spec Decision 30; DECISIONS 2026-11-28 M4r-5a-i).

`semgrep --test` ignores `paths`, so a widened exclude would pass every fixture; the reader is
test_semgrep_tenancy_paths's. The owner's rule (2026-11-28): each exemption is one file, added in
the PR where that file needs it, never a folder. So each listed file must also exist and still hold
a string the rule's regex matches, and the line-level suppressions are pinned the same way.
"""

import ast
import re
from pathlib import Path

from tests.test_semgrep_tenancy_paths import _excludes

ROOT = Path(__file__).resolve().parents[2]
OPERATOR = ROOT / "semgrep" / "operator-setting-changes-only.yml"
IMPORTS = ROOT / "semgrep" / "role-changes-commands-only.yml"
RULE_IDS = ("operator-setting-changes-only", "role-changes-commands-only")

# The migrations whose trigger bodies read the setting (0025 names it in a comment only) and the
# accounts tests that set it on purpose. changes.py and its tests join in M4r-5a-ii and -iii.
EXPECTED = {
    "operator-setting-changes-only": [
        "/app/accounts/migrations/0028_role_audit_triggers.py",
        "/app/accounts/migrations/0029_org_unit_audit_trigger.py",
        "/app/accounts/tests/isolation_cases.py",
        "/app/accounts/tests/test_access_audit_live.py",
        "/app/accounts/tests/test_access_scope_live.py",
        "/app/accounts/tests/test_access_seed_live.py",
        "/app/accounts/tests/test_access_tables_live.py",
        "/app/accounts/tests/test_org_audit_live.py",
        "/app/accounts/tests/test_org_tables_live.py",
        "/app/accounts/tests/test_roles_audit_live.py",
        "/app/accounts/tests/test_roles_dml_forms_live.py",
        "/app/accounts/tests/test_roles_guards_live.py",
        "/app/accounts/tests/test_roles_tree_owner_live.py",
    ]
}
# No module may import accounts.access.changes yet; the two commands join in M4r-5b.
EXPECTED_IMPORTS: dict[str, list[str]] = {"role-changes-commands-only": []}
# Runtime code is suppressed line by line, not by file: file -> `# nosemgrep:` lines naming a rule.
SUPPRESSED = {"app/accounts/access/seed.py": 4}


def _named_lines(path: Path) -> set[int]:
    """First lines of the string literals (docstrings, bytes and f-string parts included) that the
    rule's own regex matches. Semgrep also folds `+` of literals; nothing listed here needs that."""
    (line,) = [x for x in OPERATOR.read_text().splitlines() if x.strip().startswith("regex: ")]
    pattern = re.compile(line.split("regex: ", 1)[1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str | bytes):
            value = node.value if isinstance(node.value, str) else node.value.decode("latin-1")
            if pattern.match(value):
                found.add(node.lineno)
    return found


def test_the_exemptions_are_exactly_the_owners_files() -> None:
    assert _excludes(OPERATOR.read_text()) == EXPECTED
    assert _excludes(IMPORTS.read_text()) == EXPECTED_IMPORTS


def test_every_exemption_is_one_existing_file() -> None:
    for path in EXPECTED["operator-setting-changes-only"]:
        assert not path.endswith("/"), path
        assert (ROOT / path.removeprefix("/")).is_file(), path


def test_every_exempt_file_still_names_the_setting() -> None:
    for path in EXPECTED["operator-setting-changes-only"]:
        assert _named_lines(ROOT / path.removeprefix("/")), f"{path} no longer needs its exemption"


def test_the_line_suppressions_are_exactly_the_seeds_and_each_is_needed() -> None:
    found: dict[str, list[int]] = {}
    for path in sorted((ROOT / "app").rglob("*.py")):
        for number, text in enumerate(path.read_text().splitlines(), start=1):
            comment = re.search(r"#\s*nosemgrep\b.*", text)
            if comment and any(rule in comment.group() for rule in RULE_IDS):
                found.setdefault(str(path.relative_to(ROOT)), []).append(number)
    assert {path: len(lines) for path, lines in found.items()} == SUPPRESSED
    for name, lines in found.items():
        named = _named_lines(ROOT / name)
        # Each suppression sits on the line just above the string it suppresses.
        assert all(number + 1 in named for number in lines), (name, lines, named)
