"""A passkey as the second factor of a sign-in (POST /api/auth/second-factor/passkey, then
/confirm) against the real tables as skiw_app (accounts.auth.assertion; spec D7, Flow 5.1 (2),
AUTH-05, AUTH-06; plan M3 §3 M3g, §4 M3g row; DECISIONS M3g-1b, M3g-1d-1; PR 154 R1 P2 #2).
Users are committed and kept; the passkeys a test adds are retired after it, as a removal does, not
deleted (a kept 60-byte blob breaks the tenancy reversal test, DECISIONS M3g-1b; from M3g-1d-2
step-up evidence may name them, and the step-up tests reuse this module's helpers)."""

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.db import connection
from django.db.models.functions import Now
from django.test import Client
from django.utils import timezone

from accounts import views
from accounts.auth import assertion, blob, passkey
from accounts.auth.login import FACTOR, SEEN_AT
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.auth.second_factor import attempt
from accounts.factor_model import UserFactor
from accounts.session import SessionStore
from accounts.user_model import AppUser
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_second_factor_live as sign_in
from .authenticator import ORIGIN, RP_ID, SoftAuthenticator, b64url, unb64url
from .conftest import COOKIE, Clock
from .logins import factor_count
from .test_action_wrapper_live import signed_in
from .test_factor_lock_live import markers as lock_markers
from .test_factor_lock_live import run as lock_run
from .test_logout_password_live import answer

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step = sign_in.at_step  # autouse: totp's clock in the middle of sign_in.STEP
unsealed = sign_in.unsealed  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
BEGIN, FINISH = "/api/auth/second-factor/passkey", "/api/auth/second-factor/passkey/confirm"
WRONG = (401, {"error": "passkey-wrong"})
EXPIRED = (401, {"error": "login-expired"})
LIMITED = (429, {"error": "limited"})
NO_PASSKEY = (409, {"error": "no-passkey"})
LIMIT, WINDOW = sign_in.LIMIT, sign_in.WINDOW


@pytest.fixture(autouse=True)
def relying_party(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", RP_ID)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", ORIGIN)


def in_use(agency: uuid.UUID) -> set[uuid.UUID]:
    with with_agency(agency):
        rows = UserFactor.objects.filter(kind="passkey", retired_at__isnull=True)
        return set(rows.values_list("id", flat=True))


@pytest.fixture(autouse=True)
def passkeys_retired(live_db: None) -> Iterator[None]:
    home, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    before = in_use(home)
    yield
    added = in_use(home) - before
    with with_agency(home):
        UserFactor.objects.filter(id__in=added).update(
            retired_at=Now(), public_key=None, lookup_blob_ct=None
        )


def with_passkey(
    user: AppUser,
    authenticator: SoftAuthenticator,
    *,
    owner: tuple[uuid.UUID, uuid.UUID] | None = None,
    retired: bool = False,
) -> uuid.UUID:
    """A passkey row of `user` for `authenticator`, as registration leaves one; its lookup blob is
    sealed for `owner` (user, agency), the user's own unless given."""
    owner_user, owner_agency = owner or (user.id, user.agency_id)
    factor, credential = uuid.uuid4(), authenticator.credential_id
    with with_agency(user.agency_id):
        UserFactor.objects.create(
            id=factor,
            agency_id=user.agency_id,
            user_id=user.id,
            kind="passkey",
            credential_id=credential,
            public_key=None if retired else authenticator.cose_key(),
            sign_count=authenticator.sign_count,
            lookup_blob_ct=None
            if retired
            else blob.seal_credential(owner_user, owner_agency, credential),
            retired_at=timezone.now() if retired else None,
        )
    return factor


def passkey_user(*, counts: bool = True) -> tuple[AppUser, bytes, SoftAuthenticator, uuid.UUID]:
    """An active user with a password, a TOTP factor (secret returned), recovery codes and one
    passkey in use (its authenticator and factor id)."""
    user, secret, _ = sign_in.signing_in()
    authenticator = SoftAuthenticator(counts=counts)
    return user, secret, authenticator, with_passkey(user, authenticator)


def pending(user: AppUser, *, enrol: bool = False) -> Client:
    """A browser holding a pending login (or enrolment) of `user`, as the password step leaves."""
    request = sign_in.pending_login(user, enrol=enrol)
    request.session.save()
    browser = Client()
    browser.cookies[COOKIE] = str(request.session.session_key)
    return browser


def post(browser: Client, path: str, body: object) -> "Response":
    return browser.post(path, json.dumps(body), content_type="application/json")


