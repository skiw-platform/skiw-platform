"""`manage.py check_tenancy_schema` (plan M4c-6b) on the real database: ok on a clean schema; any
violation is printed as `<table>: <reason>` on stderr and fails the command."""

from functools import partial
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from tenancy import check as schema_check
from tenancy.management.commands import check_tenancy_schema as command
from tenancy.schema import GLOBAL_TABLES

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]

# Probe tables another test session may hold open (tests only, plan M4c-6b).
TEST_ONLY = ("public.jobs_probe", "public.files_probe")


def test_a_clean_schema_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command, "check", partial(schema_check.check, extra_allowed=TEST_ONLY))
    out, err = StringIO(), StringIO()
    call_command("check_tenancy_schema", stdout=out, stderr=err)
    assert (out.getvalue(), err.getvalue()) == ("tenancy schema check: ok\n", "")


def test_violations_are_printed_and_fail_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real check on the command's own connection, with two real globals taken off the list."""
    unlisted = {"public.django_migrations", "public.django_session"}
    monkeypatch.setattr(schema_check, "GLOBAL_TABLES", GLOBAL_TABLES - unlisted)
    monkeypatch.setattr(command, "check", partial(schema_check.check, extra_allowed=TEST_ONLY))
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError, match="tenancy schema check: 2 violations"):
        call_command("check_tenancy_schema", stdout=out, stderr=err)
    reason = "not on the global list and has no agency_id column"
    assert err.getvalue() == "".join(f"{table}: {reason}\n" for table in sorted(unlisted))
    assert out.getvalue() == ""
