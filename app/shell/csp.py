"""Nonce-based Content-Security-Policy on every Django response (spec T6, UNI-17).

Django 5.2 has no CSP middleware. The nonce lives in request.META under a private key so the
shell view can put it on its <script>; a fresh one is made for every request.
"""

import secrets

from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils.deprecation import MiddlewareMixin

HEADER = "Content-Security-Policy"
POLICY = (
    "default-src 'self'; script-src 'nonce-{nonce}' 'strict-dynamic'; "
    "object-src 'none'; frame-ancestors 'none'"
)
_META_KEY = "skiw.csp_nonce"


def nonce(request: HttpRequest) -> str:
    value: str = request.META[_META_KEY]
    return value


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        request.META[_META_KEY] = secrets.token_urlsafe(16)

    def process_response(
        self, request: HttpRequest, response: HttpResponseBase
    ) -> HttpResponseBase:
        response.headers[HEADER] = POLICY.format(nonce=nonce(request))
        return response
