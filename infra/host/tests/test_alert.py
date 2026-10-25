"""The alert sender (spec §8.4 H7; plan §3 M1j; amendment 2026-10-24; UNI-08, UNI-09).

The payload is exactly check, host and value, and the value is scrubbed. Without a channel the
alert reaches the journal only and is not delivered. The Telegram transport runs unchanged against
a local TLS fake (conftest `tls_server`, a certificate made at test time that also names
api.telegram.org): only the connection is routed there and only that certificate is trusted. The
fake answers as the Bot API does on success, on `ok: false`, with 4xx/5xx and 429, a redirect, a
cut-off or oversized answer, and silence. Every token is generated per run.
"""

import json
import os
import secrets
import socket
import ssl
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import pytest

from skiw_host import alert, hardening
from skiw_host.alert import Alert, Telegram, deliver
from skiw_host.bootstrap_secrets import Refused

HOST = Path(__file__).resolve().parents[1]
WHERE = "staging:vps-1"
API = ("api.telegram.org", 443)
CHAT = "-1001234567890"


def test_the_payload_is_exactly_check_host_and_value() -> None:
    message = Alert("disk", WHERE, "/var/lib/docker space 83% used")
    assert message.payload() == {
        "check": "disk",
        "host": WHERE,
        "value": "/var/lib/docker space 83% used",
    }
    assert (
        message.render() == f"check: disk\nhost: {WHERE}\nvalue: /var/lib/docker space 83% used\n"
    )


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("mail ops.lead@example.com now", "mail [email] now"),
        ("a@b", "[email]"),
        ("ic 900101-14-5678 seen", "ic [ic] seen"),
        ("ic 900101145678", "ic [ic]"),
        ("id=900101145678;", "id=[ic];"),
        ("9001011456789 is 13 digits", "9001011456789 is 13 digits"),  # not an IC shape
        ("line\nbreak\x1b[31m", "line break [31m"),
    ],
)
def test_the_value_is_scrubbed_of_emails_ic_numbers_and_control_characters(
    value: str, shown: str
) -> None:
    assert Alert("x", WHERE, value).value == shown  # UNI-09


def test_the_value_is_capped() -> None:
    assert len(Alert("x", WHERE, "9" * 1000).value) == alert.VALUE_MAX


@pytest.mark.parametrize(
    ("check", "host"), [("Disk", WHERE), ("disk check", WHERE), ("disk", "dev:x"), ("disk", "a@b")]
)
def test_a_check_or_host_that_is_not_a_plain_name_is_refused(check: str, host: str) -> None:
    with pytest.raises(ValueError, match="plain name"):
        Alert(check, host, "v")


class Fake:
    def __init__(
        self, error: BaseException | None = None, wait: float = 0, journal: list[str] | None = None
    ) -> None:
        self.sent: list[Alert] = []
        self.error, self.wait, self.journal = error, wait, journal
        self.lines_before: list[int] = []  # journal lines written before each send

    def send(self, message: Alert) -> None:
        if self.journal is not None:
            self.lines_before.append(len(self.journal))
        if self.wait:
            time.sleep(self.wait)
        if self.error:
            raise self.error
        self.sent.append(message)


def test_without_a_channel_the_alert_goes_to_the_journal_and_is_not_delivered() -> None:
    journal: list[str] = []
    assert deliver(Alert("disk", WHERE, "full"), None, journal.append) is False
    assert journal == [
        f"disk {WHERE} full",
        "disk: not sent off the host: no alert channel",
    ]


@pytest.mark.parametrize("error", [None, ConnectionRefusedError()])
def test_the_journal_line_comes_before_the_send(error: BaseException | None) -> None:
    journal: list[str] = []
    fake = Fake(error, journal=journal)
    assert deliver(Alert("disk", WHERE, "full"), fake, journal.append) is (error is None)
    assert fake.lines_before == [1] and journal[0] == f"disk {WHERE} full"


def test_a_failure_is_named_by_type_never_its_text() -> None:
    planted = secrets.token_hex(16)
    journal: list[str] = []
    error = ConnectionRefusedError(f"refused {planted}")
    assert deliver(Alert("disk", WHERE, "full"), Fake(error), journal.append) is False
    assert journal[-1] == "disk: not sent off the host (ConnectionRefusedError)"
    assert not any(planted in line for line in journal)


def test_one_deadline_bounds_a_send() -> None:
    journal: list[str] = []
    start = time.monotonic()
    assert deliver(Alert("disk", WHERE, "full"), Fake(wait=5), journal.append, bound=0.2) is False
    assert time.monotonic() - start < 2 and journal[-1].endswith("(Deadline)")
    assert alert.SEND_S == 10  # amendment §8: one 10 s deadline per message


