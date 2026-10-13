from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}


def files_under(top: Path) -> list[str]:
    if not top.exists():
        return []
    return sorted(
        path.relative_to(REPO).as_posix()
        for path in top.rglob("*")
        if path.is_file() and not CACHE_NAMES.intersection(path.relative_to(REPO).parts)
    )


def test_nothing_under_infra_outside_infra_host() -> None:
    # Also catches the removed CDK skeleton coming back (spec v1.14, UNI-05).
    stray = [path for path in files_under(REPO / "infra") if not path.startswith("infra/host/")]
    assert stray == []


def test_scripts_holds_only_the_owner_deploy_wrapper() -> None:
    stray = [path for path in files_under(REPO / "scripts") if path != "scripts/deploy-prod"]
    assert stray == []
