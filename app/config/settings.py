from pathlib import Path

from . import env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env.require("DJANGO_SECRET_KEY")
DEBUG = env.flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env.csv("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = ["procrastinate.contrib.django", "health", "shell", "jobs"]
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

DATABASES = {
    "default": env.database_from_url(
        env.require("DATABASE_URL"), require_tls=env.flag("DJANGO_REQUIRE_DB_TLS")
    )
}

# skiw_app has no DELETE on procrastinate_jobs (spec §4.1); "never" is also the library default.
PROCRASTINATE_WORKER_DEFAULTS = {"delete_jobs": "never"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_TZ = True