# --- the channel setting ---------------------------------------------------------------------


def never() -> str:
    raise AssertionError("the token is read only when a message is sent")


def test_no_channel_is_off() -> None:
    values = {"SKIW_ALERT_CHANNEL": "", "SKIW_ALERT_TO": ""}
    assert alert.channel(values, never, ssl.create_default_context) is None
    assert alert.channel({}, never, ssl.create_default_context) is None


@pytest.mark.parametrize(
    ("name", "chat"),
    [
        ("slack", CHAT),
        ("Telegram", CHAT),
        ("smtp", CHAT),
        ("telegram ", CHAT),
        ("", CHAT),  # a chat id while the channel is off
        ("telegram", ""),
        ("telegram", "ops"),
        ("telegram", "@owner_channel"),
        ("telegram", "42x"),
        ("telegram", "+42"),
        ("telegram", "0"),
        ("telegram", "-0"),
        ("telegram", "4 2"),
        ("telegram", "1" * 17),
        ("telegram", "42/../x"),
    ],
)
def test_a_channel_other_than_telegram_or_a_bad_chat_id_refuses(name: str, chat: str) -> None:
    values = {"SKIW_ALERT_CHANNEL": name, "SKIW_ALERT_TO": chat}
    with pytest.raises(Refused):
        alert.channel(values, never, ssl.create_default_context)


@pytest.mark.parametrize("chat", ["42", CHAT, "1" * 16])
def test_telegram_with_a_chat_id_is_the_channel(chat: str) -> None:
    values = {"SKIW_ALERT_CHANNEL": "telegram", "SKIW_ALERT_TO": chat}
    found = alert.channel(values, never, ssl.create_default_context)
    assert isinstance(found, Telegram) and found.chat == chat


def test_the_host_env_files_hold_no_channel_and_no_mail_keys() -> None:
    for name in ("production.env", "staging.env", "ci.env"):
        lines = (HOST / "env" / name).read_text().splitlines()
        assert "SKIW_ALERT_CHANNEL=" in lines and "SKIW_ALERT_TO=" in lines, name  # set per host
        assert not [x for x in lines if x.startswith(("SKIW_ALERT_SERVER", "SKIW_ALERT_FROM"))]


# --- the token file --------------------------------------------------------------------------


def new_token() -> str:
    return f"{secrets.randbelow(9 * 10**9) + 10**9}:{secrets.token_urlsafe(27)}"


class Store:
    """/etc/skiw/secrets under a temporary root; `owners` stands in for root ownership."""

    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "root"
        self.dir = self.root / hardening.SECRETS
        self.dir.mkdir(parents=True)
        self.dir.chmod(0o700)
        self.path = self.root / alert.CREDENTIAL
        self.owners: dict[Path, tuple[int, int]] = {}

    def owner(self, path: Path, info: os.stat_result) -> tuple[int, int]:
        return self.owners.get(path, (0, 0))

    def put(self, data: bytes, mode: int = 0o400) -> None:
        self.path.unlink(missing_ok=True)
        self.path.write_bytes(data)
        self.path.chmod(mode)

    def read(self) -> str:
        return alert.credential(self.root, self.owner)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def test_the_token_is_read_from_a_root_0400_file(store: Store) -> None:
    token = new_token()
    store.put(f"{token}\n".encode())
    assert store.read() == token
    store.put(token.encode())  # written without a newline
    assert store.read() == token


def test_a_missing_token_file_is_named_as_missing(store: Store) -> None:
    with pytest.raises(FileNotFoundError):
        store.read()


def linked(store: Store) -> None:
    elsewhere = store.root / "elsewhere"
    elsewhere.write_text(f"{new_token()}\n")
    elsewhere.chmod(0o400)
    store.path.symlink_to(elsewhere)


def hard_linked(store: Store) -> None:
    store.put(f"{new_token()}\n".encode())
    os.link(store.path, store.root / "second-name")


def fifo(store: Store) -> None:
    os.mkfifo(store.path, 0o400)


def writable_directory(store: Store) -> None:
    store.put(f"{new_token()}\n".encode())
    store.dir.chmod(0o777)


