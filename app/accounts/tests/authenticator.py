"""A software WebAuthn authenticator for tests (plan M3 §4 M3g): an ES256 key, "none"
attestation, and the JSON a browser hands the app. Each ceremony can be made wrong one way at a
time (origin, RP ID, user verification, challenge, count, key, ids)."""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

RP_ID = "localhost"
ORIGIN = "http://localhost:8000"
UP, UV, AT = 0x01, 0x04, 0x40


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _new_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@dataclass
class SoftAuthenticator:
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(16))
    key: ec.EllipticCurvePrivateKey = field(default_factory=_new_key)
    sign_count: int = 0
    counts: bool = True  # False: always sends 0, as most synced passkeys do

    def cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        x, y = numbers.x.to_bytes(32, "big"), numbers.y.to_bytes(32, "big")
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: x, -3: y})

    def _client_data(self, kind: str, challenge: bytes, origin: str) -> bytes:
        data = {
            "type": kind,
            "challenge": b64url(challenge),
            "origin": origin,
            "crossOrigin": False,
        }
        return json.dumps(data).encode()

    def _ids(self, sent_id: bytes | None) -> dict[str, str]:
        raw = self.credential_id if sent_id is None else sent_id
        return {"id": b64url(raw), "rawId": b64url(raw), "type": "public-key"}

    def register(
        self,
        challenge: bytes,
        *,
        uv: bool = True,
        origin: str = ORIGIN,
        rp_id: str = RP_ID,
        sent_id: bytes | None = None,
    ) -> dict[str, Any]:
        """The PublicKeyCredential JSON of navigator.credentials.create()."""
        attested = (
            bytes(16) + len(self.credential_id).to_bytes(2, "big") + self.credential_id
        ) + self.cose_key()
        flags = UP | AT | (UV if uv else 0)
        auth_data = (
            hashlib.sha256(rp_id.encode()).digest()
            + bytes([flags])
            + self.sign_count.to_bytes(4, "big")
            + attested
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            **self._ids(sent_id),
            "response": {
                "clientDataJSON": b64url(self._client_data("webauthn.create", challenge, origin)),
                "attestationObject": b64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def assertion(
        self,
        challenge: bytes,
        *,
        uv: bool = True,
        origin: str = ORIGIN,
        rp_id: str = RP_ID,
        count: int | None = None,
        signer: ec.EllipticCurvePrivateKey | None = None,
        sent_id: bytes | None = None,
    ) -> dict[str, Any]:
        """The PublicKeyCredential JSON of navigator.credentials.get(); the counter moves on."""
        if count is None:
            self.sign_count += 1 if self.counts else 0
            count = self.sign_count
        flags = UP | (UV if uv else 0)
        auth_data = (
            hashlib.sha256(rp_id.encode()).digest() + bytes([flags]) + count.to_bytes(4, "big")
        )
        client_data = self._client_data("webauthn.get", challenge, origin)
        signed = auth_data + hashlib.sha256(client_data).digest()
        signature = (signer or self.key).sign(signed, ec.ECDSA(hashes.SHA256()))
        return {
            **self._ids(sent_id),
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(signature),
            },
            "clientExtensionResults": {},
        }
