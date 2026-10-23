"""The clamd INSTREAM client against a fake clamd that follows the real framing and replies
(clamd 1.5.4, probed 2026-10-23: `stream: OK`, `stream: <name> FOUND`, `INSTREAM size limit
exceeded. ERROR`, `UNKNOWN COMMAND`, and no reply to a stream cut short)."""

import io
import socket
import struct
import threading
from collections.abc import Iterator

import pytest

from documents.clamd import ClamdScanner, ScanError

MARKER = b"FAKE-TEST-SIGNATURE"


class FakeClamd:
    def __init__(self, mode: str, limit: int = 1 << 20) -> None:
        self.mode, self.limit, self.chunks = mode, limit, list[int]()
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.done = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        conn, _ = self.server.accept()
        with conn:
            conn.settimeout(5)
            reply = self._answer(conn.makefile("rb"))
            if reply is not None:
                conn.sendall(reply)
            if self.mode == "silent":
                self.done.wait(10)

    def _answer(self, stream: io.BufferedReader) -> bytes | None:
        read = stream.read
        command = b""
        while not command.endswith(b"\0"):
            byte = read(1)
            if not byte:
                return None
            command += byte
        if command == b"zVERSION\0":
            return {"garbage": b"no version\0"}.get(self.mode, b"ClamAV 1.5.4/28150/x\0")
        if command != b"zINSTREAM\0":
            return b"UNKNOWN COMMAND\0"
        data, total = b"", 0
        while True:
            header = read(4)
            if len(header) != 4:
                return None  # cut short: real clamd sends nothing
            (size,) = struct.unpack("!I", header)
            if self.mode == "hangup":
                return None  # closes mid-stream, unread data pending: the client sees a reset
            if size == 0:
                break
            self.chunks.append(size)
            total += size
            if total > self.limit:
                return b"INSTREAM size limit exceeded. ERROR\0"
            data += read(size)
        if self.mode == "silent":
            return None
        return {
            "garbage": b"stream: maybe\0",
            "unterminated": b"stream: OK",
            "error": b"stream: Can't allocate memory ERROR\0",
            "limits": b"stream: Heuristics.Limits.Exceeded.MaxRecursion FOUND\0",
        }.get(self.mode, b"stream: Fake-Sig FOUND\0" if MARKER in data else b"stream: OK\0")

    def close(self) -> None:
        self.done.set()
        self.server.close()


@pytest.fixture
def clamd(request: pytest.FixtureRequest) -> Iterator[FakeClamd]:
    fake = FakeClamd(*request.param)
    yield fake
    fake.close()


def scanner(fake: FakeClamd, timeout_s: float = 3) -> ClamdScanner:
    return ClamdScanner("127.0.0.1", fake.port, timeout_s=timeout_s, chunk_bytes=1000)


@pytest.mark.parametrize("clamd", [("ok",)], indirect=True)
def test_clean_stream_is_chunked_and_terminated(clamd: FakeClamd) -> None:
    verdict = scanner(clamd).scan(iter([b"%PDF-" + b"a" * 2500, b"b" * 10]))
    assert not verdict.infected and verdict.clean
    assert clamd.chunks == [1000, 1000, 505, 10]


@pytest.mark.parametrize("clamd", [("ok",)], indirect=True)
def test_found_is_infected(clamd: FakeClamd) -> None:
    verdict = scanner(clamd).scan(iter([b"%PDF-", MARKER]))
    assert verdict.infected and verdict.signature == "Fake-Sig"


@pytest.mark.parametrize(
    "clamd",
    [("garbage",), ("unterminated",), ("error",), ("ok", 100)],
    ids=["garbage", "unterminated", "error", "size-limit"],
    indirect=True,
)
def test_anything_but_a_verdict_fails_closed(clamd: FakeClamd) -> None:
    with pytest.raises(ScanError):
        scanner(clamd).scan(iter([b"%PDF-" + b"a" * 5000]))


@pytest.mark.parametrize("clamd", [("limits",)], indirect=True)
def test_a_scan_limit_hit_is_incomplete_never_clean(clamd: FakeClamd) -> None:
    """`AlertExceedsMax yes`: clamd stopped at a limit, so part of the file was not scanned."""
    verdict = scanner(clamd).scan(iter([b"%PDF-"]))
    assert not verdict.clean and verdict.incomplete and not verdict.infected
    assert verdict.signature == "Heuristics.Limits.Exceeded.MaxRecursion"


@pytest.mark.parametrize(
    "clamd", [("hangup",), ("ok", 100)], ids=["hangup", "size-limit-then-close"], indirect=True
)
def test_a_socket_closed_during_the_stream_fails_closed(clamd: FakeClamd) -> None:
    """clamd closes the socket mid-stream (after a size-limit error, or when it dies): the
    sends fail, and whatever is read after that is never a clean verdict."""
    big = (b"%PDF-" + b"a" * (1 << 20) for _ in range(16))
    with pytest.raises(ScanError):
        scanner(clamd).scan(big)


@pytest.mark.parametrize("clamd", [("silent",)], indirect=True)
def test_a_silent_clamd_is_bounded_by_the_deadline(clamd: FakeClamd) -> None:
    with pytest.raises(ScanError):
        scanner(clamd, timeout_s=0.5).scan(iter([b"%PDF-"]))


@pytest.mark.parametrize("clamd", [("ok",)], indirect=True)
def test_version(clamd: FakeClamd) -> None:
    assert scanner(clamd).version() == "ClamAV 1.5.4/28150/x"


@pytest.mark.parametrize("clamd", [("garbage",)], indirect=True)
def test_unrecognised_version_fails_closed(clamd: FakeClamd) -> None:
    with pytest.raises(ScanError):
        scanner(clamd).version()


def test_unreachable_clamd_fails_closed() -> None:
    with socket.create_server(("127.0.0.1", 0)) as probe:
        port = probe.getsockname()[1]
    with pytest.raises(ScanError):
        ClamdScanner("127.0.0.1", port, timeout_s=1).scan(iter([b"%PDF-"]))
