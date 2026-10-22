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

INSTALLED_APPS = ["procrastinate.contrib.django", "config", "health", "shell", "jobs"]
MIDDLEWARE: list[str] = []

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_TZ = True
