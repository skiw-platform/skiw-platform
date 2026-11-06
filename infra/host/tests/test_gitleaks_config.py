"""The `skiw-secret-key-assignment` rule flags each M1 key name, and the label allowlist skips only
bare domain-separation labels, no wider than the labels that exist (UNI-07; PR 117 R1 P1, PR 118 R1
P2).

No fake secret is committed: values for the custom rule are random and generated at test time in a
temporary directory; values for `generic-api-key` are derived from fixed hashes, because that rule
skips a value that happens to contain a common word and a random one would fail a run now and then.
Runs as `make secrets-test` in the CI `security` job, where gitleaks is installed.
"""

import base64
import hashlib
import json
import os
import secrets
import shutil
import string
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


# gitleaks' generic-api-key rule skips a value that contains a common word, so a *random* value is
# flagged only most of the time (a few runs in 100 for a 32-character one, about 1 in 6 for 40
# random letters). Values for that rule are derived from fixed hashes instead: the same on every
# run, no high-entropy literal in the source, and each is a finding under the pinned gitleaks.
def stream(name: str) -> bytes:
    return hashlib.sha512(f"skiw-gitleaks-label-test:{name}".encode()).digest()


def derived_letters(name: str, count: int) -> str:
    return "".join(string.ascii_lowercase[byte % 26] for byte in stream(name)[:count])


def derived_digits(name: str, count: int) -> str:
    return "".join(string.digits[byte % 10] for byte in stream(name)[:count])


def derived_urlsafe(name: str) -> str:
    return base64.urlsafe_b64encode(stream(name)).decode()[:32]


# Every label in app/, infra/, docs/ and scripts/ (grep `skiw(-[a-z0-9]+)+-v[0-9]+`): the allowlist
# must keep skipping each one.
LABELS = (
    "skiw-approval-v1",
    "skiw-blob-key-v1",
    "skiw-credential-v1",
    "skiw-decoy-login-v1",
    "skiw-enrol-v1",
    "skiw-factor-secret-v1",
    "skiw-login-v1",
    "skiw-recovery-v1",
    "skiw-reset-v1",
    "skiw-session-v1",
    "skiw-stepup-v1",
    "skiw-tenant-v1",
    "skiw-throttle-account-v1",
    "skiw-throttle-ip-v1",
    "skiw-throttle-lock-v1",
)


def test_a_bare_label_in_prose_passes(tmp_path: Path) -> None:
    lines = [
        f"It uses an HKDF subkey with its own info, `{label}`, so keys stay apart."
        for label in LABELS
    ]
    returncode, findings = scan(tmp_path, "\n".join(lines) + "\n")
    assert (returncode, findings) == (0, [])


def test_a_real_value_next_to_a_label_is_still_flagged(tmp_path: Path) -> None:
    value = derived_urlsafe("next-to")
    content = f'info = "skiw-factor-secret-v1"\nfactor_secret = "{value}"\n'
    returncode, findings = scan(tmp_path, content)
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]


def test_a_label_with_a_value_appended_is_still_flagged(tmp_path: Path) -> None:
    value = derived_urlsafe("appended")
    returncode, findings = scan(tmp_path, f'api_key = "skiw-factor-secret-v1-{value}"\n')
    assert returncode == 1
    assert [f["RuleID"] for f in findings] == ["generic-api-key"]


SHAPED_VALUES = {
    "hex": f"skiw-{stream('hex').hex()[:32]}-v1",
    "one-long-word": f"skiw-{derived_letters('one-long-word', 40)}-v1",
    "many-words": "skiw-" + "-".join(derived_letters(f"word-{n}", 3) for n in range(12)) + "-v1",
    "long-version": "skiw-factor-secret-v" + derived_digits("long-version", 30),
    "short-hex": f"skiw-{stream('short-hex').hex()[:12]}-v1",
}


@pytest.mark.parametrize("name", ["client_secret", "api_key"])
def test_a_random_value_in_the_label_shape_is_still_flagged(tmp_path: Path, name: str) -> None:
    """PR 118 R1 P2: `skiw-<hex>-v1` has the label's outline but not its words."""
    value = SHAPED_VALUES["hex"]
    returncode, findings = scan(tmp_path, f'{name} = "{value}"\n')
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]


@pytest.mark.parametrize("shape", ["one-long-word", "many-words", "long-version", "short-hex"])
def test_the_label_shape_is_limited_in_word_length_word_count_and_version(
    tmp_path: Path, shape: str
) -> None:
    value = SHAPED_VALUES[shape]
    returncode, findings = scan(tmp_path, f'api_key = "{value}"\n')
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]


def test_a_value_in_front_of_a_label_is_flagged(tmp_path: Path) -> None:
    value = f"{stream('prefix').hex()[:32]}-skiw-factor-secret-v1"
    returncode, findings = scan(tmp_path, f'api_key = "{value}"\n')
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]


def test_a_value_on_the_same_line_as_a_label_is_flagged(tmp_path: Path) -> None:
    value = derived_urlsafe("same-line")
    returncode, findings = scan(tmp_path, f'skiw-factor-secret-v1 = "{value}"\n')
    assert returncode == 1
    assert [f["Secret"] for f in findings] == [value]
