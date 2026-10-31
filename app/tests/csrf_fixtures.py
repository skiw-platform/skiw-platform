"""Request fixtures per route name for the CSRF gate (plan M2d). Only how to build a request:
path parameters and a minimal body. Methods and auth kind come from route() (config.routes), never
from here, so a new method on a route is tested without touching this file."""

from dataclasses import dataclass, field


# A logged-in session joins the fixture with M3 (there is no login before it): until then every
# case runs as a browser without a session. CSRF_USE_SESSIONS is off, so the check is the same.
@dataclass(frozen=True)
class Fixture:
    path_kwargs: dict[str, str] = field(default_factory=dict)
    body: bytes = b"{}"


FIXTURES: dict[str, Fixture] = {
    "healthz": Fixture(),
    "readyz": Fixture(),
    "asset": Fixture(path_kwargs={"path": "index-abc.js"}),
    "shell": Fixture(),
    "csrf-probe": Fixture(),  # test only: tests.csrf_urls
}
