"""`bootstrap-secrets init` (spec §8.4 H4; plan §3 M1d).

Each test runs on a temporary root with a fake `age` (header + base64 of its stdin) and a recording
chown, so no root and no real key are needed. Every key value is generated at run time.
"""

import base64
import json
import re
import secrets as token
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from config import env
from skiw_host.bootstrap_secrets import main
from skiw_host.secrets import APP_KEYS, INVENTORY, OWNER, Kind

HOST = Path(__file__).resolve().parents[1]
HEADER = b"age-encryption.org/v1\n"
BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
FAKE_AGE = """
import base64, os, sys
if sys.argv[1:] == ["--version"]:
    print(os.environ.get("FAKE_AGE_VERSION", "v1.3.2"))
    sys.exit(0)
if os.environ.get("FAKE_AGE_FAIL"):
    sys.exit(1)
sys.stdout.buffer.write(b"age-encryption.org/v1\\n" + base64.b64encode(sys.stdin.buffer.read()))
"""


class Rig:
    def __init__(self, tmp: Path, name: str) -> None:
        self.root = tmp / name
        self.age = tmp / "age"
        self.age.write_text(f"#!{sys.executable}\n{FAKE_AGE}")
        self.age.chmod(0o755)
        self.recipient = "age1" + "".join(token.choice(BECH32) for _ in range(58))
        self.env = tmp / f"{name}.env"
        self.env.write_text(f"SKIW_ESCROW_RECIPIENTS={self.recipient}\n")
        self.chowns: dict[str, int] = {}
        self.journal: list[str] = []
        self.secrets = self.root / "etc/skiw/secrets"
        self.escrow = self.root / "srv/skiw/escrow"

    def chown(self, path: str, uid: int, gid: int) -> None:
        assert gid == 0
        self.chowns[Path(path).name.removeprefix(".").removesuffix(".tmp")] = uid

    def run(self, *argv: str, chown: Callable[[str, int, int], None] | None = None) -> int:
        args = [
            *argv,
            "--env-file",
            str(self.env),
            "--root",
            str(self.root),
            "--age",
            str(self.age),
        ]
        return main(args, chown or self.chown, self.journal.append)

    def files(self) -> dict[str, str]:
        return (
            {p.name: p.read_text() for p in self.secrets.iterdir()} if self.secrets.exists() else {}
        )

    def bundles(self) -> list[Path]:
        return sorted(self.escrow.glob("*")) if self.escrow.exists() else []

    def plaintext(self) -> bytes:
        (path,) = self.bundles()
        data = path.read_bytes()
        assert data.startswith(HEADER)
        return base64.b64decode(data[len(HEADER) :])


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path, "a")


def doc(rig: Rig) -> dict[str, dict[str, list[dict[str, str]]]]:
    value: dict[str, dict[str, list[dict[str, str]]]] = json.loads(rig.plaintext())
    return value


def test_init_installs_each_app_key_with_owner_mode_and_escrow(rig: Rig) -> None:
    assert rig.run("init") == 0
    files = rig.files()
    assert set(files) == set(APP_KEYS)
    assert {name: rig.chowns[name] for name in files} == {name: OWNER[name] for name in files}
    assert rig.chowns["secrets"] == 0 and rig.chowns["escrow"] == 0
    for directory in (rig.secrets, rig.escrow):
        assert directory.stat().st_mode & 0o777 == 0o700
    for path in [*rig.secrets.iterdir(), *rig.bundles()]:
        assert path.stat().st_mode & 0o777 == 0o400
    for text in files.values():
        assert re.fullmatch(r"v1:([A-Za-z0-9+/=]+)\n", text)
        assert len(base64.b64decode(text[3:])) == 32
    keys = doc(rig)["keys"]
    escrowed = {n: "".join(v["line"] + "\n" for v in vs) for n, vs in keys.items()}
    assert escrowed == files  # every version of every app key
    db_and_owner = {s.name for s in INVENTORY if s.kind is not Kind.APP_KEY}
    assert db_and_owner and not db_and_owner & set(keys)
    assert not any(name in rig.plaintext().decode() for name in db_and_owner)


def test_values_never_reach_stdout_stderr_journal_or_deploy_log(
    rig: Rig, capfd: pytest.CaptureFixture[str]
) -> None:
    assert rig.run("init") == 0
    out, err = capfd.readouterr()
    log = (rig.root / "var/log/skiw/deploy.log").read_text()
    seen = "\n".join([out, err, log, *rig.journal])
    values = [line for k in APP_KEYS for line in rig.files()[k].split()]
    assert values and "init: 10 key files installed" in log
    assert not [v for v in values if v in seen or v.partition(":")[2] in seen]


def test_the_app_reads_the_minted_key_files(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    assert rig.run("init") == 0
    for name in APP_KEYS:
        monkeypatch.setenv("KEY_FILE", str(rig.secrets / name))
        assert env.key_versions("KEY_FILE") == [rig.files()[name][3:].strip()]


def test_init_twice_refuses_and_changes_nothing(rig: Rig) -> None:
    assert rig.run("init") == 0
    before = rig.files(), rig.bundles()
    assert rig.run("init") == 2
    assert (rig.files(), rig.bundles()) == before


@pytest.mark.parametrize("kind", ["private", "not-age"])
def test_escrow_recipient_must_be_public_and_is_never_echoed(
    rig: Rig, kind: str, capfd: pytest.CaptureFixture[str]
) -> None:
    if kind == "private":
        value = "AGE-SECRET-KEY-1" + "".join(token.choice(BECH32.upper()) for _ in range(58))
    else:
        value = token.token_urlsafe(40)
    rig.env.write_text(f"SKIW_ESCROW_RECIPIENTS={rig.recipient} {value}\n")
    assert rig.run("init") == 2
    out, err = capfd.readouterr()
    assert value not in out + err and "not shown" in err
    assert not rig.root.exists()


def test_no_escrow_recipient_refuses(rig: Rig) -> None:
    rig.env.write_text("SKIW_ESCROW_RECIPIENTS=\n")
    assert rig.run("init") == 2
    assert not rig.root.exists()


@pytest.mark.parametrize("env", [{"FAKE_AGE_FAIL": "1"}, {"FAKE_AGE_VERSION": "v1.2.1"}])
def test_age_failure_leaves_nothing(
    rig: Rig, env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert rig.run("init") == 2
    assert rig.files() == {} and rig.bundles() == []


def test_failure_while_installing_rolls_back(rig: Rig) -> None:
    calls: list[str] = []

    def chown(path: str, uid: int, gid: int) -> None:
        calls.append(path)
        if len(calls) == 6:
            raise PermissionError(1, "Operation not permitted", path)

    assert rig.run("init", chown=chown) == 1
    assert rig.files() == {} and rig.bundles() == []
    assert rig.run("init") == 0  # a retry works on the emptied store


def test_inventory_matches_the_compose_secret_files() -> None:
    # Static read, no docker: the Compose config test checks readers and uids on the rendered file.
    text = (HOST / "compose.yml").read_text().partition("\nsecrets:\n")[2]
    files = dict(re.findall(r"^  (\w+): \{file: /etc/skiw/secrets/(\w+)\}$", text, re.MULTILINE))
    assert all(name == file for name, file in files.items())
    assert set(files) == {s.name for s in INVENTORY if s.readers}
    assert len({s.name for s in INVENTORY}) == len(INVENTORY)


def test_executable_runs_the_module() -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(HOST / "bootstrap-secrets"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and "--env-file" in result.stdout
