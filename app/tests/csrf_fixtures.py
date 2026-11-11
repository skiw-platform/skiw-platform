"""Request fixtures per route name for the CSRF gate (plan M2d). Only how to build a request:
path parameters and a minimal body. Methods and auth kind come from route() (config.routes), never
from here, so a new method on a route is tested without touching this file."""

from dataclasses import dataclass, field


# Every case runs once as a browser without a session (test_csrf_gate.py) and, for the mutating
# routes, once signed in through accounts.auth.login() (test_csrf_gate_live.py, M3d).
@dataclass(frozen=True)
class Fixture:
    path_kwargs: dict[str, str] = field(default_factory=dict)
    body: bytes = b"{}"
    # The status the view gives `body` once CSRF passes, when that is a refusal on purpose; None
    # means a success (or 400/422). The login steps answer an empty body as a failed login.
    answers: int | None = None


FIXTURES: dict[str, Fixture] = {
    "healthz": Fixture(),
    "readyz": Fixture(),
    "asset": Fixture(path_kwargs={"path": "index-abc.js"}),
    "shell": Fixture(),
    "auth-login": Fixture(answers=401),
    "auth-second-factor": Fixture(),  # no "code": 400
    "auth-enrol": Fixture(answers=401),
    "auth-enrol-totp": Fixture(answers=401),  # no enrolment session: expired
    "auth-enrol-totp-confirm": Fixture(),  # no "code": 400
    "auth-stepup": Fixture(),  # an authorized_action; signed in, no "purpose" or "code": 400
    "csrf-probe": Fixture(),  # test only: tests.csrf_urls
    "action-probe": Fixture(),  # test only: tests.csrf_urls, an authorized_action
    "stepup-probe": Fixture(answers=403),  # test only: signed in without a step-up
}
