"""Passkey ceremonies against a software authenticator (accounts.auth.passkey; plan M3 §4 M3g:
"a passkey is checked for user verification, origin, RP ID and sign count"). No database: the
challenge is read from the options as the browser would; consuming it is
test_passkey_challenge_live.py."""

import uuid
from typing import Any

import cbor2
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from django.http import HttpRequest
from django.test import RequestFactory
from django.utils import timezone

from accounts.auth import passkey
from accounts.auth.passkey import Challenge
from accounts.session import SessionStore

from .authenticator import ORIGIN, RP_ID, SoftAuthenticator, b64url, unb64url

USER = uuid.uuid4()


@pytest.fixture(autouse=True)
def relying_party(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", RP_ID)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", ORIGIN)


def request() -> HttpRequest:
    req = RequestFactory().post("/")
    req.session = SessionStore()
    return req


def challenge() -> Challenge:
    return Challenge(b"\x07" * 32, timezone.now())


def registered(auth: SoftAuthenticator) -> passkey.Registered:
    ch = challenge()
    result = passkey.verify_registration(auth.register(ch.value), ch)
    assert result is not None
    return result


def asserted(
    auth: SoftAuthenticator, stored: passkey.Registered, stored_count: int, **kw: Any
) -> int | None:
    ch = challenge()
    return passkey.verify_assertion(
        auth.assertion(ch.value, **kw), ch, stored.credential_id, stored.public_key, stored_count
    )


def test_registration_options_require_user_verification_and_exclude_existing() -> None:
    req = request()
    existing = [b"\x01" * 16]
    options = passkey.begin_registration(req, USER, "a@example.test", existing)
    assert options["rp"] == {"id": RP_ID, "name": "SKIW Assistant"}
    assert options["user"]["id"] == b64url(USER.bytes)
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["authenticatorSelection"]["residentKey"] == "preferred"
    assert options["attestation"] == "none"
    assert [p["alg"] for p in options["pubKeyCredParams"]] == [-8, -7, -257]
    assert [c["id"] for c in options["excludeCredentials"]] == [b64url(existing[0])]
    stored = req.session[passkey.CHALLENGE]
    assert stored["purpose"] == "register" and stored["user"] == str(USER)
    assert unb64url(options["challenge"]) == unb64url(stored["value"])
    assert len(unb64url(stored["value"])) == 32


def test_assertion_options_allow_only_the_users_passkeys_and_require_verification() -> None:
    req = request()
    options = passkey.begin_assertion(req, "login", USER, [b"\x02" * 20])
    assert options["rpId"] == RP_ID and options["userVerification"] == "required"
    assert [c["id"] for c in options["allowCredentials"]] == [b64url(b"\x02" * 20)]
    assert req.session[passkey.CHALLENGE]["purpose"] == "login"


def test_each_ceremony_gets_a_new_challenge() -> None:
    req = request()
    first = passkey.begin_assertion(req, "stepup", USER, [])["challenge"]
    second = passkey.begin_assertion(req, "stepup", USER, [])["challenge"]
    assert first != second and req.session[passkey.CHALLENGE]["value"] == second


def test_a_registration_then_assertions_verify() -> None:
    auth = SoftAuthenticator()
    stored = registered(auth)
    assert stored.credential_id == auth.credential_id and stored.sign_count == 0
    assert asserted(auth, stored, 0) == 1
    assert asserted(auth, stored, 1) == 2


@pytest.mark.parametrize(
    "wrong",
    [
        {"uv": False},
        {"origin": "https://localhost:8000"},
        {"origin": "http://localhost:8001"},
        {"rp_id": "evil.test"},
        {"sent_id": b"\x09" * 16},
    ],
    ids=["no-user-verification", "other-scheme", "other-port", "other-rp-id", "other-id"],
)
def test_a_registration_is_refused(wrong: dict[str, Any]) -> None:
    ch = challenge()
    assert passkey.verify_registration(SoftAuthenticator().register(ch.value, **wrong), ch) is None


def test_a_registration_for_another_challenge_is_refused() -> None:
    credential = SoftAuthenticator().register(b"\x08" * 32)
    assert passkey.verify_registration(credential, challenge()) is None


