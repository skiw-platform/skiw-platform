"""Adding (POST /api/auth/factors/passkey, then /confirm) and removing
(POST /api/auth/factors/passkey/remove) a passkey against the real tables as skiw_app
(accounts.auth.factor_change; spec D7, AUTH-07, AUTH-09; plan M3 §3 M3g, §4 M3g row; DECISIONS
M3g-1c). A passkey is optional: TOTP stays required. The AUTH-07 tests run on the real clock (see
test_logout_password_live). Users, factors and markers are committed and kept."""

import json
import logging
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import cbor2
import pytest
from django.conf import settings
from django.db import IntegrityError
from django.test import RequestFactory
from django.utils import timezone

from accounts.auth import blob, factor_change, passkey, stepup
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.auth.second_factor import Passed, attempt
from accounts.auth.wrapper import Signed
from accounts.factor_model import SIGN_COUNT_MAX, UserFactor
from accounts.session import SessionStore, stored_key
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .authenticator import ORIGIN, RP_ID, SoftAuthenticator, unb64url
from .conftest import COOKIE, committed_user, row_deadline
from .test_action_wrapper_live import markers, signed_in
from .test_factor_change_live import stepped_up
from .test_factor_remove_live import first_totp, listed, row
from .test_logout_password_live import answer, client, probe

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of sign_in.STEP
unsealed = sign_in.unsealed  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
REFUSED = (400, {"error": "passkey-refused"})
STEPUP = (403, {"error": "stepup-required"})


PLANTED: list[tuple[uuid.UUID, uuid.UUID]] = []  # (agency, factor) written by `planted`


@pytest.fixture(autouse=True)
def no_passkey_kept(live_db: None) -> Iterator[None]:
    """A passkey in use keeps a 60-byte `lookup_blob_ct`, which the tenancy reversal test's
    accounts.0008 reverse refuses (DECISIONS M3g-1b), so each test deletes the passkeys it made
    (skiw_app holds DELETE on user_factor; no step-up names a passkey yet)."""
    home, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    before = all_passkeys(home)
    PLANTED.clear()
    yield
    for agency, factor in [(home, f) for f in all_passkeys(home) - before] + PLANTED:
        with with_agency(agency):
            UserFactor.objects.filter(id=factor, kind="passkey").delete()


def all_passkeys(agency: uuid.UUID) -> set[uuid.UUID]:
    with with_agency(agency):
        return set(UserFactor.objects.filter(kind="passkey").values_list("id", flat=True))


@pytest.fixture(autouse=True)
def relying_party(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", RP_ID)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", ORIGIN)


def post(cookie: str, path: str, body: object) -> "Response":
    return client(cookie).post(path, json.dumps(body), content_type="application/json")


def begin(cookie: str) -> "Response":
    return post(cookie, "/api/auth/factors/passkey", {})


def begun(cookie: str) -> bytes:
    """The challenge of a registration begun through the route."""
    status, body = answer(begin(cookie))
    assert status == 200 and body.keys() == {"options"}
    return unb64url(body["options"]["challenge"])


def confirm(cookie: str, credential: object) -> "Response":
    return post(cookie, "/api/auth/factors/passkey/confirm", {"credential": credential})


def remove(cookie: str, factor: object, kind: str = "passkey") -> "Response":
    return post(cookie, f"/api/auth/factors/{kind}/remove", {"id": str(factor)})


def passkeys(user: AppUser) -> list[UserFactor]:
    with with_agency(user.agency_id):
        return list(UserFactor.objects.filter(user_id=user.id, kind="passkey"))


def planted(user: AppUser, credential: bytes, *, retired: bool = False) -> uuid.UUID:
    """A passkey row of `user` written directly, in use or retired as removing leaves one."""
    factor = uuid.uuid4()
    sealed = blob.seal_credential(user.id, user.agency_id, credential)
    with with_agency(user.agency_id):
        UserFactor.objects.create(
            id=factor,
            agency_id=user.agency_id,
            user_id=user.id,
            kind="passkey",
            credential_id=credential,
            public_key=None if retired else SoftAuthenticator().cose_key(),
            lookup_blob_ct=None if retired else sealed,
            retired_at=timezone.now() if retired else None,
        )
    PLANTED.append((user.agency_id, factor))
    return factor


