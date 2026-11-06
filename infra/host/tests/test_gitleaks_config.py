"""The `skiw-secret-key-assignment` rule flags each M1 key name, and the label allowlist skips only
bare domain-separation labels (UNI-07; PR 117 R1 P1).

Values are random and generated at test time in a temporary directory, so no fake secret is
committed. Runs as `make secrets-test` in the CI `security` job, where gitleaks is installed.
"""

import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
RULE_ID = "skiw-secret-key-assignment"
M1_KEY_NAMES = ("lookup_decoy_key", "field_kek", "blind_index_key", "crm_jar_kek")

pytestmark = pytest.mark.secrets


def gitleaks_binary() -> str:
    path = shutil.which("gitleaks")
    if path is not None:
        return path
    if os.environ.get("CI") == "true":
        pytest.fail("gitleaks is not on PATH in CI: the secrets test must run, not skip")
    pytest.skip("gitleaks is not installed locally (brew install gitleaks); CI runs this test")


# UNI-01 escape hatch: `Any` only types the findings that gitleaks writes to its JSON report. The
# fields are mixed (strings, numbers, nested lists) and belong to an external tool, so they are
# not modelled here; the tests read only `RuleID` and `Match` and assert on those two keys.
def scan(tmp_path: Path, content: str) -> tuple[int, list[dict[str, Any]]]:
    scanned = tmp_path / "scanned"
    scanned.mkdir()
    (scanned / "fixture.txt").write_text(content)
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            gitleaks_binary(),
            "dir",
            "--no-banner",
            "--config",
            str(REPO / ".gitleaks.toml"),
            "--report-format",
            "json",
            "--report-path",
            str(report),
            str(scanned),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    findings: list[dict[str, Any]] = json.loads(report.read_text()) if report.exists() else []
    return result.returncode, findings


def test_each_m1_key_name_with_a_value_is_one_finding(tmp_path: Path) -> None:
    lines = [f'{name} = "{secrets.token_urlsafe(24)}"' for name in M1_KEY_NAMES]
    returncode, findings = scan(tmp_path, "\n".join(lines) + "\n")
    assert returncode == 1
    flagged = [
        name
        for finding in findings
        if finding["RuleID"] == RULE_ID
        for name in M1_KEY_NAMES
        if finding["Match"].lower().startswith(name)
    ]
    assert sorted(flagged) == sorted(M1_KEY_NAMES)


def test_bare_m1_key_names_pass(tmp_path: Path) -> None:
    returncode, findings = scan(tmp_path, "\n".join(M1_KEY_NAMES) + "\n")
    assert (returncode, findings) == (0, [])


LABELS = (
    "skiw-factor-secret-v1",
    "skiw-recovery-v1",
    "skiw-throttle-account-v1",
    "skiw-blob-key-v1",
)


def test_a_bare_label_in_prose_passes(tmp_path: Path) -> None:
    lines = [
        f"It uses an HKDF subkey with its own info, `{label}`, so keys stay apart."
        for label in LABELS
    ]
    returncode, findings = scan(tmp_path, "\n".join(lines) + "\n")
    assert (returncode, findings) == (0, [])


def test_a_real_value_next_to_a_label_is_still_flagged(tmp_path: Path) -> None:
    value = secrets.token_urlsafe(24)
    content = f'info = "skiw-factor-secret-v1"\nfactor_secret = "{value}"\n'
    returncode, findings = scan(tmp_path, content)
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]


def test_a_label_with_a_value_appended_is_still_flagged(tmp_path: Path) -> None:
    value = secrets.token_urlsafe(24)
    returncode, findings = scan(tmp_path, f'api_key = "skiw-factor-secret-v1-{value}"\n')
    assert returncode == 1
    assert [f["RuleID"] for f in findings] == ["generic-api-key"]
