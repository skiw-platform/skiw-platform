"""The files volume (spec §8.4 H5, D14). The only module that reads or writes it (UNI-04).

Layout under `settings.FILES_ROOT` (one filesystem, so a rename is atomic): `tmp/<uuid>.part`,
`tmp/<document>.<attempt>.part`, `quarantine/<agency_id>/<document>` and
`clean/<agency_id>/<document>`.
Every directory component is opened with O_NOFOLLOW and files are created with O_EXCL; each file is
fsynced before its rename and the target directory after it, before success is reported. An agency
or document id becomes a path component only in its canonical uuid form (`_part`).

This module touches no database (TEN-10). Row access is the caller's `FileRows`, bound to the
caller's open transaction: from M4/M16 the scan job's or request's `with_agency()` transaction
(H5); in M1 a test-only probe table (plan G14).
"""

import contextlib
import hashlib
import logging
import os
import stat
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO, Protocol

from django.conf import settings

from .clamd import Verdict

logger = logging.getLogger(__name__)

CHUNK = 65536
# FILE-01 allow-list, checked on the first bytes (spec H5: PDF, JPEG, PNG; never SVG or HTML).
MAGIC = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)
HEAD = max(len(prefix) for prefix, _ in MAGIC)
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
NEW_FILE = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
# Crash points for the H5 harness. Armed only when settings.FILES_FAILPOINTS is True, which no
# settings module sets and no environment variable reaches (test_failpoints_cannot_be_enabled).
FAILPOINTS = frozenset(
    {
        "upload_write",
        "after_quarantine_rename",
        "output_write",
        "after_publish_rename",
        "before_quarantine_delete",
    }
)
_armed: set[str] = set()


class StorageError(RuntimeError):
    pass


class RefusedUpload(StorageError):
    """FILE-01 (type) or FILE-02 (size) refusal at the boundary."""


class FileIntegrityError(StorageError):
    """A clean file does not match its row; the row is now `integrity_failed`."""


class SimulatedCrash(BaseException):
    """Raised by an armed failpoint. BaseException, so no `except Exception` cleanup runs."""


