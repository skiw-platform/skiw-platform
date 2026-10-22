"""`predeploy` (infra/host/backup/predeploy; spec §8.4 H3 step 4, H6; plan §3 M1g).

Fake processes stand in for pg_dump, pg_restore --list and age with their real failure rules: each
exits non-zero on failure, and a reader that stops early breaks the writer's pipe. The password is
generated per test and must reach only the libpq password file.
"""

import importlib.util
import io
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from types import ModuleType
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "backup/predeploy/predeploy.py"
RECIPIENT = "age1" + "q" * 58
NOW = datetime(2026, 10, 22, 10, 15, tzinfo=UTC)
NAME = "20261022T101500Z.dump.age"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("predeploy", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


predeploy = load()


class Process:
    def __init__(self, tools: "Tools", argv: list[str], **kwargs: Any) -> None:
        self.argv, self.kwargs, self.code = argv, kwargs, tools.codes.get(argv[0], 0)
        self.stdout = io.BytesIO(tools.archive) if argv[0] == "pg_dump" else None
        self.stdin = Sink(argv[0] in tools.early) if kwargs.get("stdin") else None
        self.done, self.killed = False, False
        tools.started.append(self)
        if argv[0] == "pg_dump":
            tools.passfile = Path(kwargs["env"]["PGPASSFILE"]).read_text()
            tools.passmode = Path(kwargs["env"]["PGPASSFILE"]).stat().st_mode & 0o777

    def wait(self) -> int:
        if self.killed:  # SIGKILL: no output, exit -9
            self.done = True
            return -9
        if self.argv[0] == "pg_restore":  # a partial table of contents even when it fails
            self.kwargs["stdout"].write(b"; Archive created\n1; TABLE public t\n")
        if self.argv[0] == "age" and self.code == 0:
            Path(self.argv[-1]).write_bytes(b"age-encrypted:" + bytes(self.stdin.data))  # type: ignore[union-attr]
        self.done = True
        return self.code

    def poll(self) -> int | None:
        return self.code if self.done else None

    def kill(self) -> None:
        self.killed = True


class Sink:
    def __init__(self, early: bool) -> None:
        self.data, self.early = bytearray(), early

    def write(self, chunk: bytes) -> None:
        if self.early:
            raise BrokenPipeError
        self.data += chunk

    def close(self) -> None:
        pass


class Tools:
    def __init__(self) -> None:
        self.archive = b"PGDMP" + os.urandom(200_000)
        self.codes: dict[str, int] = {}
        self.early: set[str] = set()
        self.started: list[Process] = []
        self.passfile, self.passmode = "", 0

    def popen(self, argv: list[str], **kwargs: Any) -> Process:
        return Process(self, argv, **kwargs)


@pytest.fixture
def rig(tmp_path: Path) -> tuple[Tools, Path, Path, str]:
    out, secret = tmp_path / "predeploy", tmp_path / "skiw_backup_password"
    out.mkdir()
    value = token_urlsafe(24)
    secret.write_text(f"{value}\n")
    return Tools(), out, secret, value


def run(rig: tuple[Tools, Path, Path, str], env: dict[str, str] | None = None) -> int:
    tools, out, secret, _ = rig
    environ = {"SKIW_DUMP_RECIPIENTS": RECIPIENT, "SKIW_POSTGRES_DB": "skiw"} | (env or {})
    return int(predeploy.main(["predeploy"], environ, tools.popen, out, secret, lambda: NOW))


def test_dumps_checks_encrypts_and_prints_the_one_line(
    rig: tuple[Tools, Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    tools, out, _, value = rig
    assert run(rig) == 0
    data = (out / NAME).read_bytes()
    assert data == b"age-encrypted:" + tools.archive  # the whole stream reached age
    digest = predeploy.hashlib.sha256(data).hexdigest()
    assert capsys.readouterr().out == f"predeploy {NAME} {digest}\n"
    assert (out / f"{NAME}.sha256").read_text() == f"{digest}  {NAME}\n"
    assert sorted(p.name for p in out.iterdir()) == [NAME, f"{NAME}.sha256"]
    assert (out / NAME).stat().st_mode & 0o777 == 0o400
    dump, check, age = (p.argv for p in tools.started)
    assert dump[:2] == ["pg_dump", "-Fc"] and "skiw_backup" in dump
    assert {a for a in dump if a.startswith("--exclude-table-data=")} == {
        "--exclude-table-data=guard.tenant_mac_key",
        "--exclude-table-data=guard.approval_mac_key",
        "--exclude-table-data=guard.lookup_decoy_key",
    }
    assert check == ["pg_restore", "--list"] and age[:3] == ["age", "-r", RECIPIENT]
    assert tools.started[1].stdin.data == tools.archive  # type: ignore[union-attr]
    assert tools.passfile == f"db:5432:skiw:skiw_backup:{value}\n" and tools.passmode == 0o600
    assert all(
        value not in " ".join(p.argv) and value not in str(p.kwargs.get("env"))
        for p in tools.started[1:]
    )
    assert value not in " ".join(tools.started[0].argv)


@pytest.mark.parametrize(
    "fault",
    [
        {"codes": {"pg_dump": 1}},
        {"codes": {"pg_restore": 1}},  # the stream is not a readable archive
        {"codes": {"age": 1}},
        {"early": {"pg_restore"}},  # a reader stopped early: broken pipe
        {"env": {"SKIW_DUMP_RECIPIENTS": ""}},
        {"env": {"SKIW_DUMP_RECIPIENTS": "AGE-SECRET-KEY-1QQQ"}},
        {"env": {"SKIW_POSTGRES_DB": "skiw; drop"}},
    ],
)
def test_any_failure_keeps_nothing_and_prints_no_value(
    rig: tuple[Tools, Path, Path, str], capsys: pytest.CaptureFixture[str], fault: dict[str, Any]
) -> None:
    tools, out, _, value = rig
    tools.codes, tools.early = fault.get("codes", {}), fault.get("early", set())
    assert run(rig, fault.get("env")) == 1
    assert list(out.iterdir()) == []
    printed = capsys.readouterr()
    assert printed.out == "" and printed.err.startswith("predeploy: failed, nothing kept:")
    assert value not in printed.err and "AGE-SECRET-KEY" not in printed.err
    assert all(p.done or p.killed for p in tools.started)  # no child left running


def test_only_the_predeploy_command_runs(rig: tuple[Tools, Path, Path, str]) -> None:
    tools, out, secret, _ = rig
    for argv in ([], ["--version"], ["predeploy", "x"]):
        assert predeploy.main(argv, {}, tools.popen, out, secret, lambda: NOW) == 2
    assert tools.started == [] and subprocess.PIPE  # nothing started
