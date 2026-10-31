# Fixture for `semgrep --test semgrep/` (rules config-accounts-*). `--test` ignores `paths`, so
# every rule sees every line here; the urls.py / asgi.py scoping is checked by a planted file.
# Each import line is a case for the rules, so unused and unsorted imports are the point here.
# ruff: noqa: F401, I001
import importlib

from django.urls import include
from django.utils.module_loading import import_string

# ruleid: config-accounts-imports
import accounts

# ruleid: config-accounts-imports
import accounts.session

# ruleid: config-accounts-imports
import accounts.models

# ruleid: config-accounts-imports
from accounts import session

# ruleid: config-accounts-imports
from accounts import models

# ruleid: config-accounts-imports
from accounts.session import SessionStore

# ruleid: config-accounts-imports
from accounts.models import Session

# ruleid: config-accounts-imports
from accounts.auth import login

# ruleid: config-accounts-views-in-urls-only
import accounts.views

# ruleid: config-accounts-views-in-urls-only
from accounts import views

# ruleid: config-accounts-views-in-urls-only
from accounts.views import login_view

# ruleid: config-accounts-source-key-in-asgi-only
from accounts.source_key import require_key

# ruleid: config-accounts-source-key-in-asgi-only
import accounts.source_key

# ruleid: config-accounts-source-key-in-asgi-only
from accounts import source_key

# ok: config-accounts-imports
from config.routes import route

# ok: config-accounts-imports
from . import env

# ok: config-accounts-imports
SESSION_ENGINE = "accounts.session"

# ruleid: config-accounts-imports
importlib.import_module("accounts.session")
# ruleid: config-accounts-imports
import_string("accounts.session.SessionStore")
# ruleid: config-accounts-imports
__import__("accounts.models")
# ruleid: config-accounts-imports
include("accounts.urls")
# ok: config-accounts-imports
include("other.urls")
