"""Enrolment links (AUTH-08; plan M3 §3 M3e, §4 M3e row "enrolment link: works once, expired,
tampered, reused"), against the real tables as skiw_app. The route that calls `redeem` is M3e-3b."""

import threading
import time
import uuid
from collections.abc import Iterator
from io import StringIO
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core import signing
from django.core.management import CommandError, call_command
from django.db import connection
from pytest_django import Settings

from accounts.auth import blob, enrol, passwords
from accounts.auth.password_step import Verified, attempt
from accounts.user_model import AppUser
from tenancy.binding import with_agency

from .conftest import committed_user
from .logins import PASSWORD, SEALED, enrolled, random_ip, unknown, unseal

pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db")]


@pytest.fixture(autouse=True)
def unsealed(live_db: None) -> Iterator[None]:
    yield
    unseal()


def row(email: str) -> AppUser:
    agency, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    with with_agency(agency):
        return AppUser.objects.get(email=email)


def sealed(email: str) -> bytes:
    value = row(email).login_blob_ct
    assert value is not None
    return bytes(value)


def invited() -> tuple[str, str]:
    """A fresh invite: the email as stored and its link token. Its blob is cleared afterwards."""
    email = unknown()
    token = enrol.invite(email, "New User")
    SEALED.append(row(email))
    return email, token


def address(length: int) -> str:
    """A fresh address of exactly `length` characters that Django's validator accepts."""
    local = uuid.uuid4().hex
    domain = f"{'b' * 63}.{'c' * 63}.{'d' * 63}."
    return f"{local}@{domain}{'e' * (length - len(local) - 1 - len(domain))}"


def later(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    now = time.time() + seconds
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: now))


def test_an_invite_makes_an_invited_user_and_its_link_sets_the_password() -> None:
    email = unknown()
    token = enrol.invite(f"  {email.upper()} ", " Ann Lee ")
    user = row(email)  # stored as the lookup and the blob's AAD normalise it
    SEALED.append(user)
    assert (user.status, user.display_name, user.login_blob_ct) == ("invited", "Ann Lee", None)
    assert enrol.redeem(token, PASSWORD) == Verified(user.id, user.agency_id)
    after = row(email)
    record = blob.open_login(sealed(email), email)
    assert record is not None and (record.user_id, record.agency_id) == (user.id, user.agency_id)
    assert passwords.verify(record.password_hash, PASSWORD)
    assert after.status == "invited"  # the first second factor activates (M3f, M3g)
    assert attempt(email, PASSWORD, random_ip()) == "failed"  # a password alone signs no one in


def test_the_longest_address_can_be_invited() -> None:
    email = address(254)
    assert len(email) == 254
    enrol.invite(email, "Long")
    assert row(email).status == "invited"


def test_a_link_works_once() -> None:
    email, token = invited()
    assert isinstance(enrol.redeem(token, PASSWORD), Verified)
    before = sealed(email)
    assert enrol.redeem(token, "another password") is None
    assert sealed(email) == before


def test_a_second_link_dies_when_the_first_is_used_and_a_new_invite_gives_a_working_one() -> None:
    email, first = invited()
    second = enrol.invite(email, "ignored")  # an unused invite can be sent again
    assert row(email).display_name == "New User"
    assert isinstance(enrol.redeem(first, PASSWORD), Verified)
    assert enrol.redeem(second, PASSWORD) is None
    third = enrol.invite(email, "New User")  # enrolment not finished: a link over the new blob
    assert isinstance(enrol.redeem(third, "a new password"), Verified)
    assert enrol.redeem(first, PASSWORD) is None


def test_a_link_expires_after_the_configured_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    _, token = invited()
    limit = settings.SKIW_ENROL_LINK_MIN * 60
    later(monkeypatch, limit + 1)
    assert enrol.redeem(token, PASSWORD) is None
    later(monkeypatch, limit - 5)
    assert isinstance(enrol.redeem(token, PASSWORD), Verified)


