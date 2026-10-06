import os
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit


class MissingSettingError(RuntimeError):
    pass


class InvalidSettingError(RuntimeError):
    pass


TLS_OPTIONS = ("sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl")
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
STRICT_SSL_MODES = ("verify-ca", "verify-full")


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