class Status(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"
    INTEGRITY_FAILED = "integrity_failed"


class Outcome(StrEnum):
    PUBLISHED = "published"
    ALREADY_CLEAN = "already_clean"
    INFECTED = "infected"
    FAILED = "failed"
    INTEGRITY_FAILED = "integrity_failed"
    MISSING = "missing"


@dataclass(frozen=True)
class Upload:
    id: uuid.UUID
    mime: str
    size: int
    sha256: str


@dataclass(frozen=True)
class FileRow:
    id: uuid.UUID
    agency_id: uuid.UUID
    av_status: Status
    source_size: int
    source_sha256: str
    clean_size: int | None = None
    clean_sha256: str | None = None
    object_key: str | None = None


@dataclass(frozen=True)
class CleanFile:
    object_key: str
    clean_size: int
    clean_sha256: str
    scanner_db_version: str


class FileRows(Protocol):
    """The caller's row access, inside the caller's open transaction."""

    def lock(self, document_id: uuid.UUID) -> None:
        """`pg_advisory_xact_lock` on the document id; held until the transaction ends."""

    def load(self, document_id: uuid.UUID) -> FileRow | None: ...
    def status(self, document_id: uuid.UUID) -> Status | None: ...
    def set_status(self, document_id: uuid.UUID, status: Status) -> None: ...
    def set_clean(self, document_id: uuid.UUID, clean: CleanFile) -> None: ...


class Scanner(Protocol):
    def scan(self, chunks: Iterator[bytes]) -> Verdict: ...
    def version(self) -> str: ...


class Reader(Protocol):
    def read(self, size: int, /) -> bytes: ...


def write_quarantine(agency_id: uuid.UUID, stream: Reader, max_bytes: int) -> Upload:
    """Stream an upload to `quarantine/<agency_id>/<new uuid>`. The caller then inserts the row
    (`pending`, size, SHA-256) and enqueues the scan in one transaction (H5, EVT-01)."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    agency = _part(agency_id)
    doc_id, part = uuid.uuid4(), f"{uuid.uuid4()}.part"
    head = b""
    while len(head) < HEAD and (piece := stream.read(HEAD - len(head))):
        head += piece
    mime = next((m for prefix, m in MAGIC if head.startswith(prefix)), None)
    if mime is None:
        raise RefusedUpload("file type is not allowed")
    digest, size = hashlib.sha256(), 0
    with _dir("tmp") as tmp:
        fd = os.open(part, NEW_FILE, 0o600, dir_fd=tmp)
        try:
            with os.fdopen(fd, "wb") as out:
                chunk = head
                while chunk:
                    size += len(chunk)
                    if size > max_bytes:
                        raise RefusedUpload("file is larger than the upload limit")
                    digest.update(chunk)
                    out.write(chunk)
                    _failpoint("upload_write")
                    chunk = stream.read(CHUNK)
                out.flush()
                os.fsync(out.fileno())
            with _dir("quarantine", agency) as qdir:
                os.rename(part, str(doc_id), src_dir_fd=tmp, dst_dir_fd=qdir)
                os.fsync(qdir)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(part, dir_fd=tmp)
            raise
    _failpoint("after_quarantine_rename")
    return Upload(doc_id, mime, size, digest.hexdigest())


def publish_clean(
    rows: FileRows, document_id: uuid.UUID, scanner: Scanner, max_bytes: int
) -> Outcome:
    """One scan-and-publish attempt (H5 steps 1-6) inside the caller's transaction. Never raises
    for a verdict, so the caller commits the status it set; a ScanError or StorageError leaves
    the row as committed before (retry with backoff, EVT-05). After the caller commits a
    PUBLISHED outcome it calls `discard_quarantine`."""
    rows.lock(document_id)
    row = rows.load(document_id)
    if row is None:
        return Outcome.MISSING
    if row.av_status is Status.CLEAN:
        handle = _verified(row)
        if handle is None:
            return _mark(rows, row, Status.INTEGRITY_FAILED, Outcome.INTEGRITY_FAILED)
        handle.close()
        return Outcome.ALREADY_CLEAN
    if row.av_status is not Status.PENDING:
        return Outcome(row.av_status.value)
    agency, name = _part(row.agency_id), _part(row.id)
    with _dir("quarantine", agency) as qdir:
        try:
            source = _open_file(name, qdir)
        except FileNotFoundError:
            return _mark(rows, row, Status.FAILED, Outcome.FAILED)
    with source:
        if _measure(source) != (row.source_size, row.source_sha256):  # step 2
            return _mark(rows, row, Status.FAILED, Outcome.FAILED)
        source.seek(0)
        verdict = scanner.scan(iter(lambda: source.read(CHUNK), b""))  # step 3
        if verdict.infected:
            return _mark(rows, row, Status.INFECTED, Outcome.INFECTED)
        if not verdict.clean:  # a clamd limit was hit: never published; a retry hits it again
            return _mark(rows, row, Status.FAILED, Outcome.FAILED)
        db_version = scanner.version()
        source.seek(0)
        part = f"{name}.{uuid.uuid4()}.part"
        with _dir("tmp") as tmp:
            size, sha256 = _copy_output(source, part, tmp, row, max_bytes)  # step 4
            with _dir("clean", agency) as cdir:  # step 5
                os.replace(part, name, src_dir_fd=tmp, dst_dir_fd=cdir)
                os.fsync(cdir)
    _failpoint("after_publish_rename")
    rows.set_clean(row.id, CleanFile(f"clean/{agency}/{name}", size, sha256, db_version))  # step 6
    return Outcome.PUBLISHED


def discard_quarantine(agency_id: uuid.UUID, document_id: uuid.UUID) -> None:
    """Delete the quarantine copy after the PUBLISHED commit; a leftover goes to the sweeper."""
    _failpoint("before_quarantine_delete")
    name = _part(document_id)
    with _dir("quarantine", _part(agency_id)) as qdir:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name, dir_fd=qdir)
        os.fsync(qdir)


def open_verified(rows: FileRows, row: FileRow) -> BinaryIO:
    """The clean file of a committed `clean` row, checked against the row's size and SHA-256
    before the first byte is returned (FILE-04, H5). The row's `object_key` must be exactly
    `clean/<its agency>/<its id>`.

    On a mismatch, a missing file or a malformed key it calls `rows.set_status(integrity_failed)`
    and THEN raises FileIntegrityError. The mark is only durable if the caller commits it: an
    M16 download path that runs this inside `transaction.atomic()` (or `with_agency()`) and lets
    the exception propagate rolls the mark back. The caller must catch FileIntegrityError and
    commit the mark (as the harness's `download()` does) before it answers with an error."""
    if row.av_status is not Status.CLEAN:
        raise StorageError("only a clean document can be opened")
    handle = _verified(row)
    if handle is None:
        _mark(rows, row, Status.INTEGRITY_FAILED, Outcome.INTEGRITY_FAILED)
        raise FileIntegrityError("the stored file does not match its row")
    return handle


def sweep_tmp(now: float | None = None) -> int:
    """Remove `tmp/*.part` files older than FILES_SWEEP_AGE_S. Never on a served path."""
    with _dir("tmp") as tmp:
        return _sweep(tmp, now, lambda name: name.endswith(".part"))


def sweep_quarantine(rows: FileRows, agency_id: uuid.UUID, now: float | None = None) -> int:
    """Remove this agency's quarantine files older than FILES_SWEEP_AGE_S whose row is absent
    (never committed) or `clean` (published; the post-commit delete did not run). Pending,
    infected and failed sources stay (retention is M16)."""

    def leftover(name: str) -> bool:
        try:
            document_id = uuid.UUID(name)
        except ValueError:
            return False
        return str(document_id) == name and rows.status(document_id) in (None, Status.CLEAN)

    with _dir("quarantine", _part(agency_id)) as qdir:
        return _sweep(qdir, now, leftover)


@contextlib.contextmanager
def arm(name: str) -> Iterator[None]:
    """Arm one failpoint for the next time it is reached (test settings only)."""
    if getattr(settings, "FILES_FAILPOINTS", False) is not True or name not in FAILPOINTS:
        raise StorageError("failpoints are not enabled by these settings")
    _armed.add(name)
    try:
        yield
    finally:
        _armed.discard(name)


def _failpoint(name: str) -> None:
    if name in _armed and getattr(settings, "FILES_FAILPOINTS", False) is True:
        _armed.discard(name)
        raise SimulatedCrash(name)


def _mark(rows: FileRows, row: FileRow, status: Status, outcome: Outcome) -> Outcome:
    rows.set_status(row.id, status)
    logger.error("file store alert: document %s set to %s", row.id, status.value)
    return outcome


def _copy_output(
    source: BinaryIO, part: str, tmp: int, row: FileRow, max_bytes: int
) -> tuple[int, str]:
    """H5 step 4. PDFs and images are copied in M1 (image re-encoding needs a decoder: M16).
    The bytes read must still be the verified source; the output is re-validated (FILE-01/02)."""
    fd = os.open(part, NEW_FILE, 0o600, dir_fd=tmp)
    try:
        with os.fdopen(fd, "wb") as out:
            read_digest, size = hashlib.sha256(), 0
            while chunk := source.read(CHUNK):
                read_digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
                _failpoint("output_write")
            out.flush()
            os.fsync(out.fileno())
        with _open_file(part, tmp) as output:
            head = output.read(HEAD)
            output.seek(0)
            out_size, out_sha256 = _measure(output)
        if (size, read_digest.hexdigest()) != (row.source_size, row.source_sha256):
            raise StorageError("the quarantine source changed during the attempt")
        if not any(head.startswith(prefix) for prefix, _ in MAGIC) or out_size > max_bytes:
            raise StorageError("the output failed validation")
        return out_size, out_sha256
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(part, dir_fd=tmp)
        raise


def _verified(row: FileRow) -> BinaryIO | None:
    """An open handle at offset 0 if the row's clean file has its size and SHA-256, else None.
    The key must be `clean/<row agency>/<row id>`: another agency's or document's file, or a key
    that is not two canonical uuids, is a failed verification."""
    try:
        agency, name = _part(row.agency_id), _part(row.id)
    except StorageError:
        return None
    if row.object_key != f"clean/{agency}/{name}":
        return None
    try:
        with _dir("clean", agency, create=False) as cdir:
            handle = _open_file(name, cdir)
    except (OSError, StorageError):  # missing, a symlink (ELOOP) or not a regular file
        return None
    if os.fstat(handle.fileno()).st_size != row.clean_size or _measure(handle) != (
        row.clean_size,
        row.clean_sha256,
    ):
        handle.close()
        return None
    handle.seek(0)
    return handle


def _part(value: uuid.UUID) -> str:
    """The canonical text of an id, the only form used as a path component. The type says uuid,
    but a caller's string (for example `../other`) must never reach a directory name."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError as exc:
        raise StorageError("an agency or document id is not a uuid") from exc


def _measure(handle: BinaryIO) -> tuple[int, str]:
    digest, size = hashlib.sha256(), 0
    while chunk := handle.read(CHUNK):
        digest.update(chunk)
        size += len(chunk)
    return size, digest.hexdigest()


def _open_file(name: str, dir_fd: int) -> BinaryIO:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise StorageError("not a regular file")
    return os.fdopen(fd, "rb")


def _sweep(dir_fd: int, now: float | None, wanted: Callable[[str], bool]) -> int:
    cutoff = (time.time() if now is None else now) - settings.FILES_SWEEP_AGE_S
    removed = 0
    for entry in os.scandir(dir_fd):
        info = entry.stat(follow_symlinks=False)
        if stat.S_ISREG(info.st_mode) and info.st_mtime < cutoff and wanted(entry.name):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(entry.name, dir_fd=dir_fd)
                removed += 1
    if removed:
        os.fsync(dir_fd)
    return removed


@contextlib.contextmanager
def _dir(*parts: str, create: bool = True) -> Iterator[int]:
    """An fd for FILES_ROOT/<parts>, each component opened O_NOFOLLOW; a missing component is
    created 0700 (and its parent fsynced) when `create` is set."""
    root = settings.FILES_ROOT
    if not root or not os.path.isabs(root):
        raise StorageError("FILES_ROOT is not configured")
    fd = os.open(root, DIR_FLAGS)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                else:
                    os.fsync(fd)
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)