@pytest.mark.parametrize("change", ["payload", "signature", "salt", "key", "garbage", "empty"])
def test_a_tampered_link_does_nothing(change: str, settings: Settings) -> None:
    email, token = invited()
    value, _, signature = token.rpartition(":")
    forged = {
        "payload": ("x" if value[0] != "x" else "y") + token[1:],
        "signature": f"{value}:{signature[::-1]}",
        "salt": signing.TimestampSigner(salt="skiw-reset-v1").sign_object(
            signing.TimestampSigner(salt=enrol.SALT).unsign_object(token)
        ),
        "garbage": "not a token",
        "empty": "",
    }
    if change == "key":
        settings.SECRET_KEY, settings.SECRET_KEY_FALLBACKS = "another key " * 4, []
        assert enrol.redeem(token, PASSWORD) is None
    else:
        assert enrol.redeem(forged[change], PASSWORD) is None
    assert row(email).login_blob_ct is None


def test_a_signed_value_of_another_shape_does_nothing() -> None:
    email, token = invited()
    signer = signing.TimestampSigner(salt=enrol.SALT)
    value = signer.unsign_object(token)
    for shape in ([value["u"]], {**value, "u": "not a uuid"}, {"u": value["u"]}, "text"):
        assert enrol.redeem(signer.sign_object(shape), "x") is None
    assert row(email).login_blob_ct is None


def test_a_link_for_a_user_no_longer_invited_does_nothing() -> None:
    email, token = invited()
    agency, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    with with_agency(agency):
        AppUser.objects.filter(email=email).update(status="disabled")
    assert enrol.redeem(token, PASSWORD) is None
    assert row(email).login_blob_ct is None


def test_an_empty_password_is_refused() -> None:
    email, token = invited()
    assert enrol.redeem(token, "") is None
    assert row(email).login_blob_ct is None
    assert isinstance(enrol.redeem(token, PASSWORD), Verified)  # still unused


def test_two_uses_at_once_set_one_password() -> None:
    email, token = invited()
    results: list[Verified | None] = []
    start = threading.Barrier(2)

    def use(password: str) -> None:
        start.wait()
        try:
            results.append(enrol.redeem(token, password))
        finally:
            connection.close()

    threads = [threading.Thread(target=use, args=(p,)) for p in (PASSWORD, "the other one")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r is None for r in results) == [False, True]
    record = blob.open_login(sealed(email), email)
    assert record is not None
    won = PASSWORD if passwords.verify(record.password_hash, PASSWORD) else "the other one"
    assert passwords.verify(record.password_hash, won)


@pytest.mark.parametrize("status", ["active", "disabled"])
def test_an_enrolled_user_is_not_invited_again(status: str) -> None:
    _, email = enrolled(status=status)
    with pytest.raises(enrol.Refused, match="already enrolled"):
        enrol.invite(email, "Again")


def test_an_email_of_another_agency_is_refused_without_naming_it(agency_b: uuid.UUID) -> None:
    other = committed_user(agency=agency_b)
    with pytest.raises(enrol.Refused, match="cannot be invited"):
        enrol.invite(other.email, "Someone")


@pytest.mark.parametrize(
    "email, name",
    [
        ("not-an-address", "Name"),
        (address(255), "Name"),  # valid in form, one past the login route's cap
        ("a@example.test", ""),
        ("a@example.test", "   "),
        ("a@example.test", "n" * 201),
        ("a@example.test", "a\x00b"),
    ],
)
def test_a_bad_email_or_name_is_refused_before_any_row(email: str, name: str) -> None:
    with pytest.raises(enrol.Refused):
        enrol.invite(email, name)


def test_the_command_prints_one_working_link() -> None:
    email, out, err = unknown(), StringIO(), StringIO()
    call_command("accounts_invite", email, name="Ann Lee", stdout=out, stderr=err)
    SEALED.append(row(email))
    link = out.getvalue().strip()
    prefix = f"https://{settings.ALLOWED_HOSTS[0]}/enrol#"
    assert link.startswith(prefix) and "\n" not in link
    assert f"{settings.SKIW_ENROL_LINK_MIN} minutes" in err.getvalue()
    assert isinstance(enrol.redeem(link.removeprefix(prefix), PASSWORD), Verified)


def test_the_command_exits_with_the_reason_when_refused() -> None:
    _, email = enrolled()
    with pytest.raises(CommandError, match="already enrolled"):
        call_command("accounts_invite", email, name="Again", stdout=StringIO())
