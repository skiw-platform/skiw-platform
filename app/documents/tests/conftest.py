import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_django import Settings

from documents.clamd import ScanError, Verdict
from documents.storage import CleanFile, FileRow, Status

PDF = b"%PDF-1.7\n" + bytes(range(256)) * 800 + b"\n%%EOF\n"  # ~200 KiB: several write chunks
INFECTED_MARKER = b"FAKE-TEST-SIGNATURE"


@pytest.fixture
def files_root(tmp_path: Path, settings: Settings) -> Path:
    """A fresh files volume per test; failpoints may be armed (test settings only)."""
    root = tmp_path / "files"
    root.mkdir(mode=0o700)
    settings.FILES_ROOT = str(root)
    settings.FILES_FAILPOINTS = True
    return root


class FakeScanner:
    """Models clamd's rules the storage code relies on: a size limit that is an error (never a
    verdict), a FOUND verdict for a signature, and the VERSION string."""

    def __init__(self, limit: int = 100 * 1024 * 1024) -> None:
        self.limit, self.calls = limit, 0

    def scan(self, chunks: Iterator[bytes]) -> Verdict:
        self.calls += 1
        data = b"".join(chunks)
        if len(data) > self.limit:
            raise ScanError("INSTREAM size limit exceeded")
        if INFECTED_MARKER in data:
            return Verdict(infected=True, signature="Fake-Test-Signature")
        return Verdict(infected=False)

    def version(self) -> str:
        return "ClamAV 1.5.4/0/fake"


class MemoryRows:
    """FileRows without a database, for tests that do not need the probe table."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, FileRow] = {}

    def add(self, row: FileRow) -> None:
        self.rows[row.id] = row

    def lock(self, document_id: uuid.UUID) -> None:
        pass

    def load(self, document_id: uuid.UUID) -> FileRow | None:
        return self.rows.get(document_id)

    def status(self, document_id: uuid.UUID) -> Status | None:
        row = self.rows.get(document_id)
        return None if row is None else row.av_status

    def set_status(self, document_id: uuid.UUID, status: Status) -> None:
        row = self.rows[document_id]
        self.rows[document_id] = FileRow(**{**row.__dict__, "av_status": status})

    def set_clean(self, document_id: uuid.UUID, clean: CleanFile) -> None:
        row = self.rows[document_id]
        self.rows[document_id] = FileRow(
            **{
                **row.__dict__,
                "av_status": Status.CLEAN,
                "clean_size": clean.clean_size,
                "clean_sha256": clean.clean_sha256,
                "object_key": clean.object_key,
            }
        )


def files_under(root: Path) -> list[str]:
    """Every regular file under the volume, as relative paths."""
    return sorted(
        str(Path(base, name).relative_to(root))
        for base, _, names in os.walk(root)
        for name in names
    )
