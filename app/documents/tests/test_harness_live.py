"""File-store harness (spec §8.4 H5 "Tests", plan §3 M1i, gate G14) on a test-only probe table.

`files_probe` is created for the session through MIGRATION_DATABASE_URL, granted to skiw_app only,
and dropped afterwards, as M0c did with `jobs_probe`. It has the `document` columns H5 uses and no
RLS: `with_agency()` and the `document` table arrive in M4/M16, where this harness runs again on
the real table. Every attempt runs as skiw_app on its own connection, like a worker attempt.
"""

import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from documents import storage
from documents.storage import (
    CleanFile,
    FileIntegrityError,
    FileRow,
    Outcome,
    SimulatedCrash,
    Status,
    Upload,
)

from .conftest import PDF, FakeScanner, files_under

pytestmark = pytest.mark.live
LIMIT = 1024 * 1024
LOCK_CLASS = 0x46494C45  # first key of the two-key advisory lock space, for documents
COLUMNS = (
    "id, agency_id, av_status, source_size, source_sha256, clean_size, clean_sha256, object_key"
)


@pytest.fixture(scope="session")
def files_probe() -> Iterator[None]:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE files_probe (id uuid PRIMARY KEY, agency_id uuid NOT NULL,"
            " av_status text NOT NULL CHECK (av_status IN"
            " ('pending', 'clean', 'infected', 'failed', 'integrity_failed')),"
            " source_size bigint NOT NULL, source_sha256 text NOT NULL, clean_size bigint,"
            " clean_sha256 text, scanner_db_version text, object_key text)"
        )
        conn.execute("REVOKE ALL ON files_probe FROM PUBLIC")
        conn.execute("GRANT SELECT, INSERT, UPDATE ON files_probe TO skiw_app")
        try:
            yield
        finally:
            conn.execute("DROP TABLE files_probe")


