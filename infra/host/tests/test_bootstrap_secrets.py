"""`bootstrap-secrets init|restore` (spec §8.4 H4; plan §3 M1d).

Each test runs on a temporary root with a fake `age` (header + base64 of its stdin) and a recording
chown, so no root and no real key are needed. Every key value is generated at run time.
"""

import base64
import hashlib
import io
import json
import os
import re
import secrets as token
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from config import env
from skiw_host import bootstrap_secrets
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
        self.code = -1

    def chown(self, path: str, uid: int, gid: int) -> None:
        assert gid == 0
        self.chowns[Path(path).name.removeprefix(".").removesuffix(".tmp")] = uid

    def run(
        self,
        *argv: str,
        chown: Callable[[str, int, int], None] | None = None,
        journal: Callable[[str], None] | None = None,
        stdin: bytes = b"",
    ) -> int:
        args = [
            *argv,
            "--env-file",
            str(self.env),
            "--root",
            str(self.root),
            "--age",
            str(self.age),
        ]
        return main(args, chown or self.chown, journal or self.journal.append, io.BytesIO(stdin))

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


def entry(number: int) -> dict[str, str]:
    line = f"v{number}:{base64.b64encode(token.token_bytes(32)).decode()}"
    return {"line": line, "sha256": hashlib.sha256(line.encode()).hexdigest()}


def generated() -> dict[str, object]:
    return {"format": "skiw-escrow-1", "keys": {name: [entry(1)] for name in APP_KEYS}}


def restored(tmp_path: Path, bundle: object, *argv: str, **kw: Callable[..., None]) -> Rig:
    other = Rig(tmp_path, "b")
    other.code = other.run("restore", *argv, stdin=json.dumps(bundle).encode(), **kw)
    return other


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
    rig: Rig, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    assert rig.run("init") == 0
    bundle = doc(rig)
    del bundle["keys"]["field_kek"]
    other = restored(tmp_path, bundle, "--allow-new-key-version", "field_kek")
    assert other.code == 0
    out, err = capfd.readouterr()
    logs = [(r.root / "var/log/skiw/deploy.log").read_text() for r in (rig, other)]
    seen = "\n".join([out, err, *logs, *rig.journal, *other.journal])
    values = [line for r in (rig, other) for k in APP_KEYS for line in r.files()[k].split()]
    assert values and "init: 10 key files installed" in logs[0] and "field_kek v1" in logs[1]
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


