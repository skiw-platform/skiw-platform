"""Pin the path excludes of semgrep/no-role-name-branching.yml (slice spec Decision 36; plan row
M4r-2a). `semgrep --test` ignores `paths`, so a widened exclude would pass every fixture; the
reader is test_semgrep_tenancy_paths's, which refuses any other spelling of a `paths:` block."""

from pathlib import Path

from tests.test_semgrep_tenancy_paths import _excludes

RULE = Path(__file__).resolve().parents[2] / "semgrep" / "no-role-name-branching.yml"

# Decision 36: seed.py, changes.py, the two operator commands, migrations and tests.
EXPECTED = {
    "no-role-name-branching": [
        "/app/accounts/access/seed.py",
        "/app/accounts/access/changes.py",
        "/app/accounts/management/commands/accounts_role.py",
        "/app/accounts/management/commands/accounts_org.py",
        "/app/*/migrations/",
        "/app/*/tests/",
        "/app/tests/",
    ]
}


def test_the_excludes_are_exactly_decision_36s() -> None:
    assert _excludes(RULE.read_text()) == EXPECTED
