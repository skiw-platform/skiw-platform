import os
from typing import Any
from urllib.parse import unquote, urlsplit


class MissingSettingError(RuntimeError):
    pass


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


def database_from_url(url: str) -> dict[str, Any]:
    parts = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql"} or not parts.path.strip("/"):
        raise MissingSettingError("DATABASE_URL must be postgres://user:password@host:port/name")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or 5432),
    }
