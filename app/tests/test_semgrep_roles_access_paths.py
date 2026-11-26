"""Pin the path excludes of semgrep/roles-access-only.yml (slice spec Decision 3; plan row M4r-2).
`semgrep --test` ignores `paths`, so a widened exclude would pass every fixture; the reader is
test_semgrep_tenancy_paths's, which refuses any other spelling of a `paths:` block."""

from pathlib import Path

from tests.test_semgrep_tenancy_paths import _excludes

RULE = Path(__file__).resolve().parents[2] / "semgrep" / "roles-access-only.yml"

# Decision 3: only accounts.access reads or writes the four tables and `permission`; the
# migrations create them and the tests set rows up by SQL on purpose.
EXPECTED = {
    "roles-access-only": [
        "/app/accounts/access/",
        "/app/accounts/migrations/",
        "/app/accounts/tests/",
        "/app/tenancy/tests/",
        "/app/jobs/tests/",
        "/app/tests/",
    ]
}


def test_the_excludes_are_exactly_decision_3s() -> None:
    assert _excludes(RULE.read_text()) == EXPECTED
