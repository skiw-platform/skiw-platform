"""SKIW_WEBAUTHN_RP_ID and SKIW_WEBAUTHN_ORIGIN (plan M3g, owner Q8 (a)): the RP ID is a lowercase
hostname, the origin exactly https://<RP ID> (the value when it is unset, as on hosts), or http(s)
with a port only for localhost. The error names the variable, never the value."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env


def read(monkeypatch: pytest.MonkeyPatch, rp_id: str, origin: str) -> env.WebAuthnSettings:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", rp_id)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", origin)
    return env.webauthn()


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        ("skiw.example.my", "https://skiw.example.my"),
        ("a-b.c1.test", "https://a-b.c1.test"),
        ("localhost", "http://localhost:8000"),
        ("localhost", "https://localhost"),
        ("localhost", "http://localhost:65535"),
    ],
)
def test_a_hostname_and_its_exact_origin_are_read(
    monkeypatch: pytest.MonkeyPatch, rp_id: str, origin: str
) -> None:
    assert read(monkeypatch, rp_id, origin) == env.WebAuthnSettings(rp_id, origin)


@pytest.mark.parametrize(
    "rp_id",
    [
        "",
        "Skiw.test",
        "https://skiw.test",
        "skiw.test:443",
        "skiw.test.",
        ".skiw.test",
        "-skiw.test",
        "skiw-.test",
        "127.0.0.1",
        "10.0.0.1",
        "[::1]",
        "skiw test",
        "a" * 64 + ".test",
        ("a" * 63 + ".") * 4 + "test",
        "skiw.tést",
    ],
)
def test_anything_but_a_lowercase_hostname_is_refused(
    monkeypatch: pytest.MonkeyPatch, rp_id: str
) -> None:
    with pytest.raises(ImproperlyConfigured, match=r"^SKIW_WEBAUTHN_RP_ID ") as error:
        read(monkeypatch, rp_id, f"https://{rp_id}")
    assert rp_id == "" or rp_id not in str(error.value)


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        ("skiw.test", ""),
        ("skiw.test", "http://skiw.test"),
        ("skiw.test", "https://skiw.test/"),
        ("skiw.test", "https://skiw.test:443"),
        ("skiw.test", "https://SKIW.test"),
        ("skiw.test", "https://other.skiw.test"),
        ("skiw.test", "http://localhost:8000"),  # the localhost exception needs RP ID localhost
        ("app.skiw.test", "https://skiw.test"),
        ("localhost", "http://localhost:65536"),
        ("localhost", "http://localhost:0"),
        ("localhost", "http://localhost:"),
        ("localhost", "http://127.0.0.1:8000"),
        ("localhost", "http://localhost:8000/"),
        ("localhost", "ftp://localhost"),
    ],
)
def test_any_other_origin_is_refused(
    monkeypatch: pytest.MonkeyPatch, rp_id: str, origin: str
) -> None:
    with pytest.raises(ImproperlyConfigured, match=r"^SKIW_WEBAUTHN_ORIGIN ") as error:
        read(monkeypatch, rp_id, origin)
    assert origin == "" or origin not in str(error.value)


def test_an_unset_rp_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKIW_WEBAUTHN_RP_ID", raising=False)
    monkeypatch.setenv("SKIW_WEBAUTHN_ORIGIN", "https://skiw.test")
    with pytest.raises(ImproperlyConfigured, match="SKIW_WEBAUTHN_RP_ID"):
        env.webauthn()


@pytest.mark.parametrize("rp_id", ["skiw.test", "localhost"])
def test_an_unset_origin_is_tls_on_the_rp_id(monkeypatch: pytest.MonkeyPatch, rp_id: str) -> None:
    monkeypatch.setenv("SKIW_WEBAUTHN_RP_ID", rp_id)
    monkeypatch.delenv("SKIW_WEBAUTHN_ORIGIN", raising=False)
    assert env.webauthn() == env.WebAuthnSettings(rp_id, f"https://{rp_id}")
