"""clamd INSTREAM client (spec §8.4 H5 step 3, T14). Standard library only; fails closed.

Protocol (docs.clamav.net ClamdProtocol, checked against clamd 1.5.4 on 2026-10-23): `zINSTREAM\\0`,
then chunks of a 4-byte unsigned length in network byte order followed by that many bytes, then a
zero-length chunk. The reply is one NUL-terminated record: `stream: OK`, `stream: <name> FOUND`, or
an error such as `INSTREAM size limit exceeded. ERROR`. Anything other than the first two, a
missing NUL, a closed socket or a passed deadline is a ScanError: never treated as clean.
"""

import re
import socket
import struct
import time
from collections.abc import Iterable
from dataclasses import dataclass

MAX_REPLY = 4096
FOUND = re.compile(r"stream: ([\x21-\x7e]{1,200}) FOUND")
VERSION = re.compile(r"ClamAV [\x20-\x7e]{1,200}")


class ScanError(RuntimeError):
    """The scanner gave no usable verdict; the caller retries later (EVT-05)."""


@dataclass(frozen=True)
class Verdict:
    infected: bool
    signature: str | None = None


class ClamdScanner:
    def __init__(self, host: str, port: int, *, timeout_s: float, chunk_bytes: int = 65536) -> None:
        if timeout_s <= 0 or not 0 < chunk_bytes <= 1 << 20:
            raise ValueError("timeout_s must be positive and chunk_bytes in (0, 1 MiB]")
        self.address, self.timeout_s, self.chunk_bytes = (host, port), timeout_s, chunk_bytes

    def scan(self, chunks: Iterable[bytes]) -> Verdict:
        """Stream `chunks` with INSTREAM; the whole exchange is bounded by `timeout_s`."""
        deadline = time.monotonic() + self.timeout_s
        with self._connect(deadline) as sock:
            try:
                self._send(sock, deadline, b"zINSTREAM\0")
                for chunk in chunks:
                    for start in range(0, len(chunk), self.chunk_bytes):
                        piece = chunk[start : start + self.chunk_bytes]
                        self._send(sock, deadline, struct.pack("!I", len(piece)) + piece)
                self._send(sock, deadline, struct.pack("!I", 0))
            except OSError:
                # clamd closes the socket after a size-limit error; its reply (if any) is read
                # below only to fail closed the same way.
                pass
            reply = self._reply(sock, deadline)
        if reply == "stream: OK":
            return Verdict(infected=False)
        if match := FOUND.fullmatch(reply):
            return Verdict(infected=True, signature=match[1])
        raise ScanError("clamd gave no verdict")

    def version(self) -> str:
        """The program and signature database version, stored as `scanner_db_version`."""
        deadline = time.monotonic() + self.timeout_s
        with self._connect(deadline) as sock:
            self._send(sock, deadline, b"zVERSION\0")
            reply = self._reply(sock, deadline)
        if not VERSION.fullmatch(reply):
            raise ScanError("clamd VERSION reply is not recognised")
        return reply

    def _connect(self, deadline: float) -> socket.socket:
        try:
            return socket.create_connection(self.address, timeout=_left(deadline))
        except OSError as exc:
            raise ScanError("clamd is unreachable") from exc

    @staticmethod
    def _send(sock: socket.socket, deadline: float, data: bytes) -> None:
        sock.settimeout(_left(deadline))
        sock.sendall(data)

    @staticmethod
    def _reply(sock: socket.socket, deadline: float) -> str:
        data = b""
        try:
            while b"\0" not in data and len(data) <= MAX_REPLY:
                sock.settimeout(_left(deadline))
                piece = sock.recv(MAX_REPLY)
                if not piece:
                    break
                data += piece
        except OSError as exc:
            raise ScanError("clamd reply timed out or failed") from exc
        record, nul, _ = data.partition(b"\0")
        if not nul or len(record) > MAX_REPLY:
            raise ScanError("clamd reply is missing or unterminated")
        try:
            return record.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ScanError("clamd reply is not ASCII") from exc


def _left(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise ScanError("clamd deadline passed")
    return left