@pytest.mark.parametrize(
    "spoil",
    [
        linked,
        hard_linked,
        fifo,
        writable_directory,
        lambda s: s.put(f"{new_token()}\n".encode(), 0o440),
        lambda s: s.put(f"{new_token()}\n".encode(), 0o600),
        lambda s: (s.put(f"{new_token()}\n".encode()), s.owners.update({s.path: (1000, 0)})),
        lambda s: (s.put(f"{new_token()}\n".encode()), s.owners.update({s.path: (0, 1000)})),
        lambda s: s.put(b"1" * (alert.CREDENTIAL_MAX + 1)),
    ],
)
def test_an_unsafe_token_file_is_refused(store: Store, spoil: Callable[[Store], object]) -> None:
    spoil(store)
    with pytest.raises(alert.UnsafeCredential):
        store.read()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "123456789",
        "123456789:",
        "123456789:short",
        "abc:" + "A" * 35,
        "1234:" + "A" * 35,  # a bot number too short
        "123456789:" + "A" * 34 + "/x",
        "123456789:" + "A" * 34 + "?x",
        "123456789:" + "A" * 34 + "#",
        "123456789:" + "A" * 34 + "@evil.example",
        "123456789:" + "A" * 34 + " x",
        "123456789:" + "A" * 34 + "\r\nHost: evil.example",
        "123456789:" + "A" * 35 + "\n123456789:" + "A" * 35,  # two lines
        "123456789:" + "A" * 35 + "é",
        " 123456789:" + "A" * 35,
    ],
)
def test_a_malformed_token_is_refused(store: Store, text: str) -> None:
    store.put(f"{text}\n".encode())
    with pytest.raises(alert.UnsafeCredential):
        store.read()


# --- the Bot API, against a local TLS fake ---------------------------------------------------


class Server(Protocol):
    port: int
    handler: Callable[[ssl.SSLSocket], None]

    def client(self) -> ssl.SSLContext: ...

    def close(self) -> None: ...

    @property
    def stop(self) -> "Waiter": ...


class Waiter(Protocol):
    def wait(self, timeout: float) -> bool: ...


