# Fixture for `semgrep --test semgrep/` (rule role-changes-commands-only).
# ruff: noqa: F401, F403, F811, I001, B009, E402 -- the import shapes are what is under test.
import importlib
from unittest import mock

# ruleid: role-changes-commands-only
import accounts.access.changes

# ruleid: role-changes-commands-only
import accounts.access.changes as ch

# ruleid: role-changes-commands-only
from accounts.access.changes import create_role

# ruleid: role-changes-commands-only
from accounts.access.changes import create_role, delete_role

# ruleid: role-changes-commands-only
from accounts.access.changes import *

# ruleid: role-changes-commands-only
from accounts.access import changes

# ruleid: role-changes-commands-only
from accounts.access import changes as moves

# ruleid: role-changes-commands-only
from accounts.access import grants, changes

# ruleid: role-changes-commands-only
from accounts.access import (
    grants,
    changes,
)

# The accounts.access re-export and the other relative forms.
# ruleid: role-changes-commands-only
from . import changes

# ruleid: role-changes-commands-only
from . import grants, changes

# ruleid: role-changes-commands-only
from .changes import create_role

# ruleid: role-changes-commands-only
from .access import changes

# ruleid: role-changes-commands-only
from .access.changes import create_role

# ruleid: role-changes-commands-only
from ..access import changes

# ruleid: role-changes-commands-only
from ..access.changes import create_role

# ruleid: role-changes-commands-only
from .. import changes

# ruleid: role-changes-commands-only
from ..changes import create_role

# Three dots, as a command in accounts/management/commands/ writes it.
# ruleid: role-changes-commands-only
from ...access import changes

# ruleid: role-changes-commands-only
from ...access import grants, changes

# ruleid: role-changes-commands-only
from ...access.changes import create_role

# ok: role-changes-commands-only
from ...access import grants

import accounts.access
from accounts import access
from accounts import access as acc


def reached(name):
    # ruleid: role-changes-commands-only
    accounts.access.changes.create_role("x", operator="y")
    # ruleid: role-changes-commands-only
    access.changes.create_role("x", operator="y")
    # ruleid: role-changes-commands-only
    acc.changes.create_role("x", operator="y")
    # ruleid: role-changes-commands-only
    getattr(accounts.access, "changes")
    # ruleid: role-changes-commands-only
    importlib.import_module("accounts.access.changes")
    # ruleid: role-changes-commands-only
    importlib.import_module(".changes", "accounts.access")
    # ruleid: role-changes-commands-only
    __import__("accounts.access.changes")
    # ruleid: role-changes-commands-only
    importlib.import_module("..changes", "accounts.access.sub")
    # ruleid: role-changes-commands-only
    importlib.import_module("...access.changes", __name__)
    # ruleid: role-changes-commands-only
    mock.patch("accounts.access.changes.create_role")
    # ruleid: role-changes-commands-only
    importlib.import_module(name + ".changes")


# ok: role-changes-commands-only
from accounts.access import grants

# ok: role-changes-commands-only
from accounts.access.changes_log import entry

# ok: role-changes-commands-only
from .access import grants


def quiet(name, relative):
    # ok: role-changes-commands-only
    accounts.access.grants.grants()
    # ok: role-changes-commands-only
    importlib.import_module("accounts.access.grants")
    # ok: role-changes-commands-only
    importlib.import_module("accounts.access.changes_log")
    # ok: role-changes-commands-only
    mock.patch("accounts.access.grants.changes")
    # Known misses (DECISIONS M4r-5a-i): a computed module name, an attribute on a package
    # imported relatively (Semgrep resolves absolute aliases only), and __import__ with a fromlist.
    # ok: role-changes-commands-only
    __import__("accounts.access", fromlist=["changes"])
    # ok: role-changes-commands-only
    importlib.import_module("accounts.access." + name)
    # ok: role-changes-commands-only
    relative.changes.create_role("x", operator="y")
