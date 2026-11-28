"""Pin the path excludes of semgrep/scoped-only.yml (slice spec Decision 10; plan row M4r-4a).
`semgrep --test` ignores `paths`, so a widened exclude would pass every fixture; the reader is
test_semgrep_tenancy_paths's, which refuses any other spelling of a `paths:` block."""

from pathlib import Path

from tests.test_semgrep_tenancy_paths import _excludes

RULE = Path(__file__).resolve().parents[2] / "semgrep" / "scoped-only.yml"

# Decision 10: `_unscoped` only in accounts/access/scope.py; tests have no exclude either.
EXPECTED = {"scoped-only": ["/app/accounts/access/scope.py"]}


def test_the_excludes_are_exactly_decision_10s() -> None:
    assert _excludes(RULE.read_text()) == EXPECTED