def test_restore_installs_versions_verbatim_then_init_and_restore_refuse(
    rig: Rig, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    assert rig.run("init") == 0
    bundle = doc(rig)
    v2 = entry(2)
    bundle["keys"]["audit_mac_key"].insert(0, v2)  # newest listed first in the bundle
    other = restored(tmp_path, bundle)
    assert other.code == 0
    files = other.files()
    assert files.pop(".restored") and other.chowns[".restored"] == 0
    assert (other.secrets / ".restored").stat().st_mode & 0o777 == 0o400
    assert files["audit_mac_key"] == rig.files()["audit_mac_key"] + f"{v2['line']}\n"
    assert {k: v for k, v in files.items() if k != "audit_mac_key"} == {
        k: v for k, v in rig.files().items() if k != "audit_mac_key"
    }
    assert set(json.loads(other.plaintext())["keys"]) == set(APP_KEYS)  # re-escrowed
    capfd.readouterr()
    before = other.files(), other.bundles()
    assert other.run("init") == 2
    assert other.run("restore", stdin=json.dumps(bundle).encode()) == 2
    assert capfd.readouterr().err.count("already restored") == 2
    assert (other.files(), other.bundles()) == before


@pytest.mark.parametrize(
    ("spoil", "reason"),
    [
        pytest.param(lambda b: b["keys"].pop("crm_jar_kek"), "lacks crm_jar_kek", id="missing-key"),
        pytest.param(
            lambda b: b["keys"]["login_blob_key"][0].update(sha256="0" * 64),
            "login_blob_key: version entry 1 does not match its SHA-256",
            id="wrong-sha256",
        ),
        pytest.param(
            lambda b: b["keys"].update(skiw_app_password=[entry(1)]),
            "1 entries outside the app-key inventory",
            id="extra-db-password",
        ),
        pytest.param(
            lambda b: b["keys"]["tenant_token_key"][0].update(
                line="v1:c2hvcnQ=", sha256=hashlib.sha256(b"v1:c2hvcnQ=").hexdigest()
            ),
            "tenant_token_key: version entry 1 is not 32 bytes",
            id="short-key",
        ),
        pytest.param(
            lambda b: b["keys"]["field_kek"].append(entry(1)),
            "field_kek: version entry 2 is malformed or repeated",
            id="repeated-version",
        ),
        pytest.param(
            lambda b: b["keys"]["field_kek"][0].update(line="1:x"),
            "field_kek: version entry 1 is malformed or repeated",
            id="malformed-line",
        ),
        pytest.param(
            lambda b: b.update(format="other"), "not a decrypted escrow bundle", id="not-a-bundle"
        ),
    ],
)
def test_restore_refuses_a_bad_bundle_and_writes_nothing(
    tmp_path: Path,
    spoil: Callable[[dict[str, object]], object],
    reason: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    bundle: dict[str, object] = json.loads(json.dumps(generated()))
    spoil(bundle)
    other = restored(tmp_path, bundle)
    assert other.code == 2
    assert reason in capfd.readouterr().err
    assert not other.root.exists()


def test_restore_refuses_a_seven_digit_version_without_echoing_it(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """The app reads at most v999999 (config.env KEY_LINE, accounts.source_key SEALED)."""
    big = entry(1_000_000)
    keys = {name: [big if name == "field_kek" else entry(1)] for name in APP_KEYS}
    other = restored(tmp_path, {"format": "skiw-escrow-1", "keys": keys})
    assert other.code == 2
    err = capfd.readouterr().err
    assert "field_kek: version entry 1 is malformed or repeated" in err
    assert big["line"].partition(":")[2] not in err and not other.root.exists()


def test_restore_refuses_a_non_empty_store(tmp_path: Path) -> None:
    other = Rig(tmp_path, "b")
    other.secrets.mkdir(parents=True)
    (other.secrets / "ghcr_read_token").write_text("x\n")
    assert other.run("restore", stdin=json.dumps(generated()).encode()) == 2
    assert other.files() == {"ghcr_read_token": "x\n"} and other.bundles() == []


def test_override_mints_only_the_named_keys_and_records_them(
    rig: Rig, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    assert rig.run("init") == 0
    bundle = doc(rig)
    del bundle["keys"]["crm_jar_kek"]
    flags = ["--allow-new-key-version", "crm_jar_kek", "--allow-new-key-version", "field_kek"]
    other = restored(tmp_path, bundle, *flags)
    assert other.code == 0
    old, new = rig.files(), other.files()
    assert [k for k in APP_KEYS if new[k] != old[k]] == ["field_kek", "crm_jar_kek"]
    assert (
        re.fullmatch(r"v1:\S+\n", new["crm_jar_kek"]) and new["crm_jar_kek"] != old["crm_jar_kek"]
    )
    assert new["field_kek"].startswith(old["field_kek"])
    assert re.fullmatch(r"v2:\S+\n", new["field_kek"].removeprefix(old["field_kek"]))
    lines = [
        f"restore minted {k} (--allow-new-key-version)" for k in ("crm_jar_kek v1", "field_kek v2")
    ]
    assert [line for line in other.journal if "minted" in line] == lines
    log = (other.root / "var/log/skiw/deploy.log").read_text()
    err = capfd.readouterr().err
    assert all(line in log and line in err for line in lines)
    keys = json.loads(other.plaintext())["keys"]
    escrowed = {n: "".join(v["line"] + "\n" for v in vs) for n, vs in keys.items()}
    assert escrowed == {k: v for k, v in new.items() if k != ".restored"}


def test_override_is_refused_for_init_or_a_name_outside_the_app_keys(rig: Rig) -> None:
    assert rig.run("init", "--allow-new-key-version", "field_kek") == 2
    stdin = json.dumps(generated()).encode()
    assert rig.run("restore", "--allow-new-key-version", "skiw_app_password", stdin=stdin) == 2
    assert not rig.root.exists()


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


def test_restore_failure_at_the_marker_rolls_back_everything(tmp_path: Path) -> None:
    def chown(path: str, uid: int, gid: int) -> None:
        if path.endswith(".restored.tmp"):
            raise PermissionError(1, "Operation not permitted", path)

    bundle = generated()
    other = restored(tmp_path, bundle, "--allow-new-key-version", "field_kek", chown=chown)
    assert other.code == 1
    assert other.files() == {} and other.bundles() == []
    assert other.run("restore", stdin=json.dumps(bundle).encode()) == 0  # retry on the empty store


def test_restore_journal_failure_after_commit_keeps_everything_and_exits_3(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    def journal(message: str) -> None:
        raise OSError(5, "Input/output error")

    other = restored(tmp_path, generated(), "--allow-new-key-version", "field_kek", journal=journal)
    assert other.code == 3
    err = capfd.readouterr().err
    assert "Minted by override: field_kek v2." in err and "Do not run restore again" in err
    assert "Traceback" not in err
    assert set(other.files()) == {*APP_KEYS, ".restored"} and len(other.bundles()) == 1
    assert not [v for k in APP_KEYS for v in other.files()[k].split() if v in err]


def test_journal_failure_after_install_keeps_the_keys_and_exits_3(
    rig: Rig, capfd: pytest.CaptureFixture[str]
) -> None:
    def journal(message: str) -> None:
        raise OSError(5, "Input/output error")

    assert rig.run("init", journal=journal) == 3
    err = capfd.readouterr().err
    assert "installed" in err and "Do not run init again" in err and "Traceback" not in err
    assert (
        set(rig.files()) == set(APP_KEYS) and len(rig.bundles()) == 1
    )  # committed, not rolled back
    assert not [v for k in APP_KEYS for v in rig.files()[k].split() if v in err]
    assert rig.run("init") == 2  # the documented outcome: the store is not empty


def test_deploy_log_failure_after_install_keeps_the_keys_and_exits_3(
    rig: Rig, capfd: pytest.CaptureFixture[str]
) -> None:
    (rig.root / "var/log").mkdir(parents=True)
    (rig.root / "var/log/skiw").write_text("a file where the log directory should be\n")
    assert rig.run("init") == 3
    err = capfd.readouterr().err
    assert "installed" in err and "Traceback" not in err
    assert set(rig.files()) == set(APP_KEYS) and len(rig.bundles()) == 1


@pytest.mark.parametrize("mode", ["init", "restore"])
def test_escrow_directory_is_synced_before_the_first_key_is_installed(
    rig: Rig, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    monkeypatch.setattr(bootstrap_secrets, "sync_dir", lambda d: events.append(f"sync:{d.name}"))

    def chown(path: str, uid: int, gid: int) -> None:
        rig.chown(path, uid, gid)
        events.append(f"chown:{Path(path).name}")

    assert rig.run(mode, chown=chown, stdin=json.dumps(generated()).encode()) == 0
    first_key = next(
        i for i, e in enumerate(events) if e.startswith("chown:.") and e.endswith(".tmp")
    )
    assert "sync:escrow" in events[:first_key]
    assert events.count("sync:secrets") == 1 and events.index("sync:secrets") > first_key
    marker = [i for i, e in enumerate(events) if e == "chown:..restored.tmp"]
    assert marker == ([events.index("sync:secrets") - 1] if mode == "restore" else [])


def test_failed_escrow_sync_installs_no_key_and_leaves_no_bundle(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sync_dir(directory: Path) -> None:
        if directory.name == "escrow":
            raise OSError(5, "Input/output error", str(directory))

    monkeypatch.setattr(bootstrap_secrets, "sync_dir", sync_dir)
    assert rig.run("init") == 1
    assert rig.files() == {} and rig.bundles() == []


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
    assert result.returncode == 0 and "--allow-new-key-version" in result.stdout


# The installed programs run as `python3 -I` (their shebang) with stderr on the SSH channel.
CLOSED_STDERR = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from skiw_host.bootstrap_secrets import Host, record
root = Path(sys.argv[2])
journal = lambda message: (root / "journal").write_text(message)
record(Host(root, lambda p, u, g: None), journal, "deploy x key staging: done", "skiw-deploy")
sys.exit(int(sys.argv[3]))
"""


@pytest.mark.parametrize("code", [0, 1, 2])
def test_a_closed_stderr_loses_no_record_and_keeps_the_exit_code(tmp_path: Path, code: int) -> None:
    read, write = os.pipe()
    os.close(read)  # the SSH client is gone: every write to stderr fails with EPIPE
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", CLOSED_STDERR, str(HOST), str(tmp_path), str(code)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=write,
            timeout=60,
            check=False,
        )
    finally:
        os.close(write)
    assert result.returncode == code  # not 1 (an uncaught error) or 120 (a failed exit flush)
    assert (tmp_path / "journal").read_text() == "deploy x key staging: done"
    [line] = (tmp_path / "var/log/skiw/deploy.log").read_text().splitlines()
    assert line.endswith(" skiw-deploy: deploy x key staging: done")
