import base64
import binascii
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


class MissingSettingError(RuntimeError):
    pass


class InvalidSettingError(RuntimeError):
    pass


TLS_OPTIONS = ("sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl")
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
STRICT_SSL_MODES = ("verify-ca", "verify-full")
# At most six digits, as accounts.source_key.SEALED reads them back (plan M3 (c)).
KEY_LINE = re.compile(r"v([1-9][0-9]{0,5}):([A-Za-z0-9+/]+={0,2})")
WHOLE_NUMBER = re.compile(r"[0-9]{1,6}")  # ASCII digits only: int() also takes "+1", "1_0", " 1"
MIN_KEY_BYTES = 32  # bootstrap-secrets mints 32 random bytes per key version (spec §8.4 H4)
# One canonical lowercase uuid: no list, braces, urn: prefix or upper case (PROJECT §9 gate).
AGENCY_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
AGENCY_NAME_MAX = 200  # tenancy.Agency.name max_length
# A lowercase DNS hostname (plan Q8 (a)): letters, digits and inner hyphens per label, no port,
# scheme, trailing dot or IP literal (the last label must hold a letter).
RP_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
RP_ID = re.compile(rf"(?:{RP_LABEL}\.)*(?=[a-z0-9-]*[a-z])" + RP_LABEL)
LOCAL_ORIGIN = re.compile(r"https?://localhost(?::([1-9][0-9]{0,4}))?")


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


def bounded_int(name: str, low: int, high: int) -> int:
    """A required whole number in [low, high]; the error names the variable, never the value."""
    raw = os.environ.get(name, "")
    if WHOLE_NUMBER.fullmatch(raw) is None or not low <= int(raw) <= high:
        raise ImproperlyConfigured(f"{name} must be a whole number from {low} to {high}")
    return int(raw)


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


def parse_key_lines(
    name: str, text: str, max_version: int = 999_999
) -> list[tuple[int, str, bytes]]:
    """`v<n>:<base64>` lines (spec §8.4 H4) as (n, base64, bytes), newest version first. Fails
    closed on any bad line; errors name the line, never its content."""
    versions: dict[int, tuple[str, bytes]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        match = KEY_LINE.fullmatch(line)
        if match is None:
            raise InvalidSettingError(f"{name}: line {number} is not v<n>:<base64>")
        if int(match[1]) > max_version:
            raise InvalidSettingError(f"{name}: line {number} has a version above {max_version}")
        try:
            raw = base64.b64decode(match[2], validate=True)
        except binascii.Error as exc:
            raise InvalidSettingError(f"{name}: line {number} is not valid base64") from exc
        if len(raw) < MIN_KEY_BYTES or int(match[1]) in versions:
            raise InvalidSettingError(f"{name}: line {number} is too short or a repeated version")
        versions[int(match[1])] = (match[2], raw)
    if not versions:
        raise InvalidSettingError(f"{name}: holds no key version")
    return [(n, *versions[n]) for n in sorted(versions, reverse=True)]


def key_versions(name: str) -> list[str]:
    """The base64 text of each version in secret file `name`, newest first."""
    return [text for _, text, _ in parse_key_lines(name, secret_file(name))]


def versioned_keys(name: str, max_version: int = 999_999) -> list[tuple[int, bytes]]:
    """(version, key bytes) of app key `name`, newest first: from the secret file named by
    `<name>_FILE` on hosts, else from env var `name` (local and CI), in the same line format.
    `max_version` is lower where a key's version is stored in fewer digits or bytes."""
    file_name = f"{name}_FILE"
    if file_name in os.environ:
        if name in os.environ:
            raise InvalidSettingError(f"set {name} or {file_name}, not both")
        text, source = secret_file(file_name), file_name
    elif os.environ.get(name):
        text, source = os.environ[name], name
    else:
        raise MissingSettingError(f"{name} (or {file_name} on hosts) is required and not set")
    return [(version, raw) for version, _, raw in parse_key_lines(source, text, max_version)]


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


def deployment_agency() -> tuple[uuid.UUID, str]:
    """The one deployment agency (plan M4c-5, Q2 (a)): SKIW_DEPLOYMENT_AGENCY_ID, exactly one
    uuid while PROJECT §9's second-agency gate is locked, and SKIW_DEPLOYMENT_AGENCY_NAME."""
    raw = os.environ.get("SKIW_DEPLOYMENT_AGENCY_ID", "")
    if AGENCY_ID.fullmatch(raw) is None:
        raise ImproperlyConfigured(
            "SKIW_DEPLOYMENT_AGENCY_ID must be exactly one lowercase uuid (a second agency is"
            " gated, PROJECT §9)"
        )
    name = os.environ.get("SKIW_DEPLOYMENT_AGENCY_NAME", "")
    if not 0 < len(name) <= AGENCY_NAME_MAX or name != name.strip() or not name.isprintable():
        raise ImproperlyConfigured(
            f"SKIW_DEPLOYMENT_AGENCY_NAME must be 1 to {AGENCY_NAME_MAX} printable characters,"
            " with no leading or trailing space"
        )
    return uuid.UUID(raw), name


@dataclass(frozen=True)
class WebAuthnSettings:
    rp_id: str
    origin: str


def webauthn() -> WebAuthnSettings:
    """SKIW_WEBAUTHN_RP_ID and SKIW_WEBAUTHN_ORIGIN (plan M3g, Q8 (a)). The origin is checked
    exactly. Unset, it is https://<rp id> (hosts set only the RP ID); set, it must be that, and
    only an RP ID of localhost may use http or a port (local dev and e2e). The errors name the
    variable, never the value."""
    rp_id = os.environ.get("SKIW_WEBAUTHN_RP_ID", "")
    if len(rp_id) > 253 or RP_ID.fullmatch(rp_id) is None:
        raise ImproperlyConfigured("SKIW_WEBAUTHN_RP_ID must be a lowercase DNS hostname")
    origin = os.environ.get("SKIW_WEBAUTHN_ORIGIN", f"https://{rp_id}")
    local = LOCAL_ORIGIN.fullmatch(origin) if rp_id == "localhost" else None
    port = local.group(1) if local else None
    if origin != f"https://{rp_id}" and (local is None or (port and int(port) > 65_535)):
        raise ImproperlyConfigured(
            "SKIW_WEBAUTHN_ORIGIN must be https:// and SKIW_WEBAUTHN_RP_ID (http and a port only"
            " for localhost)"
        )
    return WebAuthnSettings(rp_id, origin)