def begun(browser: Client) -> bytes:
    """The challenge of an assertion begun through the route."""
    status, body = answer(post(browser, BEGIN, {}))
    assert status == 200 and body.keys() == {"options"}
    return unb64url(body["options"]["challenge"])


def finish(browser: Client, credential: object) -> tuple[int, Any]:
    return answer(post(browser, FINISH, {"credential": credential}))


def stored(factor: uuid.UUID, user: AppUser) -> tuple[int, datetime | None]:
    with with_agency(user.agency_id):
        row = UserFactor.objects.get(id=factor)
    return row.sign_count, row.last_challenge_at


def probe(browser: Client) -> int:
    return browser.post("/action-probe", b"{}", content_type="application/json").status_code


def lookups() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM security_event WHERE kind = 'passkey.lookup'")
        return int(cursor.fetchone()[0])


def session_of(browser: Client) -> SessionStore:
    store = SessionStore(browser.cookies[COOKIE].value)
    store.load()
    return store


def test_a_right_assertion_signs_in_and_stores_the_count_and_the_challenge_time() -> None:
    user, _, authenticator, factor = passkey_user()
    browser = pending(user)
    status, body = answer(post(browser, BEGIN, {}))
    options = body["options"]
    assert status == 200 and options["rpId"] == RP_ID and options["userVerification"] == "required"
    assert [unb64url(c["id"]) for c in options["allowCredentials"]] == [authenticator.credential_id]
    challenge = unb64url(options["challenge"])
    issued_at = datetime.fromisoformat(session_of(browser)[passkey.CHALLENGE]["at"])
    events = lookups()
    status, body = finish(browser, authenticator.assertion(challenge))
    assert status == 200 and body.keys() == {"next", "csrf"} and body["next"] == "signed_in"
    session = session_of(browser)
    assert session[FACTOR] == "passkey" and passkey.CHALLENGE not in session
    keys = list(session.keys())  # a SessionStore is not iterable
    assert not any(key.startswith("_skiw_pending") for key in keys)
    assert probe(browser) == 200
    assert stored(factor, user) == (1, issued_at) and lookups() == events + 1
    assert factor_count(user.id) == 0 and lock_run(user.id) == 0


def test_a_zero_counter_signs_in_with_each_new_challenge_and_its_count_stays_zero() -> None:
    user, _, authenticator, factor = passkey_user(counts=False)
    for _ in range(2):
        browser = pending(user)
        assert finish(browser, authenticator.assertion(begun(browser)))[0] == 200
        assert stored(factor, user)[0] == 0


def test_lookup_commits_before_a_fault_in_tenant_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _, authenticator, factor = passkey_user()
    browser = pending(user)
    credential = authenticator.assertion(begun(browser))
    events = lookups()

    def lookup(credential_id: bytes) -> CredentialOwner | None:
        assert connection.get_autocommit() and not connection.in_atomic_block
        assert factor_count(user.id) == 1  # reservation precedes discovery
        return lookup_credential(credential_id)

    def fault(*args: Any) -> None:
        assert connection.in_atomic_block
        UserFactor.objects.filter(id=factor).update(sign_count=99)
        raise OSError("post-lookup fault")

    monkeypatch.setattr(assertion, "lookup_credential", lookup)
    monkeypatch.setattr(passkey, "verify_assertion", fault)
    with pytest.raises(OSError, match="post-lookup fault"):
        finish(browser, credential)
    assert lookups() == events + 1
    assert stored(factor, user) == (0, None)  # tenant write rolled back, event did not
    assert factor_count(user.id) == 0 and lock_run(user.id) == 0
    assert passkey.CHALLENGE not in session_of(browser)
    assert probe(browser) == 401


def stale_copy(browser: Client) -> SessionStore:
    """The session as a parallel request loaded it while it held the challenge."""
    stale = session_of(browser)
    assert passkey.CHALLENGE in stale
    return stale


def put_back(stale: SessionStore) -> None:
    """The stale request saves the whole session (one changed key, as the wrapper's SEEN_AT bump),
    which writes the taken challenge back (PR 154 R1 P2 #2)."""
    stale[SEEN_AT] = timezone.now().isoformat(timespec="microseconds")
    stale.save()