@pytest.mark.parametrize(
    "wrong",
    [
        {"uv": False},
        {"origin": "https://localhost:8000"},
        {"rp_id": "evil.test"},
        {"signer": ec.generate_private_key(ec.SECP256R1())},
        {"sent_id": b"\x09" * 16},
    ],
    ids=["no-user-verification", "other-origin", "other-rp-id", "other-key", "other-id"],
)
def test_an_assertion_is_refused(wrong: dict[str, Any]) -> None:
    auth = SoftAuthenticator()
    assert asserted(auth, registered(auth), 0, **wrong) is None


def test_an_assertion_for_another_challenge_is_refused() -> None:
    auth = SoftAuthenticator()
    stored = registered(auth)
    credential = auth.assertion(b"\x08" * 32)
    assert (
        passkey.verify_assertion(
            credential, challenge(), stored.credential_id, stored.public_key, 0
        )
        is None
    )


@pytest.mark.parametrize(
    ("stored", "sent", "result"), [(5, 6, 6), (0, 3, 3), (5, 5, None), (5, 4, None), (5, 0, None)]
)
def test_the_sign_count_must_rise(stored: int, sent: int, result: int | None) -> None:
    auth = SoftAuthenticator()
    assert asserted(auth, registered(auth), stored, count=sent) == result


def test_an_authenticator_without_a_counter_keeps_sending_zero() -> None:
    """WebAuthn: 0 means no counter (most synced passkeys); accepted, DECISIONS M3g-1."""
    auth = SoftAuthenticator(counts=False)
    stored = registered(auth)
    assert asserted(auth, stored, 0) == 0 and asserted(auth, stored, 0) == 0


@pytest.mark.parametrize(
    "mangle",
    [
        lambda c: "not a dict",
        lambda c: {**c, "rawId": c["rawId"] + "="},
        lambda c: {**c, "rawId": "!!"},
        lambda c: {**c, "id": "other"},
        lambda c: {**c, "rawId": b64url(b""), "id": ""},
        lambda c: {**c, "rawId": b64url(b"\x01" * 1024), "id": b64url(b"\x01" * 1024)},
        lambda c: {**c, "response": {}},
        lambda c: {**c, "response": {**c["response"], "attestationObject": b64url(b"\xff")}},
        lambda c: {**c, "response": {**c["response"], "clientDataJSON": b64url(b"{")}},
        lambda c: {**c, "type": "other"},
    ],
)
def test_a_malformed_registration_is_refused_without_raising(mangle: Any) -> None:
    ch = challenge()
    assert passkey.verify_registration(mangle(SoftAuthenticator().register(ch.value)), ch) is None


@pytest.mark.parametrize(
    "cose",
    [
        cbor2.dumps({1: 2, 3: -7, -1: 1}),  # EC2 with no x or y: the library raises KeyError
        cbor2.dumps({1: 2, 3: -35, -1: 2, -2: bytes(48), -3: bytes(48)}),  # ES384, not pinned
        cbor2.dumps([1, 2]),
        cbor2.dumps(7),
    ],
)
def test_a_registration_with_a_bad_public_key_is_refused_without_raising(cose: bytes) -> None:
    ch = challenge()
    credential = SoftAuthenticator().register(ch.value, cose=cose)
    assert passkey.verify_registration(credential, ch) is None


@pytest.mark.parametrize(
    "mangle",
    [
        lambda c: [c],
        lambda c: {**c, "response": {**c["response"], "authenticatorData": b64url(b"\x00")}},
        lambda c: {**c, "response": {**c["response"], "signature": b64url(b"\x30\x00")}},
        lambda c: {**c, "response": {**c["response"], "clientDataJSON": 7}},
        lambda c: {**c, "response": None},
    ],
)
def test_a_malformed_assertion_is_refused_without_raising(mangle: Any) -> None:
    auth = SoftAuthenticator()
    stored = registered(auth)
    ch = challenge()
    credential = mangle(auth.assertion(ch.value))
    assert (
        passkey.verify_assertion(credential, ch, stored.credential_id, stored.public_key, 0) is None
    )


def test_asserted_id_reads_only_a_well_formed_id() -> None:
    credential = SoftAuthenticator(credential_id=b"\x05" * 32).assertion(b"\x00" * 32)
    assert passkey.asserted_id(credential) == b"\x05" * 32
    assert passkey.asserted_id({**credential, "id": "x"}) is None
    assert passkey.asserted_id(None) is None


def test_a_refusal_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    ch = challenge()
    with caplog.at_level("DEBUG"):
        passkey.verify_registration(SoftAuthenticator().register(ch.value, uv=False), ch)
        passkey.verify_registration(SoftAuthenticator().register(ch.value, origin="https://x"), ch)
    assert caplog.records == []
