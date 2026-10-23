"""`skiw_host.labels` (CI `publish`; spec §8.4 H3 step 2; plan §3 M1h): the labels skiw-deploy
reads are built only from a well-formed `migration_labels` answer, in the format it compares."""

import io
import json

import pytest

from skiw_host import labels

COMMIT = "c5647a4c04ee4e19dda59cc02fbdc0528ae5ad56"
NAMES = {
    "head": ["jobs.0001_grants", "procrastinate.0041_post"],
    "contracts": ["jobs.0001_grants"],
    "migrations": ["jobs.0001_grants", "procrastinate.0040_pre", "procrastinate.0041_post"],
}


def run(argv: list[str], text: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = labels.main(argv, io.StringIO(text))
    return code, capsys.readouterr().out


def test_the_three_labels_in_the_format_skiw_deploy_compares(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = run([COMMIT], json.dumps(NAMES), capsys)
    assert code == 0
    assert out.splitlines() == [
        f"org.opencontainers.image.revision={COMMIT}",
        "skiw.migration-head=jobs.0001_grants,procrastinate.0041_post",
        "skiw.contract-migrations=jobs.0001_grants",
    ]


def test_no_contract_migration_gives_an_empty_label(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run([COMMIT], json.dumps(NAMES | {"contracts": []}), capsys)
    assert code == 0 and out.splitlines()[2] == "skiw.contract-migrations="


@pytest.mark.parametrize(
    ("argv", "text"),
    [
        ([COMMIT[:7]], json.dumps(NAMES)),
        ([COMMIT.upper()], json.dumps(NAMES)),
        ([], json.dumps(NAMES)),
        ([COMMIT, COMMIT], json.dumps(NAMES)),
        ([COMMIT], "not json"),
        ([COMMIT], json.dumps(NAMES)[:-1]),
        ([COMMIT], json.dumps(NAMES | {"extra": []})),
        ([COMMIT], json.dumps(NAMES | {"head": ["jobs.9999_not_shipped"]})),
        ([COMMIT], json.dumps(NAMES | {"head": ["jobs.0001_grants\nx=y"]})),
        ([COMMIT], json.dumps(NAMES | {"contracts": "jobs.0001_grants"})),
        ([COMMIT], " " * (labels.MAX_INPUT + 1)),
    ],
)
def test_anything_else_prints_no_label(
    argv: list[str], text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(argv, text, capsys)
    assert code == 1 and out == ""