@pytest.mark.parametrize("counts", [False, True], ids=["zero-counter", "counter"])
def test_a_challenge_a_stale_save_put_back_cannot_sign_in_again(
    counts: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Request A takes the challenge and its assertion is accepted, but login() then fails (a 500
    saves nothing, so the pending login stays: DECISIONS M3f-3c-2); request B, which loaded the
    session before the take, saves it. The same assertion against the challenge put back is
    refused by the conditional update (equal issue time; for a counter, also the count)."""
    user, _, authenticator, factor = passkey_user(counts=counts)
    browser = pending(user)
    credential = authenticator.assertion(begun(browser))
    stale = stale_copy(browser)
    with monkeypatch.context() as patch:
        patch.setattr(views, "login", lambda *args, **kwargs: (_ for _ in ()).throw(OSError))
        with pytest.raises(OSError):
            post(browser, FINISH, {"credential": credential})
    after_a = stored(factor, user)
    assert after_a[1] is not None and passkey.CHALLENGE not in session_of(browser)
    put_back(stale)
    assert passkey.CHALLENGE in session_of(browser)  # the challenge really is back
    assert finish(browser, credential) == WRONG
    assert stored(factor, user) == after_a and factor_count(user.id) == 1
    assert probe(browser) == 401  # still not signed in


def test_a_count_that_does_not_rise_is_refused_and_a_rising_one_passes() -> None:
    user, _, authenticator, factor = passkey_user()
    authenticator.sign_count = 5
    with with_agency(user.agency_id):
        UserFactor.objects.filter(id=factor).update(sign_count=5)
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser), count=5)) == WRONG
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser), count=6))[0] == 200
    assert stored(factor, user)[0] == 6


@pytest.mark.parametrize("counts", [False, True], ids=["zero-counter", "counter"])
def test_a_count_another_request_raised_after_the_read_is_refused_by_the_update(
    counts: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The library checks the count against the row as read; the conditional update decides
    against the row as it is (a parallel assertion with a later count, or a first non-zero count
    on a zero-counter passkey, landed in between)."""
    user, _, authenticator, factor = passkey_user(counts=counts)
    real = passkey.verify_assertion

    def overtaken(*args: Any) -> int | None:
        UserFactor.objects.filter(id=factor).update(sign_count=9)  # inside the same transaction
        return real(*args)

    monkeypatch.setattr(passkey, "verify_assertion", overtaken)
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser))) == WRONG
    assert stored(factor, user) == (9, None)


def test_a_passkey_retired_after_the_read_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    user, _, authenticator, factor = passkey_user()
    real = passkey.verify_assertion
    gone = {"retired_at": timezone.now(), "public_key": None, "lookup_blob_ct": None}

    def retired_meanwhile(*args: Any) -> int | None:
        UserFactor.objects.filter(id=factor).update(**gone)  # factor_change.remove, in between
        return real(*args)

    monkeypatch.setattr(passkey, "verify_assertion", retired_meanwhile)
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser))) == WRONG
    assert stored(factor, user) == (0, None)


def test_another_users_row_is_never_used_even_if_its_blob_named_this_user() -> None:
    """Defence in depth behind the owner match: the row read is this user's own."""
    user, _, _, _ = passkey_user()
    neighbour, _, _ = sign_in.signing_in()
    authenticator = SoftAuthenticator()
    factor = with_passkey(neighbour, authenticator, owner=(user.id, user.agency_id))
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser))) == WRONG
    assert stored(factor, neighbour) == (0, None) and factor_count(user.id) == 1


def test_a_challenge_issued_before_one_already_used_is_refused_even_in_another_session() -> None:
    """DECISIONS M3g-1d-1: comparing issue times fails closed for an older challenge."""
    user, _, authenticator, factor = passkey_user(counts=False)
    first, second = pending(user), pending(user)
    older = authenticator.assertion(begun(first))
    assert finish(second, authenticator.assertion(begun(second)))[0] == 200
    used = stored(factor, user)
    assert finish(first, older) == WRONG and stored(factor, user) == used


def test_an_assertion_for_another_sessions_challenge_is_refused() -> None:
    user, _, authenticator, _ = passkey_user()
    first, second = pending(user), pending(user)
    credential = authenticator.assertion(begun(first))
    assert finish(second, credential) == WRONG  # nothing begun in this session
    begun(second)
    assert finish(second, credential) == WRONG  # this session's challenge is another one
    assert factor_count(user.id) == 2