def assert_unchanged(user: AppUser, cookie: str, count: int = 0) -> None:
    """A refused add: no passkey row, no marker, this session still signed in."""
    assert len(passkeys(user)) == count and markers(user) == [] and probe(cookie) == 200


def test_a_right_registration_adds_the_passkey_ends_other_sessions_and_reissues_this_one(
    at_step: Any,
) -> None:
    user, secret, cookie = stepped_up()
    other, deadline = signed_in(user, factor="totp"), row_deadline(cookie)
    authenticator = SoftAuthenticator()
    status, body = answer(begin(cookie))
    options = body["options"]
    assert (options["rp"]["id"], options["user"]["name"]) == (RP_ID, user.email)
    assert unb64url(options["user"]["id"]) == user.id.bytes
    assert options["authenticatorSelection"]["userVerification"] == "required"
    response = confirm(cookie, authenticator.register(unb64url(options["challenge"])))
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "added", {"next", "factor_id", "csrf"})
    fresh = response.cookies[COOKIE].value
    assert fresh != cookie and row_deadline(fresh) == deadline  # re-issued, not a new lifetime
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    assert passkey.CHALLENGE not in SessionStore(fresh).load()
    [added] = passkeys(user)
    assert str(added.id) == body["factor_id"] and added.retired_at is None
    assert bytes(added.credential_id or b"") == authenticator.credential_id
    assert (bytes(added.public_key or b""), added.sign_count) == (authenticator.cose_key(), 0)
    assert lookup_credential(authenticator.credential_id) == CredentialOwner(
        user.id, user.agency_id
    )
    value = os.urandom(passkey.CHALLENGE_BYTES)  # the stored key verifies this authenticator
    proof = passkey.verify_assertion(
        authenticator.assertion(value),
        passkey.Challenge(value, timezone.now()),
        authenticator.credential_id,
        bytes(added.public_key or b""),
        added.sign_count,
    )
    assert proof == 1
    assert listed(fresh)["passkey"] == [{"id": body["factor_id"]}]
    # Optional: sign-in still asks for the TOTP, which still signs in.
    at_step.step += 1
    passed = attempt(sign_in.pending_login(user), sign_in.code_at(secret, sign_in.STEP + 1))
    assert passed == Passed(user.id, user.agency_id, "totp")


def test_without_a_step_up_nothing_is_begun_or_added_and_the_challenge_is_spent() -> None:
    user, _, _ = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    assert answer(begin(cookie)) == STEPUP
    assert passkey.CHALLENGE not in SessionStore(cookie).load()
    challenge = plant(cookie, lambda r: passkey.begin_registration(r, user.id, user.email, []))
    assert answer(confirm(cookie, SoftAuthenticator().register(challenge))) == STEPUP
    assert_unchanged(user, cookie)
    assert passkey.CHALLENGE not in SessionStore(cookie).load()


def test_a_stale_step_up_is_refused_at_begin_and_at_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _, cookie = stepped_up()
    challenge = begun(cookie)
    later = timedelta(minutes=settings.SKIW_STEPUP_MAX_AGE_MIN, seconds=1)
    monkeypatch.setattr(stepup, "timezone", SimpleNamespace(now=lambda: timezone.now() + later))
    assert answer(confirm(cookie, SoftAuthenticator().register(challenge))) == STEPUP
    assert answer(begin(cookie)) == STEPUP
    assert_unchanged(user, cookie)


def plant(cookie: str, issue: Callable[[Any], dict[str, Any]]) -> bytes:
    """A challenge issued into the session outside the begin route (states the route never
    leaves); its value."""
    request = RequestFactory().post("/")
    request.session = SessionStore(cookie)
    options = issue(request)
    request.session.save()
    return unb64url(options["challenge"])