class ProbeRows:
    """FileRows on files_probe, bound to one connection's open transaction."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def lock(self, document_id: uuid.UUID) -> None:
        if self.conn.info.transaction_status is not TransactionStatus.INTRANS:
            raise RuntimeError("the advisory lock needs an open transaction")
        self.conn.execute(
            "SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (LOCK_CLASS, str(document_id))
        )

    def load(self, document_id: uuid.UUID) -> FileRow | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM files_probe WHERE id = %s",  # noqa: S608 - constant columns
            (document_id,),
        ).fetchone()
        return None if row is None else FileRow(row[0], row[1], Status(row[2]), *row[3:])

    def status(self, document_id: uuid.UUID) -> Status | None:
        row = self.load(document_id)
        return None if row is None else row.av_status

    def set_status(self, document_id: uuid.UUID, status: Status) -> None:
        self.conn.execute(
            "UPDATE files_probe SET av_status = %s WHERE id = %s", (status.value, document_id)
        )

    def set_clean(self, document_id: uuid.UUID, clean: CleanFile) -> None:
        self.conn.execute(
            "UPDATE files_probe SET av_status = 'clean', clean_size = %s, clean_sha256 = %s,"
            " scanner_db_version = %s, object_key = %s WHERE id = %s",
            (
                clean.clean_size,
                clean.clean_sha256,
                clean.scanner_db_version,
                clean.object_key,
                document_id,
            ),
        )


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def upload(agency: uuid.UUID, body: bytes = PDF) -> Upload:
    """The web side of H5: quarantine write, then the row in one transaction."""
    up = storage.write_quarantine(agency, _Stream(body), LIMIT)
    with connect() as conn:
        conn.execute(
            "INSERT INTO files_probe (id, agency_id, av_status, source_size, source_sha256)"
            " VALUES (%s, %s, 'pending', %s, %s)",
            (up.id, agency, up.size, up.sha256),
        )
    return up


def attempt(agency: uuid.UUID, doc: uuid.UUID, scanner: Any = None) -> Outcome:
    """One worker attempt: publish in a transaction, then the quarantine delete after commit."""
    with connect() as conn:
        with conn.transaction():
            outcome = storage.publish_clean(ProbeRows(conn), doc, scanner or FakeScanner(), LIMIT)
        if outcome is Outcome.PUBLISHED:
            storage.discard_quarantine(agency, doc)
    return outcome


def download(doc: uuid.UUID) -> bytes | None:
    """The download side of H5: only a committed clean row, verified before the first byte."""
    with connect() as conn, conn.transaction():
        rows = ProbeRows(conn)
        row = rows.load(doc)
        if row is None or row.av_status is not Status.CLEAN:
            return None
        try:
            with storage.open_verified(rows, row) as handle:
                return handle.read()
        except FileIntegrityError:
            return None


def status(doc: uuid.UUID) -> Status | None:
    with connect() as conn:
        return ProbeRows(conn).status(doc)


def sweep(agency: uuid.UUID, later: bool = True) -> int:
    now = time.time() + 3601 if later else None
    with connect() as conn:
        return storage.sweep_tmp(now) + storage.sweep_quarantine(ProbeRows(conn), agency, now)


def assert_converged(root: Path, agency: uuid.UUID, doc: uuid.UUID, body: bytes = PDF) -> None:
    with connect() as conn:
        row = ProbeRows(conn).load(doc)
    assert row is not None and row.av_status is Status.CLEAN
    assert row.object_key == f"clean/{agency}/{doc}"
    assert download(doc) == body
    sweep(agency)
    assert files_under(root) == [f"clean/{agency}/{doc}"]


class _Stream:
    def __init__(self, body: bytes) -> None:
        self.body, self.at = body, 0

    def read(self, size: int, /) -> bytes:
        piece = self.body[self.at : self.at + size]
        self.at += len(piece)
        return piece


@pytest.fixture
def agency(files_probe: None, files_root: Path) -> uuid.UUID:
    return uuid.uuid4()


def test_crash_during_upload_write(files_root: Path, agency: uuid.UUID) -> None:
    with storage.arm("upload_write"), pytest.raises(SimulatedCrash):
        upload(agency)
    leftovers = files_under(files_root)
    assert (
        len(leftovers) == 1 and leftovers[0].startswith("tmp/") and leftovers[0].endswith(".part")
    )
    assert sweep(agency, later=False) == 0  # younger than the sweep age: kept
    doc = upload(agency).id
    assert attempt(agency, doc) is Outcome.PUBLISHED
    assert_converged(files_root, agency, doc)


def test_crash_after_quarantine_rename_before_row_commit(
    files_root: Path, agency: uuid.UUID
) -> None:
    with storage.arm("after_quarantine_rename"), pytest.raises(SimulatedCrash):
        upload(agency)
    (orphan,) = files_under(files_root)
    assert orphan.startswith(f"quarantine/{agency}/")
    assert status(uuid.UUID(orphan.rsplit("/", 1)[1])) is None
    doc = upload(agency).id
    assert attempt(agency, doc) is Outcome.PUBLISHED
    assert_converged(files_root, agency, doc)


def test_crash_during_output_write(files_root: Path, agency: uuid.UUID) -> None:
    doc = upload(agency).id
    with storage.arm("output_write"), pytest.raises(SimulatedCrash):
        attempt(agency, doc)
    assert status(doc) is Status.PENDING and download(doc) is None
    assert any(f.startswith(f"tmp/{doc}.") for f in files_under(files_root))
    assert attempt(agency, doc) is Outcome.PUBLISHED
    assert_converged(files_root, agency, doc)


def test_crash_after_publish_rename_before_db_commit(files_root: Path, agency: uuid.UUID) -> None:
    doc = upload(agency).id
    with storage.arm("after_publish_rename"), pytest.raises(SimulatedCrash):
        attempt(agency, doc)
    assert f"clean/{agency}/{doc}" in files_under(files_root)
    assert status(doc) is Status.PENDING and download(doc) is None  # no committed row: not served
    assert attempt(agency, doc) is Outcome.PUBLISHED  # redoes steps 2-6, replaces the file
    assert_converged(files_root, agency, doc)


def test_crash_after_commit_before_quarantine_delete(files_root: Path, agency: uuid.UUID) -> None:
    doc = upload(agency).id
    with storage.arm("before_quarantine_delete"), pytest.raises(SimulatedCrash):
        attempt(agency, doc)
    assert status(doc) is Status.CLEAN and download(doc) == PDF
    assert f"quarantine/{agency}/{doc}" in files_under(files_root)
    assert attempt(agency, doc) is Outcome.ALREADY_CLEAN
    assert_converged(files_root, agency, doc)


class BlockingScanner(FakeScanner):
    def __init__(self) -> None:
        super().__init__()
        self.entered, self.release = threading.Event(), threading.Event()

    def scan(self, chunks: Iterator[bytes]) -> Any:
        self.entered.set()
        assert self.release.wait(30)
        return super().scan(chunks)


def test_concurrent_second_attempt_waits_on_the_advisory_lock(
    files_root: Path, agency: uuid.UUID
) -> None:
    doc, first = upload(agency).id, BlockingScanner()
    outcomes: dict[str, Outcome | BaseException] = {}

    def run(name: str, scanner: FakeScanner) -> None:
        try:
            outcomes[name] = attempt(agency, doc, scanner)
        except BaseException as exc:  # reported by the asserts below
            outcomes[name] = exc

    threads = [threading.Thread(target=run, args=("first", first))]
    threads[0].start()
    assert first.entered.wait(10)
    threads.append(threading.Thread(target=run, args=("second", FakeScanner())))
    threads[1].start()
    try:
        deadline = time.monotonic() + 10
        with connect() as conn:
            while time.monotonic() < deadline:
                waiting = conn.execute(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory'"
                    " AND NOT granted AND classid = %s",
                    (LOCK_CLASS,),
                ).fetchone()
                if waiting and waiting[0] == 1:
                    break
                time.sleep(0.05)
            else:
                pytest.fail("the second attempt did not wait on the advisory lock")
        assert "second" not in outcomes
    finally:
        first.release.set()
        for thread in threads:
            thread.join(30)
    assert outcomes == {"first": Outcome.PUBLISHED, "second": Outcome.ALREADY_CLEAN}
    assert_converged(files_root, agency, doc)


@pytest.mark.parametrize("damage", ["altered", "truncated"])
def test_a_damaged_clean_file_is_refused_and_marked(
    files_root: Path, agency: uuid.UUID, damage: str
) -> None:
    doc = upload(agency).id
    assert attempt(agency, doc) is Outcome.PUBLISHED
    clean = files_root / "clean" / str(agency) / str(doc)
    body = clean.read_bytes()
    if damage == "altered":  # same size, one byte changed: only the SHA-256 catches it
        clean.write_bytes(body[:100] + bytes([body[100] ^ 1]) + body[101:])
        assert download(doc) is None
    else:  # the scan job's step 1 finds it before any download
        clean.write_bytes(body[: len(body) // 2])
        assert attempt(agency, doc) is Outcome.INTEGRITY_FAILED
    assert status(doc) is Status.INTEGRITY_FAILED
    assert download(doc) is None
    assert attempt(agency, doc) is Outcome.INTEGRITY_FAILED  # never republished over
    assert clean.read_bytes() != body