@pytest.mark.parametrize("purpose", ["stepup", "register", "other-user"])
def test_a_challenge_for_another_purpose_or_user_is_refused(purpose: str) -> None:
    user, _, authenticator, _ = passkey_user()
    request = sign_in.pending_login(user)
    kind = "login" if purpose == "other-user" else purpose
    named = uuid.uuid4() if purpose == "other-user" else user.id
    challenge = passkey._issue(request, kind, named)  # type: ignore[arg-type]
    request.session.save()
    browser = Client()
    browser.cookies[COOKIE] = str(request.session.session_key)
    assert finish(browser, authenticator.assertion(challenge)) == WRONG
    assert passkey.CHALLENGE not in session_of(browser)  # spent all the same


def test_a_challenge_spent_by_a_failure_cannot_be_used_by_the_right_assertion() -> None:
    user, _, authenticator, factor = passkey_user()
    browser = pending(user)
    challenge = begun(browser)
    assert finish(browser, authenticator.assertion(challenge, uv=False)) == WRONG
    assert finish(browser, authenticator.assertion(challenge)) == WRONG
    assert stored(factor, user) == (0, None) and factor_count(user.id) == 2
    assert finish(browser, authenticator.assertion(begun(browser)))[0] == 200


def unknown_id(user: AppUser, authenticator: SoftAuthenticator) -> SoftAuthenticator:
    return SoftAuthenticator()  # registered nowhere


def retired_id(user: AppUser, authenticator: SoftAuthenticator) -> SoftAuthenticator:
    other = SoftAuthenticator()
    with_passkey(user, other, retired=True)
    return other


def wrong_key(user: AppUser, authenticator: SoftAuthenticator) -> SoftAuthenticator:
    return SoftAuthenticator(credential_id=authenticator.credential_id)  # same id, another key


def another_users(user: AppUser, authenticator: SoftAuthenticator) -> SoftAuthenticator:
    _, _, theirs, _ = passkey_user()
    return theirs


DECOYS = {
    "unknown-id": unknown_id,
    "retired-id": retired_id,
    "wrong-key": wrong_key,
    "another-users-credential": another_users,
}


@pytest.mark.parametrize("case", sorted(DECOYS))
def test_every_assertion_that_is_not_the_users_gets_one_answer_and_one_count(case: str) -> None:
    """AUTH-05: an unknown or retired credential id, a wrong key and another user's passkey are
    the same answer, the same count, the same run and the same one lookup event."""
    user, _, authenticator, factor = passkey_user()
    answering = DECOYS[case](user, authenticator)
    browser = pending(user)
    challenge, events = begun(browser), lookups()
    response = post(browser, FINISH, {"credential": answering.assertion(challenge)})
    assert (response.status_code, response.content) == (401, b'{"error": "passkey-wrong"}')
    assert response["Cache-Control"] == "no-store"
    assert factor_count(user.id) == 1 and lock_run(user.id) == 1 and lookups() == events + 1
    assert stored(factor, user) == (0, None)


@pytest.mark.parametrize("owner", ["another-user", "another-agency"])
def test_a_blob_that_names_anyone_but_the_pending_user_and_agency_is_refused(
    owner: str, agency_b: uuid.UUID
) -> None:
    """The owner match is the guard (an empty allowCredentials admits any discoverable
    credential): the user's own row and key, but a lookup blob sealed for someone else."""
    user, _, _, _ = passkey_user()
    named = (uuid.uuid4(), user.agency_id) if owner == "another-user" else (user.id, agency_b)
    authenticator = SoftAuthenticator()
    factor = with_passkey(user, authenticator, owner=named)
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser))) == WRONG
    assert stored(factor, user) == (0, None) and factor_count(user.id) == 1


@pytest.mark.parametrize("size", [0, passkey.MAX_CREDENTIAL_ID + 1])
def test_an_id_outside_the_bound_is_refused_alike_before_any_lookup(size: int) -> None:
    user, _, authenticator, _ = passkey_user()
    browser = pending(user)
    challenge, events = begun(browser), lookups()
    credential = authenticator.assertion(challenge)
    credential["id"] = credential["rawId"] = b64url(b"\x01" * size)
    assert finish(browser, credential) == WRONG
    assert lookups() == events and factor_count(user.id) == 1


def test_assertions_and_codes_share_one_budget_and_no_lookup_runs_past_it() -> None:
    user, secret, authenticator, _ = passkey_user()
    for n in range(LIMIT):
        if n % 2:
            assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == ("wrong_code")
        else:
            browser = pending(user)
            assert finish(browser, authenticator.assertion(begun(browser), uv=False)) == WRONG
    browser = pending(user)
    challenge, events = begun(browser), lookups()
    assert finish(browser, authenticator.assertion(challenge)) == LIMITED
    assert lookups() == events  # nothing looked up past the budget
    assert attempt(sign_in.pending_login(user), sign_in.code_at(secret, sign_in.STEP)) == (
        "limited"
    )


