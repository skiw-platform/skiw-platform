import os
import shutil
import socket
import ssl
import subprocess
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def docker_cli() -> str:
    """The docker CLI with a running daemon; skips locally without one, fails in CI."""
    path = shutil.which("docker")
    if path and subprocess.run([path, "info"], capture_output=True, check=False).returncode == 0:
        return path
    if os.environ.get("CI") == "true":
        pytest.fail("no Docker daemon in CI: the live host tests must run, not skip")
    pytest.skip("no Docker daemon locally; CI runs the live host tests")


@pytest.fixture(scope="session")
def tls_files(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A self-signed certificate for skiw.test and localhost (ci.env's SKIW_HOSTNAME) and for
    api.telegram.org (the alert tests route that name to the fake), made now by openssl; its key
    never leaves this temporary directory. Skips locally without openssl, fails in CI."""
    openssl = shutil.which("openssl")
    if openssl is None:
        if os.environ.get("CI") == "true":
            pytest.fail("no openssl in CI: the TLS fakes must run, not skip")
        pytest.skip("no openssl locally; CI runs the TLS fake tests")
    directory = tmp_path_factory.mktemp("tls")
    argv = [openssl, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1"]
    argv += ["-nodes", "-keyout", str(directory / "key.pem"), "-out", str(directory / "cert.pem")]
    argv += ["-days", "30", "-subj", "/CN=skiw.test"]
    argv += ["-addext", "subjectAltName=DNS:skiw.test,DNS:localhost,DNS:api.telegram.org"]
    subprocess.run(argv, capture_output=True, check=True)
    return directory


class TlsServer:
    """A TLS listener on 127.0.0.1 that hands each connection to `handler` in its own thread; it
    stands in for Caddy (skiw-health's /readyz request) or the Telegram Bot API. Never a real
    service."""

    def __init__(self, files: Path) -> None:
        self.files = files
        self.server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server.load_cert_chain(files / "cert.pem", files / "key.pem")
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port: int = self.listener.getsockname()[1]
        self.handler: Callable[[ssl.SSLSocket], None] = lambda tls: None
        self.stop = threading.Event()
        threading.Thread(target=self.accept, daemon=True).start()

    def client(self) -> ssl.SSLContext:
        """What the code under test gets: verification on, this certificate the only trust."""
        return ssl.create_default_context(cafile=self.files / "cert.pem")

    def accept(self) -> None:
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:  # closed at teardown
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn: socket.socket) -> None:
        conn.settimeout(10)
        try:
            with self.server.wrap_socket(conn, server_side=True) as tls:
                self.handler(tls)
        except OSError:  # the client refused the certificate or hung up
            pass

    def close(self) -> None:
        self.stop.set()
        try:  # Linux keeps a closed listener alive while accept() waits; shutdown wakes it
            self.listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.listener.close()


@pytest.fixture
def tls_server(tls_files: Path) -> Iterator[TlsServer]:
    server = TlsServer(tls_files)
    yield server
    server.close()