def unusable(case: str, user: AppUser, cookie: str, authenticator: SoftAuthenticator) -> bytes:
    """The session left with no usable `register` challenge for `user`; the value to answer."""
    if case == "a step-up's":
        return plant(cookie, lambda r: passkey.begin_assertion(r, "stepup", user.id, []))
    if case == "a sign-in's":
        return plant(cookie, lambda r: passkey.begin_assertion(r, "login", user.id, []))
    if case == "another user's":
        other = uuid.uuid4()
        return plant(cookie, lambda r: passkey.begin_registration(r, other, "x@example.test", []))
    if case == "none begun":
        return os.urandom(passkey.CHALLENGE_BYTES)
    challenge = begun(cookie)
    if case == "past its deadline":
        store = SessionStore(cookie)
        record = dict(store[passkey.CHALLENGE])
        record["until"] = (timezone.now() - timedelta(seconds=1)).isoformat()
        store[passkey.CHALLENGE] = record
        store.save()
    else:  # spent by a failed verify
        assert answer(confirm(cookie, authenticator.register(challenge, uv=False))) == REFUSED
    return challenge


@pytest.mark.parametrize(
    "case",
    [
        "none begun",
        "a step-up's",
        "a sign-in's",
        "another user's",
        "past its deadline",
        "spent by a failed verify",
    ],
)
def test_no_usable_challenge_is_the_one_refusal(case: str) -> None:
    user, _, cookie = stepped_up()
    authenticator = SoftAuthenticator()
    challenge = unusable(case, user, cookie, authenticator)
    assert answer(confirm(cookie, authenticator.register(challenge))) == REFUSED
    assert_unchanged(user, cookie)
    assert passkey.CHALLENGE not in SessionStore(cookie).load()


UNVERIFIED: dict[str, Callable[[SoftAuthenticator, bytes], dict[str, Any]]] = {
    "no user verification": lambda a, c: a.register(c, uv=False),
    "another origin": lambda a, c: a.register(c, origin="https://evil.example"),
    "another RP ID": lambda a, c: a.register(c, rp_id="evil.example"),
    "another challenge": lambda a, c: a.register(os.urandom(passkey.CHALLENGE_BYTES)),
    "sent under another id": lambda a, c: a.register(c, sent_id=os.urandom(16)),
    "a key without coordinates": lambda a, c: a.register(c, cose=cbor2.dumps({1: 2, 3: -7, -1: 1})),
}


@pytest.mark.parametrize("case", UNVERIFIED)
def test_a_registration_that_does_not_verify_is_the_one_refusal(case: str) -> None:
    user, _, cookie = stepped_up()
    authenticator = SoftAuthenticator()
    challenge = begun(cookie)
    assert answer(confirm(cookie, UNVERIFIED[case](authenticator, challenge))) == REFUSED
    assert_unchanged(user, cookie)
    assert answer(confirm(cookie, authenticator.register(challenge))) == REFUSED  # spent


@pytest.mark.parametrize("owner", ["own, in use", "own, retired", "same agency", "other agency"])
def test_a_credential_id_registered_before_is_the_one_refusal_and_logs_nothing(
    owner: str, request: pytest.FixtureRequest, caplog: pytest.LogCaptureFixture
) -> None:
    user, _, cookie = stepped_up()
    authenticator = SoftAuthenticator()
    holder = user
    if owner == "same agency":
        holder = committed_user()
    elif owner == "other agency":
        holder = committed_user(agency=request.getfixturevalue("agency_b"))
    planted(holder, authenticator.credential_id, retired=owner == "own, retired")
    caplog.set_level(logging.DEBUG)
    response = confirm(cookie, authenticator.register(begun(cookie)))
    assert answer(response) == REFUSED
    assert_unchanged(user, cookie, count=1 if holder is user else 0)
    assert factor_change.CREDENTIAL_KEY not in caplog.text
    assert authenticator.credential_id.hex() not in caplog.text


def test_one_authenticator_registered_by_two_users_is_added_once() -> None:
    first, _, first_cookie = stepped_up()
    second, _, second_cookie = stepped_up()
    authenticator = SoftAuthenticator()
    added = confirm(first_cookie, authenticator.register(begun(first_cookie)))
    assert added.status_code == 200
    assert answer(confirm(second_cookie, authenticator.register(begun(second_cookie)))) == REFUSED
    assert_unchanged(second, second_cookie)
    assert lookup_credential(authenticator.credential_id) == CredentialOwner(
        first.id, first.agency_id
    )


