"""`predeploy` (infra/host/backup/predeploy; spec §8.4 H3 step 4, H6; plan §3 M1g).

Fake processes stand in for pg_dump, pg_restore and age with the real tools' contracts: each exits
non-zero on failure; pg_restore reads the header and table of contents and may then stop reading
(exit 0 on success, non-zero on failure), so a write to its pipe breaks; age reads every byte. The
password is generated per test and must reach only the libpq password file.
"""

import ast
import errno
import hashlib
import importlib.util
import io
import os
import re
import stat
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from types import ModuleType

import pytest

HOST = Path(__file__).resolve().parents[1]
SOURCE = HOST / "backup/predeploy/predeploy.py"
DOCKERFILE = HOST / "backup/predeploy/Dockerfile"
RECIPIENT = "age1" + "q" * 58
NOW = datetime(2026, 10, 22, 10, 15, tzinfo=UTC)
NAME = "20261022T101500Z.dump.age"
TOC = 4096  # what the fake pg_restore reads before it stops


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("predeploy", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


predeploy = load()


class Pipe:
    """A child's stdin: takes `limit` bytes, then the reader has gone (EPIPE)."""

    def __init__(self, limit: int | None) -> None:
        self.data, self.limit, self.closed = bytearray(), limit, False

    def write(self, chunk: bytes) -> int:
        if self.limit is not None and len(self.data) >= self.limit:
            raise BrokenPipeError(errno.EPIPE, "Broken pipe")
        self.data += chunk
        return len(chunk)

    def close(self) -> None:
        self.closed = True


class Process:
    def __init__(self, tools: "Tools", argv: list[str], **kwargs: object) -> None:
        self.argv, self.kwargs, self.code = argv, kwargs, tools.codes.get(argv[0], 0)
        self.stdout = io.BytesIO(tools.archive) if argv[0] == "pg_dump" else None
        if tools.lock_held and argv[0] == "pg_dump":  # a table lock it cannot take
            # Real pg_dump 17.11 (probed): without --lock-wait-timeout it waits forever; with it,
            # it gives up after the bound before writing a byte and exits 1.
            assert any(a.startswith("--lock-wait-timeout=") for a in argv), "waits forever"
            self.stdout, self.code = io.BytesIO(b""), 1
        if tools.lock_held and argv[0] == "pg_restore":  # an empty stream is not an archive
            self.code = 1
        limit = {"pg_restore": tools.toc, "age": tools.age_reads}.get(argv[0])
        self.stdin = Pipe(limit) if kwargs.get("stdin") is subprocess.PIPE else None
        self.done, self.killed = False, False
        tools.started.append(self)
        env = kwargs["env"]
        assert isinstance(env, dict)
        if argv[0] == "pg_dump":
            tools.passfile = Path(env["PGPASSFILE"]).read_text()
            tools.passmode = Path(env["PGPASSFILE"]).stat().st_mode & 0o777

    def wait(self) -> int:
        if self.killed:  # SIGKILL: no output, exit -9
            self.done = True
            return -9
        if self.argv[0] == "age" and self.code == 0 and self.stdin is not None:
            Path(self.argv[-1]).write_bytes(b"age-encrypted:" + bytes(self.stdin.data))
        self.done = True
        return self.code

    def poll(self) -> int | None:
        return self.code if self.done else None

    def kill(self) -> None:
        self.killed = True


class Tools:
    def __init__(self) -> None:
        self.archive = b"PGDMP" + os.urandom(200_000)
        self.codes: dict[str, int] = {}
        self.toc: int | None = TOC
        self.age_reads: int | None = None
        self.started: list[Process] = []
        self.lock_held = False  # a migration or long transaction holds a conflicting table lock
        self.passfile, self.passmode = "", 0

    def spawn(self, argv: list[str], **kwargs: object) -> Process:
        return Process(self, argv, **kwargs)

    def stdin(self, tool: str) -> Pipe:
        pipe = next(p.stdin for p in self.started if p.argv[0] == tool)
        assert pipe is not None
        return pipe


Rig = tuple[Tools, Path, Path, str]


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    out, secret = tmp_path / "predeploy", tmp_path / "skiw_backup_password"
    out.mkdir()
    value = token_urlsafe(24)
    secret.write_text(f"{value}\n")
    return Tools(), out, secret, value


def run(rig: Rig, env: dict[str, str] | None = None) -> int:
    tools, out, secret, _ = rig
    environ = {"SKIW_DUMP_RECIPIENTS": RECIPIENT, "SKIW_POSTGRES_DB": "skiw"} | (env or {})
    return int(predeploy.main(["predeploy"], environ, tools.spawn, out, secret, lambda: NOW))


def test_dumps_checks_encrypts_and_prints_the_one_line(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    tools, out, _, value = rig
    assert run(rig) == 0
    data = (out / NAME).read_bytes()
    assert data == b"age-encrypted:" + tools.archive  # the whole stream reached age
    digest = hashlib.sha256(data).hexdigest()
    assert capsys.readouterr().out == f"predeploy {NAME} {digest}\n"
    assert (out / f"{NAME}.sha256").read_text() == f"{digest}  {NAME}\n"
    assert sorted(p.name for p in out.iterdir()) == [NAME, f"{NAME}.sha256"]
    assert {(out / n).stat().st_mode & 0o777 for n in (NAME, f"{NAME}.sha256")} == {0o400}
    dump, check, age = (p.argv for p in tools.started)
    assert dump[:2] == ["pg_dump", "-Fc"] and "skiw_backup" in dump
    assert {a for a in dump if a.startswith("--exclude-table-data=")} == {
        "--exclude-table-data=guard.tenant_mac_key",
        "--exclude-table-data=guard.approval_mac_key",
        "--exclude-table-data=guard.lookup_decoy_key",
    }
    assert check == ["pg_restore", "-f", "/dev/null"] and age[:3] == ["age", "-r", RECIPIENT]
    assert tools.archive.startswith(tools.stdin("pg_restore").data)  # it read the start only
    assert tools.passfile == f"db:5432:skiw:skiw_backup:{value}\n" and tools.passmode == 0o600
    assert all("PGPASSFILE" not in str(p.kwargs["env"]) for p in tools.started[1:])
    assert all(value not in " ".join(p.argv) + str(p.kwargs["env"]) for p in tools.started)


def test_a_large_archive_reaches_age_whole_after_the_validator_stops_reading(rig: Rig) -> None:
    tools, out, _, _ = rig
    tools.archive = b"PGDMP" + os.urandom(6 << 20)  # far beyond any pipe buffer
    assert run(rig) == 0
    assert (out / NAME).read_bytes() == b"age-encrypted:" + tools.archive
    assert len(tools.stdin("pg_restore").data) < len(tools.archive)  # it stopped early, exit 0
    assert tools.stdin("pg_restore").closed and tools.stdin("age").closed


def test_the_checksum_reads_in_bounded_blocks(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tools, out, _, _ = rig
    tools.archive = b"PGDMP" + os.urandom(5 << 20)
    sizes: list[int] = []
    real_read = os.read

    def counted(fd: int, size: int) -> bytes:
        sizes.append(size)
        return real_read(fd, size)

    monkeypatch.setattr(predeploy.os, "read", counted)
    assert run(rig) == 0
    monkeypatch.undo()
    with (out / NAME).open("rb") as handle:  # an independent streaming checksum
        independent = hashlib.file_digest(handle, "sha256").hexdigest()
    assert capsys.readouterr().out == f"predeploy {NAME} {independent}\n"
    assert len(sizes) > 5 and max(sizes) == predeploy.HASH_BLOCK == 1 << 20


@pytest.mark.parametrize(
    "fault",
    [
        {"codes": {"pg_dump": 1}},
        {"codes": {"pg_restore": 1}},  # read the start, then found it unreadable
        {"codes": {"pg_restore": 1}, "toc": None},  # read it all, then failed
        {"codes": {"age": 1}},
        {"age_reads": 1000},  # age stopped reading: the encrypted copy is incomplete
        {"archive": b"not an archive" * 100},  # tools exit 0 on a stream that is not PGDMP
        {"archive": b""},  # pg_dump wrote nothing
        {"env": {"SKIW_DUMP_RECIPIENTS": ""}},
        {"env": {"SKIW_DUMP_RECIPIENTS": "AGE-SECRET-KEY-1QQQ"}},
        {"env": {"SKIW_POSTGRES_DB": "skiw; drop"}},
    ],
)
def test_any_failure_keeps_nothing_and_prints_no_value(
    rig: Rig, capsys: pytest.CaptureFixture[str], fault: dict[str, object]
) -> None:
    tools, out, _, value = rig
    for key in ("codes", "toc", "age_reads", "archive"):
        if key in fault:
            setattr(tools, key, fault[key])
    env = fault.get("env")
    assert run(rig, env if isinstance(env, dict) else None) == 1
    assert list(out.iterdir()) == []
    printed = capsys.readouterr()
    assert printed.out == "" and printed.err.startswith("predeploy: failed, nothing kept:")
    assert value not in printed.err and "AGE-SECRET-KEY" not in printed.err
    assert all(p.done or p.killed for p in tools.started)  # no child left running


def test_a_held_table_lock_fails_the_dump_after_the_lock_wait_bound(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    tools, out, _, _ = rig
    tools.lock_held = True
    assert run(rig) == 1
    [dump] = [p.argv for p in tools.started if p.argv[0] == "pg_dump"]
    assert f"--lock-wait-timeout={predeploy.LOCK_WAIT_MS}" in dump
    assert 0 < predeploy.LOCK_WAIT_MS <= 60_000  # well inside skiw-deploy's own dump bound
    assert list(out.iterdir()) == []
    assert capsys.readouterr().err.startswith("predeploy: failed, nothing kept:")
    assert all(p.done or p.killed for p in tools.started)  # no child left running


def recorder(
    monkeypatch: pytest.MonkeyPatch, events: list[tuple[str, str]], fail: str | None
) -> None:
    """Record the publication steps; raise EIO at the step named `fail`."""
    real_fsync, real_link, real_unlink = os.fsync, os.link, os.unlink

    def step(name: str) -> None:
        events.append(("step", name))
        if name == fail:
            raise OSError(errno.EIO, "failpoint")

    def fsync(fd: int) -> None:
        st = os.fstat(fd)
        small = "sha" if st.st_size < 1000 else "dump"  # the checksum line, or the archive
        step(f"fsync {'dir' if stat.S_ISDIR(st.st_mode) else small}")
        real_fsync(fd)

    def link(src: str, dst: str) -> None:
        step("link")
        real_link(src, dst)

    def unlink(path: str, *, dir_fd: int | None = None) -> None:
        if Path(path).name == f".{NAME}.tmp" and ("step", "unlink tmp") not in events:
            step("unlink tmp")
        real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(predeploy.os, "fsync", fsync)
    monkeypatch.setattr(predeploy.os, "link", link)
    monkeypatch.setattr(predeploy.os, "unlink", unlink)

    def say(line: str, **kwargs: object) -> None:
        events.append(("print", line))

    monkeypatch.setattr(predeploy, "print", say, raising=False)


BARRIERS = ["fsync dump", "link", "fsync sha", "unlink tmp", "fsync dir"]


def test_every_persistence_barrier_precedes_the_success_line(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[tuple[str, str]] = []
    recorder(monkeypatch, events, None)
    assert run(rig) == 0
    monkeypatch.undo()
    assert [name for kind, name in events if kind == "step"] == BARRIERS
    assert events[-1][0] == "print" and events[-1][1].startswith(f"predeploy {NAME} ")


@pytest.mark.parametrize("fail", BARRIERS)
def test_a_failed_barrier_withholds_the_success_line_and_keeps_nothing(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, fail: str
) -> None:
    _, out, _, _ = rig
    events: list[tuple[str, str]] = []
    recorder(monkeypatch, events, fail)
    assert run(rig) == 1
    monkeypatch.undo()
    assert [e for e in events if e[0] == "print"] == [
        ("print", "predeploy: failed, nothing kept: OSError")
    ]
    assert list(out.iterdir()) == []


def test_only_the_predeploy_command_runs(rig: Rig) -> None:
    tools, out, secret, _ = rig
    for argv in ([], ["--version"], ["predeploy", "x"]):
        assert predeploy.main(argv, {}, tools.spawn, out, secret, lambda: NOW) == 2
    assert tools.started == []  # nothing started


def backup_sources() -> Iterator[Path]:
    yield from sorted((HOST / "backup").rglob("*.py"))


def test_backup_tooling_imports_only_the_standard_library() -> None:
    # UNI-04: infra/host/backup is not a package on any import path, so the import-linter
    # contracts cannot name it; this test is its boundary check (no app code, no third party).
    sources = list(backup_sources())
    assert SOURCE in sources
    for path in sources:
        tree = ast.parse(path.read_text(), str(path))
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        roots = {name.split(".")[0] for name in names}
        assert roots <= sys.stdlib_module_names, (path, roots - sys.stdlib_module_names)


def test_no_app_module_refers_to_the_backup_tooling() -> None:
    app = HOST.parents[1] / "app"
    hits = [
        p for p in app.rglob("*.py") if "predeploy" in p.read_text() or "backup.predeploy" in str(p)
    ]
    assert hits == []


def instructions(text: str) -> list[tuple[str, str]]:
    """The Dockerfile's instructions, continuation lines joined, comments dropped."""
    joined = re.sub(r"\s*\\\n\s*", " ", text)
    lines = [x.strip() for x in joined.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    return [(x.split()[0].upper(), x.partition(" ")[2]) for x in lines]


def bases(text: str) -> dict[str, str]:
    """Each FROM image by name; fails unless it is `name:tag@sha256:<64 hex>`."""
    found = {}
    for kind, value in instructions(text):
        if kind == "FROM":
            image = value.split()[0]
            assert re.fullmatch(r"[a-z]+:[0-9a-z.-]+@sha256:[0-9a-f]{64}", image), image
            found[image.partition(":")[0]] = image.partition("@")[0]
    return found


# The one apk layer allowed (DECISIONS 2026-11-11, "base images krb5-libs"): only these packages,
# each at a minimum fixed version, from Alpine's signed repository; `>=` is a deliberate exception.
APK_FIX = r'apk add --no-cache( "(krb5-libs|libxslt)>=[0-9][0-9.]*-r[0-9]+")+'


def check_dockerfile(text: str) -> None:
    """The dump image's build rules (DECISIONS 2026-10-23, "Dump image passes the Trivy gate")."""
    steps = instructions(text)
    found = bases(text)
    assert set(found) == {"golang", "python", "postgres"}
    alpine = {re.sub(r".*-alpine", "alpine", tag) for tag in found.values()}
    assert len(alpine) == 1 and re.fullmatch(r"alpine3\.[0-9]+", alpine.pop())  # one musl, libssl
    server = re.search(r"image: (postgres:[0-9.]+)@sha256:", (HOST / "compose.yml").read_text())
    assert server and found["postgres"].startswith(f"{server[1]}-alpine3.")  # same major.minor
    adds = [value for kind, value in steps if kind == "ADD"]
    assert len(adds) == 1 and re.fullmatch(
        r"--checksum=sha256:[0-9a-f]{64} https://github\.com/FiloSottile/age/archive/refs/tags/"
        r"v1\.3\.2\.tar\.gz /src/age\.tar\.gz",
        adds[0],
    ), adds
    runs = " ".join(value for kind, value in steps if kind == "RUN")
    assert not re.search(r"\b(curl|wget|go get|go install)\b|@latest", runs)  # unchecked input
    apk = [value for kind, value in steps if kind == "RUN" and re.search(r"\bapk\b", value)]
    assert len(apk) <= 1 and all(re.fullmatch(APK_FIX, value) for value in apk), apk
    env = " ".join(value for kind, value in steps if kind == "ENV").split()
    assert {"CGO_ENABLED=0", "GOFLAGS=-mod=readonly", "GOTOOLCHAIN=local"} <= set(env)
    assert not [x for x in env if x.startswith(("GONOSUMDB", "GONOSUMCHECK", "GOSUMDB", "GOPROXY"))]
    assert "go build -trimpath " in runs and '-X main.Version=v1.3.2"' in runs
    assert "rm /usr/local/bin/gosu" in runs
    for tool, version in (("pg_dump", "PostgreSQL) 17.11"), ("pg_restore", "PostgreSQL) 17.11")):
        assert f'test "$({tool} --version)" = "{tool} ({version}"' in runs
    assert 'test "$(age --version)" = "v1.3.2"' in runs
    final = steps[max(i for i, (kind, _) in enumerate(steps) if kind == "FROM") :]
    assert ("USER", "10003:10003") in final
    assert steps[-1] == ("ENTRYPOINT", '["python3", "-I", "/usr/local/lib/skiw/predeploy.py"]')


def test_the_dump_image_pins_every_input() -> None:
    check_dockerfile(DOCKERFILE.read_text())


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (r"(golang:[^@\s]+)@sha256:[0-9a-f]{64}", r"\1"),  # an unpinned base
        (r"(python:[^@\s]+)@sha256:[0-9a-f]{64}", r"\1"),
        (r"(postgres:[^@\s]+)@sha256:[0-9a-f]{64}", r"\1"),
        (r"postgres:17\.11-", "postgres:17.10-"),  # another client than the server's
        (r"python:3\.12\.15-alpine3\.\d+", "python:3.12.15-slim-trixie"),
        (r"ADD --checksum=sha256:[0-9a-f]{64} ", "ADD "),  # an unchecked download
        (r"GOFLAGS=-mod=readonly ", ""),
        (r"GOTOOLCHAIN=local", "GOTOOLCHAIN=auto"),
        (r"CGO_ENABLED=0 ", ""),
        (r"-trimpath ", ""),
        (r"rm /usr/local/bin/gosu \\\n    && ", ""),
        (r"USER 10003:10003", "USER root"),
        (r"(RUN tar)", r"ENV GONOSUMDB=*\n\1"),
        (r"(RUN rm)", r"RUN wget -O /tmp/x https://example.invalid/x\n\1"),
        (r"(RUN rm)", r"RUN apk add --no-cache curl\n\1"),  # any other apk package
        (r"(RUN rm)", r'RUN apk add --no-cache "krb5-libs>=1.22.3-r0" openssl\n\1'),  # a rider
        (r"(RUN rm)", r"RUN apk upgrade --no-cache\n\1"),
        (r'"libxslt>=1\.1\.43-r4"', '"busybox>=1.37.0-r0"'),  # a versioned, unlisted package
        (r"(RUN rm)", r"RUN curl -fsSL https://example.invalid/x\n\1"),
        (r'"krb5-libs>=1\.22\.3-r0" ', '"krb5-libs" '),  # no minimum version
        (r"(RUN rm)", r'RUN apk add --no-cache "libxslt>=1.1.43-r4"\n\1'),  # a second apk layer
    ],
)
def test_the_pin_check_fails_on_a_weakened_dockerfile(old: str, new: str) -> None:
    text = DOCKERFILE.read_text()
    weakened = re.sub(old, new, text, count=1)
    assert weakened != text, old
    with pytest.raises(AssertionError):
        check_dockerfile(weakened)
