import base64
import binascii
import os
import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit


class MissingSettingError(RuntimeError):
    pass


class InvalidSettingError(RuntimeError):
    pass


TLS_OPTIONS = ("sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl")
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
STRICT_SSL_MODES = ("verify-ca", "verify-full")
KEY_LINE = re.compile(r"v([1-9][0-9]*):([A-Za-z0-9+/]+={0,2})")
MIN_KEY_BYTES = 32  # bootstrap-secrets mints 32 random bytes per key version (spec §8.4 H4)


def require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise MissingSettingError(f"{name} is required and not set")
    return value


def flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def csv(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def database_from_url(url: str, require_tls: bool = False) -> dict[str, Any]:
    parts = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql"} or not parts.path.strip("/"):
        raise MissingSettingError("DATABASE_URL must be postgres://user:password@host:port/name")
    options: dict[str, str] = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key not in TLS_OPTIONS:
            raise InvalidSettingError(f"DATABASE_URL option {key!r} is not supported")
        if key in options:
            raise InvalidSettingError(f"DATABASE_URL option {key!r} is given twice")
        options[key] = value
    mode = options.get("sslmode")
    if mode is not None and mode not in SSL_MODES:
        raise InvalidSettingError(f"DATABASE_URL sslmode {mode!r} is not a valid libpq mode")
    if require_tls and mode not in STRICT_SSL_MODES:
        raise InvalidSettingError(
            "DJANGO_REQUIRE_DB_TLS is set: DATABASE_URL needs sslmode=verify-full or verify-ca"
        )
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or 5432),
        "OPTIONS": options,
    }


def secret_file(name: str) -> str:
    """The text of the secret file named by env var `name`; errors never carry the content."""
    try:
        with open(os.environ[name], encoding="ascii", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidSettingError(f"{name}: the secret file cannot be read") from exc


def key_versions(name: str) -> list[str]:
    """`v<n>:<base64>` lines (spec §8.4 H4), newest version first. Fails closed on any bad line."""
    versions: dict[int, str] = {}
    for number, line in enumerate(secret_file(name).splitlines(), start=1):
        match = KEY_LINE.fullmatch(line)
        if match is None:
            raise InvalidSettingError(f"{name}: line {number} is not v<n>:<base64>")
        try:
            raw = base64.b64decode(match[2], validate=True)
        except binascii.Error as exc:
            raise InvalidSettingError(f"{name}: line {number} is not valid base64") from exc
        if len(raw) < MIN_KEY_BYTES or int(match[1]) in versions:
            raise InvalidSettingError(f"{name}: line {number} is too short or a repeated version")
        versions[int(match[1])] = match[2]
    if not versions:
        raise InvalidSettingError(f"{name}: the secret file holds no key version")
    return [versions[version] for version in sorted(versions, reverse=True)]


def secret_key() -> tuple[str, list[str]]:
    """SECRET_KEY and SECRET_KEY_FALLBACKS: from DJANGO_SECRET_KEY_FILE on hosts, else the env."""
    if "DJANGO_SECRET_KEY_FILE" not in os.environ:
        return require("DJANGO_SECRET_KEY"), []
    if "DJANGO_SECRET_KEY" in os.environ:
        raise InvalidSettingError("set DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE, not both")
    newest, *older = key_versions("DJANGO_SECRET_KEY_FILE")
    return newest, older


def database(require_tls: bool = False) -> dict[str, Any]:
    """DATABASE_URL, with the password from DATABASE_PASSWORD_FILE when that is set (hosts)."""
    config = database_from_url(require("DATABASE_URL"), require_tls=require_tls)
    if "DATABASE_PASSWORD_FILE" in os.environ:
        if config["PASSWORD"]:
            raise InvalidSettingError("DATABASE_URL carries a password and DATABASE_PASSWORD_FILE")
        password = secret_file("DATABASE_PASSWORD_FILE").removesuffix("\n")
        if not password or "\n" in password or "\r" in password:
            raise InvalidSettingError("DATABASE_PASSWORD_FILE must hold exactly one non-empty line")
        config["PASSWORD"] = password
    return config
