"""SKIW_DEPLOYMENT_AGENCY_ID / _NAME (plan M4c-5, Q2 (a); PROJECT §9 second-agency gate)."""

import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env

AGENCY = "0d5f8e84-842e-4ac7-96c0-cdbd2facfdd2"


def test_one_uuid_and_a_name_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_ID", AGENCY)
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_NAME", "SK iWealth (staging)")
    assert env.deployment_agency() == (uuid.UUID(AGENCY), "SK iWealth (staging)")


@pytest.mark.parametrize(
    "value",
    [
        "",
        f"{AGENCY},{uuid.uuid4()}",  # a list: the second-agency gate is locked
        f"{AGENCY} {uuid.uuid4()}",
        AGENCY.upper(),
        f"{{{AGENCY}}}",
        f"urn:uuid:{AGENCY}",
        AGENCY.replace("-", ""),
        f" {AGENCY}",
        AGENCY[:-1],
    ],
    ids=["empty", "list", "two", "upper", "braces", "urn", "no-hyphens", "space", "short"],
)
def test_anything_but_one_canonical_uuid_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_ID", value)
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_NAME", "Local agency")
    with pytest.raises(ImproperlyConfigured, match="SKIW_DEPLOYMENT_AGENCY_ID") as caught:
        env.deployment_agency()
    assert "PROJECT §9" in str(caught.value)


def test_an_unset_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKIW_DEPLOYMENT_AGENCY_ID", raising=False)
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_NAME", "Local agency")
    with pytest.raises(ImproperlyConfigured, match="SKIW_DEPLOYMENT_AGENCY_ID"):
        env.deployment_agency()


@pytest.mark.parametrize("name", ["", " Local", "Local ", "a\tb", "a\nb", "x" * 201], ids=repr)
def test_a_bad_name_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_ID", AGENCY)
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_NAME", name)
    with pytest.raises(ImproperlyConfigured, match="SKIW_DEPLOYMENT_AGENCY_NAME"):
        env.deployment_agency()


def test_the_longest_name_fits_the_column(monkeypatch: pytest.MonkeyPatch) -> None:
    from tenancy.models import Agency

    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_ID", AGENCY)
    monkeypatch.setenv("SKIW_DEPLOYMENT_AGENCY_NAME", "x" * env.AGENCY_NAME_MAX)
    assert Agency._meta.get_field("name").max_length == env.AGENCY_NAME_MAX
    assert env.deployment_agency()[1] == "x" * env.AGENCY_NAME_MAX
