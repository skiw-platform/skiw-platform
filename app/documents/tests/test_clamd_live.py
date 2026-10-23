"""EICAR through a real clamd INSTREAM (FILE-01, spec §8.4 H5, T14; plan §3 M1i).

Runs under `make host-test-live` (CI job `host`): one container from the clamav image pinned in
infra/host/compose.yml, with that file's hardening and its `CLAMD_CONF_*` settings (so
`AlertExceedsMax yes`), `CLAMAV_NO_FRESHCLAMD=true` (the image ships its signatures, so no
download), and one limit pushed low for the test (`MaxFileSize` 1 MiB, so a 2 MiB stream crosses
it), clamd published on a loopback port chosen by Docker, removed afterwards. Skips locally
without a Docker daemon; fails when CI=true. The EICAR test string is joined from two halves at
run time, so no file in the repository holds it whole.
"""

import hashlib
import io
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from documents import storage
from documents.clamd import ClamdScanner
from documents.storage import FileRow, Outcome, Status

from .conftest import PDF, MemoryRows, files_under

pytestmark = pytest.mark.host_live
COMPOSE = Path(__file__).resolve().parents[3] / "infra" / "host" / "compose.yml"
IMAGE = re.search(r"image: (clamav/clamav:\S+@sha256:[0-9a-f]{64})", COMPOSE.read_text())
CONF = dict(re.findall(r'^ +(CLAMD_CONF_\w+): "([^"]*)"$', COMPOSE.read_text(), re.MULTILINE))
# Test only: MaxFileSize 1M, so this 2 MiB PDF-like stream hits a limit.
OVER_LIMIT = b"%PDF-1.7\n" + bytes(range(256)) * (2 * 4096)
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()
STARTUP_S = 300


def docker() -> str:
    path = shutil.which("docker")
    if path and subprocess.run([path, "info"], capture_output=True, check=False).returncode == 0:
        return path
    if os.environ.get("CI") == "true":
        pytest.fail("no Docker daemon in CI: the clamd test must run, not skip")
    pytest.skip("no Docker daemon locally; CI runs the clamd test")


def pong(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
            sock.sendall(b"zPING\0")
            return sock.recv(16) == b"PONG\0"
    except OSError:
        return False


@pytest.fixture(scope="module")
def clamd() -> Iterator[ClamdScanner]:
    assert IMAGE, "the clamav image is not pinned by digest in compose.yml"
    assert CONF.get("CLAMD_CONF_AlertExceedsMax") == "yes", CONF
    cli, name = docker(), f"skiw-clamd-{secrets.token_hex(4)}"
    # The pinned index has an amd64 image only, like the hosts and CI runners (emulated on arm64).
    platform = ["--platform", "linux/amd64"]
    pull = [cli, "pull", "-q", *platform, IMAGE[1]]
    subprocess.run(pull, check=True, capture_output=True, timeout=600)
    run = [cli, "run", "-d", "--rm", *platform, "--name", name, "-p", "127.0.0.1::3310"]
    run += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges:true"]
    for cap in ("CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"):
        run += ["--cap-add", cap]
    run += ["--memory", "1536m", "--pids-limit", "256", "-e", "CLAMAV_NO_FRESHCLAMD=true"]
    for key, value in {**CONF, "CLAMD_CONF_MaxFileSize": "1M"}.items():
        run += ["-e", f"{key}={value}"]
    subprocess.run([*run, IMAGE[1]], check=True, capture_output=True, timeout=60)
    try:
        published = subprocess.run(
            [cli, "port", name, "3310/tcp"], check=True, capture_output=True, text=True
        ).stdout.splitlines()[0]
        port = int(published.rsplit(":", 1)[1])
        deadline = time.monotonic() + STARTUP_S
        while not pong(port):
            if time.monotonic() > deadline:
                pytest.fail(f"clamd did not answer PING within {STARTUP_S} s")
            time.sleep(2)
        yield ClamdScanner("127.0.0.1", port, timeout_s=60)
    finally:
        subprocess.run([cli, "rm", "-f", name], capture_output=True, check=False)


def test_eicar_is_found_by_clamd_instream(clamd: ClamdScanner) -> None:
    verdict = clamd.scan(iter([EICAR[:30], EICAR[30:]]))
    assert verdict.infected and verdict.signature and "Eicar" in verdict.signature


def test_a_clean_pdf_passes_and_the_version_is_recorded(clamd: ClamdScanner) -> None:
    assert not clamd.scan(iter([PDF])).infected
    assert clamd.version().startswith("ClamAV 1.5.4/")


def test_publish_marks_an_eicar_source_infected_and_publishes_nothing(
    clamd: ClamdScanner, files_root: Path
) -> None:
    """EICAR has no allowed magic, so the upload boundary refuses it first (FILE-01); the scan
    is proven on a quarantine source placed directly, as a file that got past the boundary."""
    agency, doc, rows = uuid.uuid4(), uuid.uuid4(), MemoryRows()
    with pytest.raises(storage.RefusedUpload):
        storage.write_quarantine(agency, io.BytesIO(EICAR), 1024)
    (files_root / "quarantine" / str(agency)).mkdir(parents=True)
    (files_root / "quarantine" / str(agency) / str(doc)).write_bytes(EICAR)
    good = storage.write_quarantine(agency, io.BytesIO(PDF), len(PDF))
    rows.add(FileRow(doc, agency, Status.PENDING, len(EICAR), hashlib.sha256(EICAR).hexdigest()))
    rows.add(FileRow(good.id, agency, Status.PENDING, good.size, good.sha256))
    assert storage.publish_clean(rows, doc, clamd, len(PDF)) is Outcome.INFECTED
    assert storage.publish_clean(rows, good.id, clamd, len(PDF)) is Outcome.PUBLISHED
    assert rows.status(doc) is Status.INFECTED
    assert f"clean/{agency}/{doc}" not in files_under(files_root)
    assert f"clean/{agency}/{good.id}" in files_under(files_root)


def nested_zip(depth: int) -> bytes:
    data = b"nested " * 64
    for level in range(depth):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"level{level}.bin", data)
        data = buf.getvalue()
    return data


@pytest.mark.parametrize(
    "body",
    [OVER_LIMIT, nested_zip(25)],
    ids=["max-file-size", "default-max-recursion"],
)
def test_a_stream_past_a_scan_limit_is_never_clean(clamd: ClamdScanner, body: bytes) -> None:
    """With `AlertExceedsMax yes` clamd names the limit; without it, it answers `stream: OK`
    (probed 2026-10-23). MaxRecursion keeps the image default here."""
    verdict = clamd.scan(iter([body]))
    assert not verdict.clean and verdict.incomplete and not verdict.infected
    assert verdict.signature and verdict.signature.startswith("Heuristics.Limits.Exceeded.")


def test_publish_fails_a_file_clamd_did_not_fully_scan(
    clamd: ClamdScanner, files_root: Path
) -> None:
    agency, rows = uuid.uuid4(), MemoryRows()
    body = OVER_LIMIT
    upload = storage.write_quarantine(agency, io.BytesIO(body), len(body))
    rows.add(FileRow(upload.id, agency, Status.PENDING, upload.size, upload.sha256))
    assert storage.publish_clean(rows, upload.id, clamd, len(body)) is Outcome.FAILED
    assert rows.status(upload.id) is Status.FAILED
    assert files_under(files_root) == [f"quarantine/{agency}/{upload.id}"]