def test_ten_wrong_assertions_and_codes_in_a_row_lock_both_like_totp(clock: Clock) -> None:
    after = settings.SKIW_AUTH_LOCK_AFTER
    user, secret, authenticator, factor = passkey_user()
    for n in range(after):
        if factor_count(user.id) >= LIMIT:
            clock.advance(WINDOW)
        if n % 2:
            wrong = sign_in.wrong_for(secret)
            assert attempt(sign_in.pending_login(user), wrong) == "wrong_code"
        else:
            browser = pending(user)
            assert finish(browser, authenticator.assertion(begun(browser), uv=False)) == WRONG
    assert lock_markers(user.id) == 1
    clock.advance(WINDOW)  # a fresh budget, but the lock holds
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser))) == LIMITED
    right = sign_in.code_at(secret, sign_in.STEP)
    assert attempt(sign_in.pending_login(user), right) == "limited"
    assert stored(factor, user) == (0, None)
    clock.advance(timedelta(minutes=settings.SKIW_AUTH_LOCK_MIN))
    browser = pending(user)
    assert finish(browser, authenticator.assertion(begun(browser)))[0] == 200
    assert lock_run(user.id) == 0  # a success ends the run


def test_no_assertion_is_begun_for_a_user_without_a_passkey_in_use() -> None:
    user, _, _ = sign_in.signing_in()
    with_passkey(user, SoftAuthenticator(), retired=True)
    browser = pending(user)
    assert answer(post(browser, BEGIN, {})) == NO_PASSKEY
    assert passkey.CHALLENGE not in session_of(browser)
    assert finish(browser, SoftAuthenticator().assertion(bytes(32))) == WRONG  # nothing to take


@pytest.mark.parametrize("case", ["no-session", "enrolment", "signed-in", "inactive"])
def test_without_a_pending_login_nothing_is_begun_taken_or_counted(case: str) -> None:
    """A passkey never stands in for the password step."""
    user, _, authenticator, factor = passkey_user()
    browser = Client()
    if case == "enrolment":
        browser = pending(user, enrol=True)
    elif case == "signed-in":
        browser.cookies[COOKIE] = signed_in(user, factor="totp")
    elif case == "inactive":
        browser = pending(user)
        with with_agency(user.agency_id):
            AppUser.objects.filter(id=user.id).update(status="disabled")
    assert answer(post(browser, BEGIN, {})) == EXPIRED
    events = lookups()
    assert finish(browser, authenticator.assertion(bytes(32))) == EXPIRED
    assert factor_count(user.id) == 0 and lookups() == events and stored(factor, user) == (0, None)


def test_a_user_disabled_after_begin_is_expired_and_nothing_is_counted() -> None:
    user, _, authenticator, factor = passkey_user()
    browser = pending(user)
    challenge = begun(browser)
    with with_agency(user.agency_id):
        AppUser.objects.filter(id=user.id).update(status="disabled")
    assert finish(browser, authenticator.assertion(challenge)) == EXPIRED
    assert factor_count(user.id) == 0 and stored(factor, user) == (0, None)


@pytest.mark.parametrize(
    "raw",
    [b"{}", b'{"credential": "x"}', b'{"credential": {}, "code": "1"}', b"[]", b"{"],
)
def test_a_body_that_is_not_one_credential_object_is_400_and_takes_nothing(raw: bytes) -> None:
    user, _, _, _ = passkey_user()
    browser = pending(user)
    begun(browser)
    response = browser.post(FINISH, raw, content_type="application/json")
    assert answer(response) == (400, {"error": "invalid"})
    assert passkey.CHALLENGE in session_of(browser) and factor_count(user.id) == 0


def test_a_user_with_a_passkey_still_signs_in_with_a_code_and_the_code_route_is_unchanged() -> None:
    user, secret, _, _ = passkey_user()
    browser = pending(user)
    code = sign_in.code_at(secret, sign_in.STEP)
    status, _ = answer(post(browser, "/api/auth/second-factor", {"code": code}))
    assert status == 200 and session_of(browser)[FACTOR] == "totp"
    browser = pending(user)
    wrong = post(browser, "/api/auth/second-factor", {"code": sign_in.wrong_for(secret)})
    assert answer(wrong) == (401, {"error": "code-wrong"})
