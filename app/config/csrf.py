"""CSRF_FAILURE_VIEW (spec T6; plan M2d). The `X-Skiw-Csrf: rejected` header lets the CSRF gate
tell a CSRF refusal from any other 403. The Django reason can carry the client's Origin or
Referer, so only a fixed code taken from its prefix is sent, never the reason itself."""

from django.http import HttpRequest, HttpResponse

CODES = (
    ("Origin checking failed", "origin"),
    ("Referer checking failed", "referer"),
    ("CSRF cookie not set", "no-cookie"),
    ("CSRF cookie", "cookie-format"),
    ("CSRF token missing", "token-missing"),
    ("CSRF token from", "token-invalid"),
)


def failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    code = next((code for prefix, code in CODES if reason.startswith(prefix)), "other")
    response = HttpResponse(code, status=403, content_type="text/plain")
    response["X-Skiw-Csrf"] = "rejected"
    return response
