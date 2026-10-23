"""documents.storage without a database (spec §8.4 H5; FILE-01, FILE-02; plan §3 M1i)."""

import hashlib
import importlib
import io
import os
import stat
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from django.conf import settings
from pytest_django import Settings

from documents import storage
from documents.clamd import ScanError
from documents.storage import FileRow, Outcome, RefusedUpload, Status, StorageError

from .conftest import PDF, FakeScanner, MemoryRows, files_under

APP = Path(__file__).resolve().parents[2]


class Endless:
    """A client that never stops sending: the limit must stop the read, not the stream end."""

    def __init__(self) -> None:
        self.sent = 0

    def read(self, size: int, /) -> bytes:
        self.sent += size
        return (b"%PDF-" + b"x" * size)[:size]


@pytest.mark.parametrize(
    "body",
    [
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>",
        b'<?xml version="1.0"?><svg/>',
        b"<!DOCTYPE html><html><body>%PDF-1.7</body></html>",
        b"MZ\x90\x00 an executable",
        b"PK\x03\x04 a zip",
        b"%PD",
        b"",
    ],
    ids=["svg", "xml-svg", "html", "exe", "zip", "short", "empty"],
)
def test_wrong_magic_svg_and_html_are_refused(files_root: Path, body: bytes) -> None:
    with pytest.raises(RefusedUpload, match="type"):
        storage.write_quarantine(uuid.uuid4(), io.BytesIO(body), 1024)
    assert files_under(files_root) == []


@pytest.mark.parametrize("head", [b"%PDF-1.4\n", b"\x89PNG\r\n\x1a\n\x00", b"\xff\xd8\xff\xe0JFIF"])
def test_allowed_types_reach_quarantine(files_root: Path, head: bytes) -> None:
    agency, body = uuid.uuid4(), head + b"body"
    upload = storage.write_quarantine(agency, io.BytesIO(body), len(body))
    assert (upload.size, upload.sha256) == (len(body), hashlib.sha256(body).hexdigest())
    assert files_under(files_root) == [f"quarantine/{agency}/{upload.id}"]
    mode = (files_root / "quarantine" / str(agency) / str(upload.id)).stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_over_limit_stream_is_refused_while_streaming(files_root: Path) -> None:
    client = Endless()
    with pytest.raises(RefusedUpload, match="limit"):
        storage.write_quarantine(uuid.uuid4(), client, 300_000)
    assert client.sent <= 300_000 + storage.CHUNK + storage.HEAD
    assert files_under(files_root) == []


def test_exactly_the_limit_is_accepted(files_root: Path) -> None:
    storage.write_quarantine(uuid.uuid4(), io.BytesIO(PDF), len(PDF))
    with pytest.raises(RefusedUpload):
        storage.write_quarantine(uuid.uuid4(), io.BytesIO(PDF), len(PDF) - 1)


def test_files_root_must_be_configured(files_root: Path, settings: Settings) -> None:
    for value in ("", "relative/files"):
        settings.FILES_ROOT = value
        with pytest.raises(StorageError, match="FILES_ROOT"):
            storage.write_quarantine(uuid.uuid4(), io.BytesIO(PDF), len(PDF))


def test_a_symlinked_directory_is_not_followed(files_root: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (files_root / "quarantine").symlink_to(elsewhere)
    with pytest.raises(OSError):  # ELOOP from O_NOFOLLOW
        storage.write_quarantine(uuid.uuid4(), io.BytesIO(PDF), len(PDF))
    assert list(elsewhere.iterdir()) == []


def test_each_file_is_fsynced_before_its_rename_and_the_directory_after(
    files_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_fsync, real_rename, real_replace = os.fsync, os.rename, os.replace

    def fsync(fd: int) -> None:
        events.append("fsync-dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync-file")
        real_fsync(fd)

    def renamer(real: Callable[..., None]) -> Callable[..., None]:
        def rename(*args: object, **kwargs: object) -> None:
            events.append("rename")
            real(*args, **kwargs)

        return rename

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "rename", renamer(real_rename))
    monkeypatch.setattr(os, "replace", renamer(real_replace))

    def assert_durable() -> None:
        at = events.index("rename")
        assert "fsync-file" in events[:at], events
        assert events[at + 1 :] == ["fsync-dir"], events
        events.clear()

    agency = uuid.uuid4()
    upload = storage.write_quarantine(agency, io.BytesIO(PDF), len(PDF))
    assert_durable()
    rows = MemoryRows()
    rows.add(FileRow(upload.id, agency, Status.PENDING, upload.size, upload.sha256))
    assert storage.publish_clean(rows, upload.id, FakeScanner(), len(PDF)) is Outcome.PUBLISHED
    assert_durable()


def test_infected_and_scanner_errors_never_publish(files_root: Path) -> None:
    agency, rows = uuid.uuid4(), MemoryRows()
    for body, scanner, expected in [
        (PDF + b"FAKE-TEST-SIGNATURE", FakeScanner(), Outcome.INFECTED),
        (PDF, FakeScanner(limit=10), None),
    ]:
        upload = storage.write_quarantine(agency, io.BytesIO(body), len(body))
        rows.add(FileRow(upload.id, agency, Status.PENDING, upload.size, upload.sha256))
        if expected is None:
            with pytest.raises(ScanError):
                storage.publish_clean(rows, upload.id, scanner, len(body))
            assert rows.status(upload.id) is Status.PENDING
        else:
            assert storage.publish_clean(rows, upload.id, scanner, len(body)) is expected
            assert rows.status(upload.id) is Status.INFECTED
    assert not (files_root / "clean").exists() or files_under(files_root / "clean") == []


def test_a_changed_quarantine_source_fails_the_row(files_root: Path) -> None:
    agency, rows = uuid.uuid4(), MemoryRows()
    upload = storage.write_quarantine(agency, io.BytesIO(PDF), len(PDF))
    rows.add(FileRow(upload.id, agency, Status.PENDING, upload.size, "0" * 64))
    assert storage.publish_clean(rows, upload.id, FakeScanner(), len(PDF)) is Outcome.FAILED
    assert rows.status(upload.id) is Status.FAILED
    assert not (files_root / "clean").exists()


def test_failpoints_cannot_be_enabled_by_production_settings() -> None:
    """Only a test can set FILES_FAILPOINTS: no settings module defines it, no environment
    variable is read for it, and no module other than storage.py names it."""
    for module in ("config.settings", "config.settings_migration_lint"):
        assert not hasattr(importlib.import_module(module), "FILES_FAILPOINTS")
    assert not hasattr(settings, "FILES_FAILPOINTS")
    with pytest.raises(StorageError, match="not enabled"), storage.arm("upload_write"):
        pass
    storage._armed.add("upload_write")  # even if armed, the hook is inert without the setting
    try:
        storage._failpoint("upload_write")
    finally:
        storage._armed.clear()
    mentions = [
        path.relative_to(APP)
        for path in APP.rglob("*.py")
        if "FILES_FAILPOINTS" in path.read_text() and "tests" not in path.parts
    ]
    assert mentions == [Path("documents/storage.py")]
