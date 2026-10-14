"""TEST ONLY: stand-in upstream for the 25 s long-poll check (no long-poll endpoint before M14).

Runs under the network alias `web`, so Caddy reaches it through the real `reverse_proxy web:8000`.
"""

import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LONG_POLL_S = 25


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/long-poll":
            time.sleep(LONG_POLL_S)
        body = b"done"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()  # noqa: S104 (container only)
