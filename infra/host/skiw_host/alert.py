"""The alert sender for skiw-health (spec §8.4 H7, D17, D19; plan §3 M1j G8; runbook
health-alerts.md).

An alert is exactly three fields: the check's name, the host (`<environment>:<node name>`) and one
value. The value is built by the check from counts, names and thresholds, never from database rows,
application logs or tool output; it is still scrubbed here (UNI-09): anything shaped like an email
address or a Malaysian IC number (12 digits, dashes or not) is replaced, control characters are
removed and the length is capped.

Every alert goes to the journal first (LOG_ALERT, ident skiw-health). The channel off the host is
the Q20 channel, which G8 has not chosen and UNI-11 has not recorded: SKIW_ALERT_CHANNEL is empty
and nothing leaves the host. No transport is built here (M1j-2), so any SKIW_ALERT_* value refuses.
`deliver` already takes a transport: one deadline per message, and a failure is reported by its
exception type only.
"""

import re
import signal
import ssl
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import FrameType
from typing import Protocol

from skiw_host.bootstrap_secrets import Refused

CHECK = re.compile(r"[a-z][a-z0-9-]{0,40}")
HOST = re.compile(r"(production|staging):[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+")
NRIC = re.compile(r"(?<!\d)\d{6}-?\d{2}-?\d{4}(?!\d)")  # MyKad: YYMMDD-PB-###G
VALUE_MAX = 200
SEND_S = 30  # one deadline for a whole message
KEYS = ("SKIW_ALERT_CHANNEL", "SKIW_ALERT_SERVER", "SKIW_ALERT_FROM", "SKIW_ALERT_TO")
Journal = Callable[[str], None]


def scrub(value: str) -> str:
    """UNI-09: no email address, IC number or control character reaches an alert."""
    text = EMAIL.sub("[email]", NRIC.sub("[ic]", value))
    text = "".join(c if c.isprintable() else " " for c in text)
    return text[:VALUE_MAX]


@dataclass(frozen=True)
class Alert:
    check: str
    host: str
    value: str

    def __post_init__(self) -> None:
        if not CHECK.fullmatch(self.check) or not HOST.fullmatch(self.host):
            raise ValueError("an alert's check or host is not a plain name")
        object.__setattr__(self, "value", scrub(self.value))

    def payload(self) -> dict[str, str]:
        return {"check": self.check, "host": self.host, "value": self.value}

    def render(self) -> str:
        return "".join(f"{k}: {v}\n" for k, v in self.payload().items())


class Transport(Protocol):
    def send(self, alert: Alert) -> None: ...


class Undelivered(Exception):
    """The channel did not take the message (or, after a failure this run, was not tried)."""


class Deadline(Exception):
    """The message's deadline passed (SIGALRM)."""


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    """One wall-clock bound around blocking socket calls; a read that drips bytes cannot extend it.
    Main thread only (signals); skiw-health is single-threaded."""

    def expired(signum: int, frame: FrameType | None) -> None:
        raise Deadline

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


Context = Callable[[], ssl.SSLContext]


def channel(values: dict[str, str]) -> Transport | None:
    """None (off): G8 is open and no transport is built (M1j-2). Any setting refuses (exit 2)."""
    if any(values.get(key, "") for key in KEYS):
        raise Refused("SKIW_ALERT_* is set, but no alert transport is built yet (G8 open, M1j-2)")
    return None


def failure(exc: BaseException) -> str:
    """The type only, never the text."""
    return type(exc).__name__


def deliver(
    alert: Alert, transport: Transport | None, journal: Journal, bound: float = SEND_S
) -> bool:
    """The journal line, then the channel; True only when the channel accepted the message."""
    journal(f"{alert.check} {alert.host} {alert.value}")
    if transport is None:
        journal(f"{alert.check}: not sent off the host: no alert channel (G8 open)")
        return False
    try:
        with deadline(bound):
            transport.send(alert)
    except Exception as exc:  # every failure is a failed delivery, named by type only
        journal(f"{alert.check}: not sent off the host ({failure(exc)})")
        return False
    return True
