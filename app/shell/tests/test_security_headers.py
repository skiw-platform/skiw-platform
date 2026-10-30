"""Security headers on Django responses (spec T6, §9 M2, UNI-17)."""

import asyncio
import re
from pathlib import Path

import pytest
from django.http.response import HttpResponseBase
from django.test import AsyncClient, Client

CSP = re.compile(
    r"default-src 'self'; script-src 'nonce-([A-Za-z0-9_-]{22})' 'strict-dynamic'; "
    r"object-src 'none'; frame-ancestors 'none'"
)
HSTS = "max-age=31536000"  # owner Q1 (a); equal to infra/host/caddy/edge.caddy


def csp_nonce(response: HttpResponseBase) -> str:
    values = [v for k, v in response.items() if k.lower() == "content-security-policy"]
    assert len(values) == 1
    match = CSP.fullmatch(values[0])
    assert match is not None, values[0]
    return match[1]


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("get", "/", 200),
        ("get", "/healthz", 200),
        ("get", "/assets/index-abc.js", 200),
        ("get", "/no-such-page", 404),
        ("post", "/healthz", 405),
    ],
)
def test_every_response_carries_the_headers(
    dist: Path, method: str, path: str, status: int
) -> None:
    response = getattr(Client(), method)(path)
    assert response.status_code == status
    csp_nonce(response)
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"


def test_each_response_gets_a_fresh_nonce(dist: Path) -> None:
    assert csp_nonce(Client().get("/")) != csp_nonce(Client().get("/"))


def test_shell_script_carries_the_header_nonce(dist: Path) -> None:
    response = Client().get("/")
    body = response.content.decode()
    assert f'<script type="module" nonce="{csp_nonce(response)}" src=' in body
    assert body.count("<script") == 1


def test_shell_is_never_cached(dist: Path) -> None:
    assert Client().get("/")["Cache-Control"] == "no-store"


def test_hsts_only_on_secure_requests(dist: Path) -> None:
    assert Client().get("/", secure=True)["Strict-Transport-Security"] == HSTS
    assert "Strict-Transport-Security" not in Client().get("/")


def test_headers_on_the_async_path(dist: Path) -> None:
    response = asyncio.run(AsyncClient().get("/"))
    assert response.status_code == 200
    assert csp_nonce(response) in response.content.decode()
    assert response["X-Frame-Options"] == "DENY"