def route(server: Server, monkeypatch: pytest.MonkeyPatch, dns: bool = True) -> list[Any]:
    """api.telegram.org:443 reaches the fake; any other address is refused. Returns the
    addresses asked for (a proxy would show up here)."""
    asked: list[Any] = []
    real = socket.create_connection

    def connect(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        asked.append(address)
        if not dns:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        if tuple(address) != API:
            raise ConnectionRefusedError(f"not routed in tests: {address}")
        return real(("127.0.0.1", server.port), *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", connect)
    return asked


def http_request(tls: ssl.SSLSocket) -> tuple[str, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        if not (chunk := tls.recv(65536)):
            break
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    lengths = [x for x in head.split(b"\r\n") if x.lower().startswith(b"content-length:")]
    while lengths and len(body) < int(lengths[0].split(b":")[1]):
        body += tls.recv(65536)
    return head.decode(), body


def answer(status: str, body: bytes, extra: str = "", length: int | None = None) -> bytes:
    size = len(body) if length is None else length
    return f"HTTP/1.1 {status}\r\nContent-Length: {size}\r\n{extra}\r\n".encode() + body


OK = json.dumps({"ok": True, "result": {"message_id": 1}}).encode()
NOT_OK = json.dumps({"ok": False, "error_code": 400, "description": "Bad Request"}).encode()
PAD = '{"ok": true, "pad": "'  # valid and ok, one byte more than is read
BIG = (PAD + "x" * (alert.ANSWER_MAX - 1 - len(PAD)) + '"}').encode()
ANSWERS: dict[str, tuple[bytes | None, str]] = {
    "401": (answer("401 Unauthorized", NOT_OK), "HTTPError 401"),  # revoked token
    "403": (answer("403 Forbidden", NOT_OK), "HTTPError 403"),  # bot removed from the chat
    "429": (answer("429 Too Many Requests", NOT_OK, "Retry-After: 3\r\n"), "HTTPError 429"),
    "500": (answer("500 Internal Server Error", b""), "HTTPError 500"),
    "302": (answer("302 Found", b"", "Location: /bot/elsewhere\r\n"), "HTTPError 302"),
    "307": (answer("307 Temporary Redirect", b"", "Location: //x.test/\r\n"), "HTTPError 307"),
    "ok false": (answer("200 OK", NOT_OK), "Undelivered"),
    "ok missing": (answer("200 OK", b'{"result": true}'), "Undelivered"),
    "ok not true": (answer("200 OK", b'{"ok": "true"}'), "Undelivered"),
    "not json": (answer("200 OK", b"<html>ok</html>"), "Undelivered"),
    "a list": (answer("200 OK", b"[true]"), "Undelivered"),
    "201": (answer("201 Created", OK), "Undelivered"),
    "too large": (answer("200 OK", BIG), "Undelivered"),
    "cut off": (answer("200 OK", OK[:5], length=len(OK)), "Undelivered"),
    "silent": (None, "Deadline"),
}


def bot_api(server: Server, reply: bytes | None, seen: list[tuple[str, bytes]]) -> None:
    def handle(tls: ssl.SSLSocket) -> None:
        seen.append(http_request(tls))
        if reply is None:
            server.stop.wait(30)  # silent
            return
        tls.sendall(reply)

    server.handler = handle


def no_secret_in(token: str, *texts: str) -> None:
    for text in texts:
        assert token not in text and "api.telegram.org" not in text and "/bot" not in text


def test_one_post_with_only_the_chat_the_plain_text_and_no_link_preview(
    tls_server: Server, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    for name in ("https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")  # ignored: never a proxy
    asked = route(tls_server, monkeypatch)
    seen: list[tuple[str, bytes]] = []
    bot_api(tls_server, answer("200 OK", OK), seen)
    token = new_token()
    message = Alert("readyz", WHERE, "status 503 for a@b.example")
    journal: list[str] = []
    bot = Telegram(CHAT, lambda: token, tls_server.client)
    assert deliver(message, bot, journal.append) is True
    assert asked == [API]  # straight to the Bot API, not to the proxy
    [(head, body)] = seen
    lines = head.split("\r\n")
    assert lines[0] == f"POST /bot{token}/sendMessage HTTP/1.1"
    assert "Host: api.telegram.org" in lines and "Content-Type: application/json" in lines
    sent = json.loads(body)
    assert sent == {
        "chat_id": int(CHAT),
        "text": message.render(),
        "link_preview_options": {"is_disabled": True},
    }  # no parse_mode: plain text
    shown = dict(line.split(": ", 1) for line in sent["text"].splitlines())
    assert shown == message.payload() and shown["value"] == "status 503 for [email]"
    out = capfd.readouterr()
    no_secret_in(token, out.out, out.err, *journal)


@pytest.mark.parametrize("case", list(ANSWERS))
def test_every_bad_answer_is_not_delivered_and_shows_no_token_or_url(
    tls_server: Server,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    case: str,
) -> None:
    reply, shown = ANSWERS[case]
    route(tls_server, monkeypatch)
    seen: list[tuple[str, bytes]] = []
    bot_api(tls_server, reply, seen)
    token = new_token()
    journal: list[str] = []
    start = time.monotonic()
    bot = Telegram("42", lambda: token, tls_server.client)
    assert deliver(Alert("disk", WHERE, "full"), bot, journal.append, bound=1) is False
    assert time.monotonic() - start < 5
    assert journal[-1] == f"disk: not sent off the host ({shown})"
    assert len(seen) == 1  # one request; a redirect is never followed
    out = capfd.readouterr()
    no_secret_in(token, out.out, out.err, *journal)


def test_each_socket_wait_is_bounded_too(
    tls_server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    route(tls_server, monkeypatch)
    bot_api(tls_server, None, [])  # silent
    monkeypatch.setattr(alert, "SEND_S", 0.3)
    bot = Telegram("42", new_token, tls_server.client)
    start = time.monotonic()
    with pytest.raises(OSError), alert.deadline(3):  # the socket timeout, not the deadline
        bot.send(Alert("disk", WHERE, "full"))
    assert time.monotonic() - start < 2


@pytest.mark.parametrize(
    ("setup", "shown"),
    [
        ("dns", "URLError gaierror"),
        ("certificate", "URLError SSLCertVerificationError"),
        ("refused", "URLError ConnectionRefusedError"),
    ],
)
def test_a_connection_failure_is_named_by_its_cause_and_sends_nothing(
    tls_server: Server,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    setup: str,
    shown: str,
) -> None:
    route(tls_server, monkeypatch, dns=setup != "dns")
    seen: list[tuple[str, bytes]] = []
    bot_api(tls_server, answer("200 OK", OK), seen)
    if setup == "refused":
        tls_server.close()
    token = new_token()
    context = ssl.create_default_context if setup == "certificate" else tls_server.client
    journal: list[str] = []
    bot = Telegram("42", lambda: token, context)  # the system CAs do not know the fake
    assert deliver(Alert("disk", WHERE, "full"), bot, journal.append, bound=2) is False
    assert journal[-1] == f"disk: not sent off the host ({shown})" and seen == []
    out = capfd.readouterr()
    no_secret_in(token, out.out, out.err, *journal)


def test_a_malformed_token_file_is_never_put_in_a_url(
    tls_server: Server, monkeypatch: pytest.MonkeyPatch, store: Store
) -> None:
    asked = route(tls_server, monkeypatch)
    seen: list[tuple[str, bytes]] = []
    bot_api(tls_server, answer("200 OK", OK), seen)
    store.put(b"123456789:" + b"A" * 34 + b"@evil.example\n")
    journal: list[str] = []
    bot = Telegram("42", store.read, tls_server.client)
    assert deliver(Alert("disk", WHERE, "full"), bot, journal.append) is False
    assert journal[-1] == "disk: not sent off the host (UnsafeCredential)"
    assert asked == [] and seen == []  # no connection at all
