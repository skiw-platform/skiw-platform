import os
from pathlib import Path

from . import env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY, SECRET_KEY_FALLBACKS = env.secret_key()
DEBUG = env.flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env.csv("DJANGO_ALLOWED_HOSTS")

# Hosts only (spec §8.4 H1, UNI-17): Caddy overwrites X-Forwarded-Proto on every request, so
# Django may trust it there. Unset elsewhere, so a client-sent header never makes a request secure.
if env.flag("DJANGO_BEHIND_CADDY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Not django.contrib.sessions: its 0001_initial would create a second django_session table;
# accounts owns that table (spec §4.1, plan M2b).
INSTALLED_APPS = ["procrastinate.contrib.django", "config", "health", "shell", "jobs", "accounts"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "shell.csp.ContentSecurityPolicyMiddleware",
]

# Same value as Caddy (infra/host/caddy/edge.caddy; owner Q1 (a) 2026-10-27): one year, no
# includeSubDomains or preload. Caddy owns the HTTP -> HTTPS redirect, so no SSL redirect here.
SECURE_HSTS_SECONDS = 31_536_000
SECURE_SSL_REDIRECT = False
X_FRAME_OPTIONS = "DENY"

# Sessions (spec D6): DB rows keyed by SHA-256 of the cookie (accounts.session). The `__Host-`
# prefix needs Secure, Path=/ and no Domain.
SESSION_ENGINE = "accounts.session"
SESSION_COOKIE_NAME = "__Host-skiw_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None
SESSION_SAVE_EVERY_REQUEST = False
# Interim deployment-wide values until M5 moves them into `setting` (owner Q2 (a), spec §8.1
# session.absolute_h / session.idle_min). The absolute deadline is fixed when a session starts
# (accounts.session); the idle limit is enforced from M3. Bounds are builder values [A].
SKIW_SESSION_ABSOLUTE_H = env.bounded_int("SKIW_SESSION_ABSOLUTE_H", 1, 72)
SKIW_SESSION_IDLE_MIN = env.bounded_int("SKIW_SESSION_IDLE_MIN", 1, 1440)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WEB_DIST_DIR = BASE_DIR.parent / "web" / "dist"

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.database(require_tls=env.flag("DJANGO_REQUIRE_DB_TLS"))}

# skiw_app has no DELETE on procrastinate_jobs (spec §4.1); "never" is also the library default.
PROCRASTINATE_WORKER_DEFAULTS = {"delete_jobs": "never"}

# The files volume (spec §8.4 H5): only documents.storage uses this setting (Semgrep rule
# files-volume-only-storage). Empty means no files volume; storage then refuses every call.
FILES_ROOT = os.environ.get("SKIW_FILES_ROOT", "")
# Age after which the sweeper removes tmp/*.part and quarantine leftovers (spec §8.4 H5 [A]).
FILES_SWEEP_AGE_S = 3600

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_TZ = True
