"""A passkey as the proof of a step-up (POST /api/auth/stepup/passkey, then /confirm) against the
real tables as skiw_app (accounts.auth.stepup.begin_passkey and verify_passkey through
assertion.counted_assertion; spec D7, AUTH-05, AUTH-06, AUTH-09; plan M3 §3 M3g, M3h; DECISIONS
M3h-3, M3g-1d-2; PR 154 R1 P2 #2, PR 157 R2 P2). Users and their step-up rows are kept; the
passkeys a test adds are retired after it (test_passkey_signin_live.passkeys_retired)."""

import json
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.db import connection
from django.test import Client, RequestFactory
from django.utils import timezone

from accounts.auth import assertion, passkey, stepup
from accounts.auth.lookup import CredentialOwner, lookup_credential
from accounts.auth.second_factor import attempt
from accounts.factor_model import UserFactor
from tenancy.binding import with_agency
from tests.test_csrf_gate import CASES_URLCONF

from . import test_passkey_signin_live as signin
from . import test_second_factor_live as sign_in
from .authenticator import SoftAuthenticator, unb64url
from .conftest import Clock
from .logins import factor_count
from .test_factor_lock_live import markers as lock_markers
from .test_factor_lock_live import run as lock_run
from .test_stepup_route_live import CHANGE, answer, evidence, probe, session, step_up

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

at_step, unsealed = sign_in.at_step, sign_in.unsealed  # autouse
relying_party, passkeys_retired = signin.relying_party, signin.passkeys_retired  # autouse
pytestmark = [pytest.mark.live, pytest.mark.usefixtures("live_db"), pytest.mark.urls(CASES_URLCONF)]
BEGIN, FINISH = "/api/auth/stepup/passkey", "/api/auth/stepup/passkey/confirm"
WRONG, LIMITED, NO_PASSKEY = signin.WRONG, signin.LIMITED, signin.NO_PASSKEY
LIMIT, WINDOW, lookups, stored = signin.LIMIT, signin.WINDOW, signin.lookups, signin.stored


def post(client: Client, path: str, body: object) -> "Response":
    return client.post(path, json.dumps(body), content_type="application/json")


def begun(client: Client) -> bytes:
    status, body = answer(post(client, BEGIN, {}))
    assert status == 200 and body.keys() == {"options"}
    return unb64url(body["options"]["challenge"])


def confirm(client: Client, credential: object, purpose: Any = CHANGE) -> tuple[int, Any]:
    return answer(post(client, FINISH, {"purpose": purpose, "credential": credential}))


def plant(client: Client, record: object) -> None:
    """Puts a challenge record (another ceremony's) into this browser's session."""
    store = signin.session_of(client)
    store[passkey.CHALLENGE] = record
    store.save()


@pytest.mark.parametrize("purpose", sorted(stepup.PURPOSES))
def test_a_right_assertion_steps_up_this_session_only_and_the_evidence_names_the_passkey(
    purpose: str,
) -> None:
    user, _, authenticator, factor = signin.passkey_user()
    client, other = session(user), session(user)
    status, body = answer(post(client, BEGIN, {}))
    options = body["options"]
    allowed = [unb64url(c["id"]) for c in options["allowCredentials"]]
    assert status == 200 and allowed == [authenticator.credential_id]
    assert options["userVerification"] == "required"
    events = lookups()
    status, body = confirm(client, authenticator.assertion(unb64url(options["challenge"])), purpose)
    (row,) = evidence(user)
    assert status == 200 and body["next"] == "verified"
    assert (row.factor_id, row.purpose) == (factor, purpose)
    assert stored(factor, user)[0] == 1 and factor_count(user.id) == 0 and lookups() == events + 1
    assert passkey.CHALLENGE not in signin.session_of(client)
    if purpose == CHANGE:
        assert probe(client) == 200 and probe(other) == 403


