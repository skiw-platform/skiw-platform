import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from config import env
from tests.settings_env import REQUIRED

APP_DIR = Path(__file__).resolve().parent.parent


def key(size: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(size)).decode()


@pytest.fixture
def secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("DJANGO_SECRET_KEY", "DJANGO_SECRET_KEY_FILE", "DATABASE_PASSWORD_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://skiw_app@db:5432/skiw")
    return tmp_path / "secret"


def test_key_versions_newest_first(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v1, v2, v3 = key(), key(), key()
    secret.write_text(f"v2:{v2}\nv3:{v3}\nv1:{v1}\n")
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(secret))
    assert env.secret_key() == (v3, [v2, v1])


@pytest.mark.parametrize(
    "content",
    [
        "",
        "v1:{k}\n\nv2:{k}\n",
        "v1:{k}\nv1:{k}\n",
        "v0:{k}\n",
        "1:{k}\n",
        "v1:{k} \n",
        "v1:{k}!\n",
        "v1:" + key(16) + "\n",
        "v1:{k}===\n",
    ],
)
def test_malformed_key_file_fails_closed_without_echoing_it(
    secret: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    value = key()
    secret.write_text(content.format(k=value))
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(secret))
    with pytest.raises(env.InvalidSettingError) as raised:
        env.secret_key()
    assert value not in str(raised.value)


def test_missing_key_file_fails_closed(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(secret))
    with pytest.raises(env.InvalidSettingError, match="cannot be read"):
        env.secret_key()


def test_key_env_and_key_file_together_fail(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret.write_text(f"v1:{key()}\n")
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(secret))
    monkeypatch.setenv("DJANGO_SECRET_KEY", key())
    with pytest.raises(env.InvalidSettingError, match="not both"):
        env.secret_key()


def test_key_from_env_without_a_file(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    value = key()
    monkeypatch.setenv("DJANGO_SECRET_KEY", value)
    assert env.secret_key() == (value, [])


def test_database_password_from_file(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    password = secrets.token_urlsafe(24)
    secret.write_text(password + "\n")
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", str(secret))
    assert env.database()["PASSWORD"] == password


@pytest.mark.parametrize("content", ["", "\n", "{p}\n{p}\n", "{p}\r\n"])
def test_malformed_password_file_fails_closed(
    secret: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    secret.write_text(content.format(p=secrets.token_urlsafe(24)))
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", str(secret))
    with pytest.raises(env.InvalidSettingError, match="exactly one"):
        env.database()


def test_password_in_url_and_file_fails(secret: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret.write_text(secrets.token_urlsafe(24))
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", str(secret))
    monkeypatch.setenv("DATABASE_URL", f"postgres://skiw_app:{secrets.token_urlsafe(8)}@db/skiw")
    with pytest.raises(env.InvalidSettingError, match="carries a password"):
        env.database()


@pytest.mark.parametrize(("content", "ok"), [("v1:{k}\nv2:{k}\n", True), ("v1:{k}=\n", False)])
def test_settings_import_reads_or_refuses_the_key_file(
    tmp_path: Path, content: str, ok: bool
) -> None:
    value = key()
    (tmp_path / "key").write_text(content.format(k=value))
    (tmp_path / "password").write_text(secrets.token_urlsafe(24))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config import settings as s; print(len(s.SECRET_KEY_FALLBACKS))",
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(APP_DIR),
            "DJANGO_SECRET_KEY_FILE": str(tmp_path / "key"),
            "DATABASE_PASSWORD_FILE": str(tmp_path / "password"),
            "DATABASE_URL": "postgres://skiw_app@db:5432/skiw",
            **REQUIRED,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0, result.stdout.strip()) == ((True, "1") if ok else (False, ""))
    assert value not in result.stderr


SOURCE = "TENANT_SOURCE_KEY"  # the M2c reader: `<name>_FILE` on hosts, `<name>` locally and in CI


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in (SOURCE, f"{SOURCE}_FILE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "tenant_source_key"


@pytest.mark.parametrize("form", ["file", "env"])
def test_versioned_keys_keep_their_numbers_newest_first(
    source: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    v1, v7, v3 = key(), key(40), key()
    content = f"v1:{v1}\nv7:{v7}\nv3:{v3}\n"
    if form == "file":
        source.write_text(content)
        monkeypatch.setenv(f"{SOURCE}_FILE", str(source))
    else:
        monkeypatch.setenv(SOURCE, content)
    decoded = [(n, base64.b64decode(k)) for n, k in ((7, v7), (3, v3), (1, v1))]
    assert env.versioned_keys(SOURCE) == decoded


@pytest.mark.parametrize("form", ["file", "env"])
@pytest.mark.parametrize(
    "content",
    ["", "v1:{k}\nv1:{k}\n", "v1:" + key(31) + "\n", "v1:{k}===\n", "v1:{k}!\n", "x1:{k}\n"],
    ids=["empty", "repeated", "short", "bad-base64", "bad-char", "no-version"],
)
def test_versioned_keys_fail_closed_without_echoing_the_key(
    source: Path, monkeypatch: pytest.MonkeyPatch, form: str, content: str
) -> None:
    value = key()
    text = content.format(k=value)
    if form == "file":
        source.write_text(text)
        monkeypatch.setenv(f"{SOURCE}_FILE", str(source))
    else:
        monkeypatch.setenv(SOURCE, text)
    with pytest.raises((env.InvalidSettingError, env.MissingSettingError)) as raised:
        env.versioned_keys(SOURCE)
    secrets_in_text = [row.split(":", 1)[1] for row in text.splitlines() if ":" in row]
    assert not [part for part in secrets_in_text if part in str(raised.value)]


def test_versioned_keys_refuse_both_forms(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    value = key()
    source.write_text(f"v1:{value}\n")
    monkeypatch.setenv(f"{SOURCE}_FILE", str(source))
    monkeypatch.setenv(SOURCE, f"v1:{value}")
    with pytest.raises(env.InvalidSettingError, match="not both") as raised:
        env.versioned_keys(SOURCE)
    assert value not in str(raised.value)


def test_versioned_keys_missing_fail_closed(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(env.MissingSettingError):
        env.versioned_keys(SOURCE)
    monkeypatch.setenv(f"{SOURCE}_FILE", str(source))  # named, but no such file
    with pytest.raises(env.InvalidSettingError, match="cannot be read"):
        env.versioned_keys(SOURCE)
