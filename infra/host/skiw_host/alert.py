"""The alert sender for skiw-health (spec §8.4 H7, D17, D19; amendment 2026-10-24 (alert channel);
runbook health-alerts.md).

An alert is exactly three fields: the check's name, the host (`<environment>:<node name>`) and one
value. The value is built by the check from counts, names and thresholds, never from database rows,
application logs or tool output; it is still scrubbed here (UNI-09): anything shaped like an email
address or a Malaysian IC number (12 digits, dashes or not) is replaced, control characters are
removed and the length is capped.

Every alert goes to the journal first (LOG_ALERT, ident skiw-health). The channel off the host is a
Telegram bot of the owner (G8 (b), UNI-11 recorded 2026-10-24): SKIW_ALERT_CHANNEL `telegram` and
SKIW_ALERT_TO the chat id; empty, nothing leaves the host. One HTTPS POST to the Bot API sendMessage
per message, standard library only: the URL is a constant, no environment proxy, no redirect
followed, the certificate verified, plain text, one deadline per message. The bot token is
/etc/skiw/secrets/alert_credential (root, 0400, UNI-08), read when a message is sent and checked
before it goes into the URL; it is never printed or journaled, and a failure is named by its type
(and an HTTP status) only, because the URL holds the token.
"""

import json
import os
import re
import signal
import ssl
import stat
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from types import FrameType
from typing import IO, Protocol

from skiw_host import apply
from skiw_host.bootstrap_secrets import Refused
from skiw_host.hardening import SECRET_MODE, SECRETS, Owner
from skiw_host.secrets import ALERT_CHANNEL, ALERT_CREDENTIAL

CHECK = re.compile(r"[a-z][a-z0-9-]{0,40}")
HOST = re.compile(r"(production|staging):[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+")
NRIC = re.compile(r"(?<!\d)\d{6}-?\d{2}-?\d{4}(?!\d)")  # MyKad: YYMMDD-PB-###G
VALUE_MAX = 200
SEND_S = 10  # one deadline for a whole message (amendment §8), and each socket wait
CHAT = re.compile(r"-?[1-9][0-9]{0,15}")  # a chat id: at most 52 bits, groups negative
# A bot token: the bot's number, a colon, then the secret. The exact lengths are not documented
# [A]; the characters are what keeps the token from changing the URL.
TOKEN = re.compile(r"[0-9]{5,16}:[A-Za-z0-9_-]{30,64}")
CREDENTIAL = f"{SECRETS}/{ALERT_CREDENTIAL}"
CREDENTIAL_MAX = 128  # bytes; a token is about 46
ANSWER_MAX = 1 << 16  # bytes of a Bot API answer read; more is a failure
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
    """The far side answered, but not with status 200 and `ok: true`."""


class UnsafeCredential(Exception):
    """The token file is not a root 0400 file with one link holding one bot token."""


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


def credential(root: Path, owner: Owner) -> str:
    """The bot token, read through no link and no writable directory, the open file a regular
    root:root 0400 file with one link and at most CREDENTIAL_MAX bytes, in the token format."""
    path = root / CREDENTIAL
    try:
        apply.untrusted(root, [CREDENTIAL], lambda p: owner(p, p.lstat()))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        raise  # named as it is: the channel is on, the token is not placed yet
    except (Refused, OSError):  # a link, or a writable directory on the way
        raise UnsafeCredential from None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or owner(path, info) != (0, 0)
            or stat.S_IMODE(info.st_mode) != SECRET_MODE
            or info.st_nlink != 1
            or info.st_size > CREDENTIAL_MAX
        ):
            raise UnsafeCredential
        data = os.read(fd, CREDENTIAL_MAX + 1)
    finally:
        os.close(fd)
    token = data.decode("ascii", "replace").removesuffix("\n")
    if len(data) > CREDENTIAL_MAX or not TOKEN.fullmatch(token):
        raise UnsafeCredential
    return token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is never followed: urllib then raises HTTPError with the 3xx status."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        return None


class Telegram:
    def __init__(self, chat: str, token: Callable[[], str], context: Context) -> None:
        self.chat, self.token, self.context = chat, token, context

    def send(self, alert: Alert) -> None:
        """One Bot API sendMessage (checked 2026-10-25, core.telegram.org/bots/api): chat_id and
        the plain text (no parse_mode), link previews off. The URL is this constant; only the chat
        id is configurable."""
        body = {
            "chat_id": int(self.chat),
            "text": alert.render(),
            "link_preview_options": {"is_disabled": True},
        }
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token()}/sendMessage",
            data=json.dumps(body).encode("ascii"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),  # never https_proxy: the URL holds the token
            NoRedirect(),
            urllib.request.HTTPSHandler(context=self.context()),
        )
        with opener.open(request, timeout=SEND_S) as answer:
            status, data = answer.status, answer.read(ANSWER_MAX + 1)
        try:
            found = json.loads(data)
        except ValueError:
            raise Undelivered from None
        if status != 200 or len(data) > ANSWER_MAX or not isinstance(found, dict):
            raise Undelivered
        if found.get("ok") is not True:
            raise Undelivered


def channel(values: dict[str, str], token: Callable[[], str], context: Context) -> Transport | None:
    """The channel the host env file names, or None (no channel). A bad setting refuses (exit 2);
    the token file is read only when a message is sent (unsafe there: not delivered, exit 3)."""
    name, chat = values.get("SKIW_ALERT_CHANNEL", ""), values.get("SKIW_ALERT_TO", "")
    if name == "" and chat == "":
        return None
    if name != ALERT_CHANNEL:
        raise Refused(f"SKIW_ALERT_CHANNEL is not {ALERT_CHANNEL}, or empty with SKIW_ALERT_TO")
    if not CHAT.fullmatch(chat):
        raise Refused("SKIW_ALERT_TO is not a Telegram chat id (digits, an optional leading -)")
    return Telegram(chat, token, context)


def failure(exc: BaseException) -> str:
    """The type, an HTTP status, or the type of a connection failure's cause; never the text."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTPError {int(exc.code)}"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, BaseException):
        return f"URLError {type(exc.reason).__name__}"
    return type(exc).__name__


def deliver(
    alert: Alert, transport: Transport | None, journal: Journal, bound: float | None = None
) -> bool:
    """The journal line, then the channel; True only when the channel accepted the message."""
    journal(f"{alert.check} {alert.host} {alert.value}")
    if transport is None:
        journal(f"{alert.check}: not sent off the host: no alert channel")
        return False
    try:
        with deadline(SEND_S if bound is None else bound):
            transport.send(alert)
    except Exception as exc:  # every failure is a failed delivery, named by type only
        journal(f"{alert.check}: not sent off the host ({failure(exc)})")
        return False
    return True