def test_reservation_then_committed_discovery_then_tenant_verification_and_a_fault_keeps_the_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR 157 R2 P2: the attempt is reserved, the lookup runs in autocommit and its event
    survives a fault in the tenant step, whose write rolls back; the attempt is given back."""
    user, _, authenticator, factor = signin.passkey_user()
    client = session(user)
    credential = authenticator.assertion(begun(client))
    events, seen = lookups(), []

    def lookup(credential_id: bytes) -> CredentialOwner | None:
        assert connection.get_autocommit() and not connection.in_atomic_block
        assert factor_count(user.id) == 1  # reserved first
        seen.append("discover")
        return lookup_credential(credential_id)

    def fault(*args: Any) -> None:
        assert connection.in_atomic_block and seen == ["discover"]
        UserFactor.objects.filter(id=factor).update(sign_count=99)
        raise OSError("post-lookup fault")

    monkeypatch.setattr(assertion, "lookup_credential", lookup)
    monkeypatch.setattr(passkey, "verify_assertion", fault)
    with pytest.raises(OSError, match="post-lookup fault"):
        confirm(client, credential)
    assert lookups() == events + 1 and stored(factor, user) == (0, None)
    assert factor_count(user.id) == 0 and lock_run(user.id) == 0 and evidence(user) == []
    assert passkey.CHALLENGE not in signin.session_of(client)


def test_a_fault_writing_the_evidence_rolls_the_passkey_use_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _, authenticator, factor = signin.passkey_user()
    client = session(user)

    def fail(*_: object) -> stepup.StepUp:
        raise RuntimeError("the insert failed")

    with monkeypatch.context() as patch:
        patch.setattr(stepup, "record", fail)
        with pytest.raises(RuntimeError):
            confirm(client, authenticator.assertion(begun(client)))
    assert stored(factor, user) == (0, None) and factor_count(user.id) == 0
    assert evidence(user) == [] and lock_run(user.id) == 0


@pytest.mark.parametrize("counts", [False, True], ids=["zero-counter", "counter"])
def test_a_challenge_a_stale_save_put_back_cannot_step_up_again(counts: bool) -> None:
    """Request B loads the session while it holds the challenge; A takes it and steps up; B saves
    the whole session (the wrapper's SEEN_AT bump), so the challenge is back. The same assertion
    is refused: 0 rows updated (equal issue time), no second evidence row (PR 154 R1 P2 #2)."""
    user, _, authenticator, factor = signin.passkey_user(counts=counts)
    client = session(user)
    credential = authenticator.assertion(begun(client))
    stale = signin.stale_copy(client)
    assert confirm(client, credential)[0] == 200
    after_a = stored(factor, user)
    signin.put_back(stale)
    assert passkey.CHALLENGE in signin.session_of(client)  # the challenge really is back
    assert confirm(client, credential) == WRONG
    assert stored(factor, user) == after_a and len(evidence(user)) == 1
    assert factor_count(user.id) == 1


@pytest.mark.parametrize("counts", [False, True], ids=["zero-counter", "counter"])
def test_a_used_assertion_replayed_against_a_new_challenge_is_refused(counts: bool) -> None:
    user, _, authenticator, factor = signin.passkey_user(counts=counts)
    client = session(user)
    credential = authenticator.assertion(begun(client))
    assert confirm(client, credential)[0] == 200
    assert confirm(client, credential) == WRONG  # nothing begun: no challenge
    begun(client)
    assert confirm(client, credential) == WRONG
    assert len(evidence(user)) == 1 and stored(factor, user)[0] == int(counts)


def test_a_wrong_assertion_records_nothing_and_is_counted_toward_the_lock() -> None:
    user, _, authenticator, factor = signin.passkey_user()
    client = session(user)
    assert confirm(client, authenticator.assertion(begun(client), uv=False)) == WRONG
    assert evidence(user) == [] and factor_count(user.id) == 1 and lock_run(user.id) == 1
    assert stored(factor, user) == (0, None) and probe(client) == 403


@pytest.mark.parametrize("case", sorted(signin.DECOYS))
def test_every_assertion_that_is_not_the_users_gets_one_answer_and_one_count(case: str) -> None:
    user, _, authenticator, factor = signin.passkey_user()
    answering = signin.DECOYS[case](user, authenticator)
    client = session(user)
    challenge, events = begun(client), lookups()
    credential = answering.assertion(challenge)
    response = post(client, FINISH, {"purpose": CHANGE, "credential": credential})
    assert (response.status_code, response.content) == (401, b'{"error": "passkey-wrong"}')
    assert response["Cache-Control"] == "no-store"
    assert factor_count(user.id) == 1 and lock_run(user.id) == 1 and lookups() == events + 1
    assert evidence(user) == [] and stored(factor, user) == (0, None)


@pytest.mark.parametrize("owner", ["another-user", "another-agency"])
def test_a_blob_that_names_anyone_but_the_signed_in_user_and_agency_is_refused(
    owner: str, agency_b: uuid.UUID
) -> None:
    user, _, _, _ = signin.passkey_user()
    named = (uuid.uuid4(), user.agency_id) if owner == "another-user" else (user.id, agency_b)
    authenticator = SoftAuthenticator()
    factor = signin.with_passkey(user, authenticator, owner=named)
    client = session(user)
    assert confirm(client, authenticator.assertion(begun(client))) == WRONG
    assert stored(factor, user) == (0, None) and evidence(user) == []


@pytest.mark.parametrize("purpose", ["login", "register", "other-user"])
def test_a_challenge_for_another_purpose_or_user_is_refused_and_spent(purpose: str) -> None:
    user, _, authenticator, factor = signin.passkey_user()
    client = session(user)
    request = RequestFactory().post("/")
    request.session = signin.session_of(client)
    kind = "stepup" if purpose == "other-user" else purpose
    named = uuid.uuid4() if purpose == "other-user" else user.id
    challenge = passkey._issue(request, kind, named)  # type: ignore[arg-type]
    request.session.save()
    assert confirm(client, authenticator.assertion(challenge)) == WRONG
    assert passkey.CHALLENGE not in signin.session_of(client)
    assert evidence(user) == [] and stored(factor, user) == (0, None)


def test_a_stepup_challenge_is_refused_at_sign_in_and_a_login_one_at_step_up() -> None:
    user, _, authenticator, factor = signin.passkey_user()
    client, browser = session(user), signin.pending(user)
    stepup_challenge, login_challenge = begun(client), signin.begun(browser)
    login_record = signin.session_of(browser)[passkey.CHALLENGE]
    plant(browser, signin.session_of(client)[passkey.CHALLENGE])
    plant(client, login_record)
    assert signin.finish(browser, authenticator.assertion(stepup_challenge)) == WRONG
    assert confirm(client, authenticator.assertion(login_challenge)) == WRONG
    assert evidence(user) == [] and stored(factor, user) == (0, None)


def test_no_assertion_is_begun_for_a_user_without_a_passkey_in_use() -> None:
    user, _, _ = sign_in.signing_in()
    signin.with_passkey(user, SoftAuthenticator(), retired=True)
    client = session(user)
    assert answer(post(client, BEGIN, {})) == NO_PASSKEY
    assert passkey.CHALLENGE not in signin.session_of(client)


def test_a_retired_passkey_cannot_step_up_but_its_earlier_evidence_still_counts() -> None:
    """Retiring keeps the row (FK NO ACTION), so evidence naming it stays genuine for its age."""
    user, _, authenticator, factor = signin.passkey_user()
    client = session(user)
    assert confirm(client, authenticator.assertion(begun(client)))[0] == 200
    challenge = begun(client)
    with with_agency(user.agency_id):
        UserFactor.objects.filter(id=factor).update(
            retired_at=timezone.now(), public_key=None, lookup_blob_ct=None
        )
    assert confirm(client, authenticator.assertion(challenge)) == WRONG
    assert len(evidence(user)) == 1 and probe(client) == 200
    assert answer(post(client, BEGIN, {})) == NO_PASSKEY


def test_wrong_passkeys_and_codes_at_step_up_share_the_lock_with_sign_in(clock: Clock) -> None:
    user, secret, authenticator, factor = signin.passkey_user()
    client = session(user)
    for n in range(settings.SKIW_AUTH_LOCK_AFTER):
        if factor_count(user.id) >= LIMIT:
            clock.advance(WINDOW)
        if n % 2:
            assert answer(step_up(client, sign_in.wrong_for(secret)))[0] == 401
        else:
            assert confirm(client, authenticator.assertion(begun(client), uv=False)) == WRONG
    assert lock_markers(user.id) == 1
    clock.advance(WINDOW)  # a fresh budget, but the lock holds
    challenge, events = begun(client), lookups()
    assert confirm(client, authenticator.assertion(challenge)) == LIMITED
    assert lookups() == events  # locked: nothing looked up
    assert attempt(sign_in.pending_login(user), sign_in.code_at(secret, sign_in.STEP)) == "limited"
    assert evidence(user) == [] and stored(factor, user) == (0, None)


def test_past_the_shared_budget_nothing_is_looked_up() -> None:
    user, secret, authenticator, _ = signin.passkey_user()
    client = session(user)
    for _ in range(LIMIT):
        assert attempt(sign_in.pending_login(user), sign_in.wrong_for(secret)) == "wrong_code"
    challenge, events = begun(client), lookups()
    assert confirm(client, authenticator.assertion(challenge)) == LIMITED
    assert lookups() == events and evidence(user) == []


@pytest.mark.parametrize(
    "body",
    [
        {"purpose": CHANGE},
        {"credential": {}},
        {"purpose": "nothing-listed", "credential": {}},
        {"purpose": CHANGE, "credential": "x"},
        {"purpose": CHANGE, "credential": {}, "code": "123456"},
    ],
)
def test_a_body_that_cannot_be_a_step_up_is_400_and_takes_nothing(body: object) -> None:
    user, _, _, _ = signin.passkey_user()
    client = session(user)
    begun(client)
    assert answer(post(client, FINISH, body)) == (400, {"error": "invalid"})
    assert passkey.CHALLENGE in signin.session_of(client) and factor_count(user.id) == 0


def test_a_totp_step_up_is_unchanged_for_a_user_with_a_passkey() -> None:
    user, secret, _, _ = signin.passkey_user()
    client = session(user)
    assert answer(step_up(client, sign_in.code_at(secret, sign_in.STEP)))[0] == 200
    (row,) = evidence(user)
    with with_agency(user.agency_id):
        assert UserFactor.objects.get(id=row.factor_id or uuid.uuid4()).kind == "totp"


def test_verification_cannot_run_without_a_discovery() -> None:
    """PR 157 R2 P2: `_verify` takes only a `Discovered`, which only `_discover` can make."""
    challenge = passkey.Challenge(bytes(32), timezone.now())
    with pytest.raises(TypeError, match="discovery"):
        assertion.Discovered(uuid.uuid4(), uuid.uuid4(), b"\x01", challenge, object())
