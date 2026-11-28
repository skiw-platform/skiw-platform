"""Pin the exemptions of semgrep/operator-setting-changes-only.yml and
semgrep/role-changes-commands-only.yml (slice spec Decision 30; DECISIONS 2026-11-28 M4r-5a-i).

`semgrep --test` ignores `paths`, so a widened exclude would pass every fixture; the reader is
test_semgrep_tenancy_paths's. The owner's rule (2026-11-28): each exemption is one file, added in
the PR where that file needs it, never a folder. So each listed file must also exist and still hold
a string the rule's regex matches, and the line-level suppressions are pinned the same way.

The scanner also accepts comments that silence every rule, a shorter word, any letter case and
other punctuation (PR 200 R1). So under app/ any line holding that word must end in the one scoped
spelling the repo uses; this file builds the word from parts so that it silences nothing itself.
"""

import ast
import re
from pathlib import Path

import pytest

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
# Runtime code is suppressed line by line, not by file: file -> comment lines naming a rule.
SUPPRESSED = {"app/accounts/access/seed.py": 4}
WORD = "nose" + "m"
ID = r"[a-z0-9][a-z0-9._-]*"
SCOPED = re.compile(rf"# {WORD}grep: ({ID}(?:, {ID})*)\Z")


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


def _silencers(text: str) -> tuple[list[int], list[int]]:
    """(lines whose comment is not the scoped spelling, lines whose comment names a pinned rule).
    Split on newlines only, as the scanner does."""
    refused, ours = [], []
    for number, line in enumerate(text.split("\n"), start=1):
        if WORD not in line.casefold():
            continue
        found = SCOPED.search(line)
        if found is None or line.casefold().count(WORD) != 1:
            refused.append(number)
        elif any(rule in found.group(1) for rule in RULE_IDS):
            ours.append(number)
    return refused, ours


@pytest.mark.parametrize(
    "comment",
    [
        f"# {WORD}grep",
        f"# {WORD}",
        f"# {WORD.upper()}GREP",
        f"#{WORD}grep",
        f"# {WORD}grep:",
        f"# {WORD}grep scoped-only",
        f"# {WORD}grep(scoped-only)",
        f"# {WORD}grep:  scoped-only",
        f"# {WORD}grep:scoped-only",
        f"# {WORD}grep={RULE_IDS[0]}",
        f"# {WORD}: {RULE_IDS[1]}",
        f"# {WORD.upper()}GREP: {RULE_IDS[0]}",
        f'# {WORD}grep: "{RULE_IDS[0]}"',
        f"# {WORD}grep: scoped-only,{RULE_IDS[0]}",
        f"# {WORD}grep: scoped-only  , {RULE_IDS[1]}",
        f"# {WORD}grep: scoped-only - reason",
        f"# {WORD}grep-ignore",
        f"# {WORD}antic",
        # One line to the scanner, two to str.splitlines().
        f"# {WORD}grep: scoped-only\u2028, {RULE_IDS[0]}",
        f'y = " {WORD}"  # {WORD}grep: scoped-only',
    ],
)
def test_a_blanket_or_differently_spelled_comment_is_refused(comment: str) -> None:
    assert _silencers(f"x = 1\nx = 2  {comment}\n") == ([2], [])


@pytest.mark.parametrize(
    ("ids", "pinned"),
    [
        ("scoped-only", False),
        ("scoped-only, tenancy-token-setting", False),
        (RULE_IDS[0], True),
        (RULE_IDS[1], True),
        (f"scoped-only, {RULE_IDS[0]}", True),
        (f"semgrep.{RULE_IDS[1]}", True),
    ],
)
def test_a_scoped_comment_counts_only_when_it_names_a_pinned_rule(ids: str, pinned: bool) -> None:
    assert _silencers(f"    # {WORD}grep: {ids}\n") == ([], [1] if pinned else [])


def test_the_line_suppressions_are_exactly_the_seeds_and_each_is_needed() -> None:
    refused: list[tuple[str, int]] = []
    found: dict[str, list[int]] = {}
    # Every file, not only *.py: the scanner also reads a script by its first line.
    for path in sorted((ROOT / "app").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        name = str(path.relative_to(ROOT))
        bad, ours = _silencers(path.read_text(errors="replace"))
        refused += [(name, number) for number in bad]
        if ours:
            found[name] = ours
    assert refused == [], f"end the line with `# {WORD}grep: rule-id[, rule-id]`"
    assert {path: len(lines) for path, lines in found.items()} == SUPPRESSED
    for name, lines in found.items():
        named = _named_lines(ROOT / name)
        # Each suppression sits on the line just above the string it suppresses.
        assert all(number + 1 in named for number in lines), (name, lines, named)