def test_begin_excludes_only_the_users_passkeys_in_use() -> None:
    user, _, cookie = stepped_up()
    in_use, retired, neighbours = os.urandom(16), os.urandom(16), os.urandom(16)
    planted(user, in_use)
    planted(user, retired, retired=True)
    planted(committed_user(), neighbours)
    status, body = answer(begin(cookie))
    excluded = [unb64url(c["id"]) for c in body["options"]["excludeCredentials"]]
    assert (status, excluded) == (200, [in_use])


@pytest.mark.parametrize(
    "raw", [b"{}", b'{"credential": []}', b'{"credential": "x"}', b'{"credential": {}, "x": 1}']
)
def test_a_body_that_is_not_one_credential_is_400_and_leaves_the_challenge(raw: bytes) -> None:
    user, _, cookie = stepped_up()
    begun(cookie)
    response = client(cookie).post(
        "/api/auth/factors/passkey/confirm", raw, content_type="application/json"
    )
    assert answer(response) == (400, {"error": "invalid"})
    assert passkey.CHALLENGE in SessionStore(cookie).load()
    assert_unchanged(user, cookie)


def test_another_integrity_error_is_raised_not_refused() -> None:
    user, now = committed_user(), timezone.now()
    signed = Signed(user.id, user.agency_id, "totp", now, now)
    bad = passkey.Registered(os.urandom(16), b"\1", SIGN_COUNT_MAX + 1)
    with pytest.raises(IntegrityError), with_agency(user.agency_id):
        factor_change._stored(signed, uuid.uuid4(), bad)


def test_removing_a_passkey_retires_it_ends_other_sessions_and_reissues_this_one() -> None:
    user, _, cookie = stepped_up()
    credential = os.urandom(16)
    factor = planted(user, credential)
    other, deadline = signed_in(user, factor="totp"), row_deadline(cookie)
    assert lookup_credential(credential) == CredentialOwner(user.id, user.agency_id)
    response = remove(cookie, factor)
    status, body = answer(response)
    assert (status, body["next"], set(body)) == (200, "removed", {"next", "csrf"})
    fresh = response.cookies[COOKIE].value
    assert fresh != cookie and row_deadline(fresh) == deadline
    assert (probe(fresh), probe(other), probe(cookie)) == (200, 401, 401)
    assert set(markers(user)) == {None, stored_key(cookie)}
    retired = row(factor, user)
    assert retired.retired_at is not None and bytes(retired.credential_id or b"") == credential
    assert (retired.public_key, retired.lookup_blob_ct) == (None, None)
    assert lookup_credential(credential) is None
    assert listed(fresh)["passkey"] == [] and len(listed(fresh)["totp"]) == 1


def test_without_a_step_up_a_passkey_is_not_removed() -> None:
    user, _, _ = sign_in.signing_in()
    cookie = signed_in(user, factor="totp")
    factor = planted(user, os.urandom(16))
    assert answer(remove(cookie, factor)) == STEPUP
    assert row(factor, user).retired_at is None and markers(user) == []


@pytest.mark.parametrize("case", ["neighbour's", "retired", "unknown", "a totp", "via totp"])
def test_anything_but_the_users_passkey_in_use_is_not_found(case: str) -> None:
    user, _, cookie = stepped_up()
    kind, factor = "passkey", uuid.uuid4()
    if case == "neighbour's":
        factor = planted(committed_user(), os.urandom(16))
    elif case == "retired":
        factor = planted(user, os.urandom(16), retired=True)
    elif case == "a totp":
        planted(user, os.urandom(16))  # removing a passkey would be allowed
        factor = first_totp(user)
    elif case == "via totp":
        kind, factor = "totp", planted(user, os.urandom(16))
    assert answer(remove(cookie, factor, kind)) == (404, {"error": "not-found"})
    assert markers(user) == [] and probe(cookie) == 200


def test_a_passkey_never_stands_in_for_the_required_totp() -> None:
    user, _, cookie = stepped_up()
    totp, factor = first_totp(user), planted(user, os.urandom(16))
    assert answer(remove(cookie, totp, "totp")) == (409, {"error": "last-factor"})
    with with_agency(user.agency_id):  # a user without a TOTP in use (never left by a route)
        UserFactor.objects.filter(id=totp).update(retired_at=timezone.now(), secret_ct=None)
    assert answer(remove(cookie, factor)) == (409, {"error": "last-factor"})
    assert row(factor, user).retired_at is None and markers(user) == []
