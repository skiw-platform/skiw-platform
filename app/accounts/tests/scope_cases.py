"""The scope harness's cases for accounts (accounts/tests/scope_harness.py)."""

from functools import partial

from accounts.tests.scope_harness import ScopeCase
from accounts.tests.scope_probe import PROBES, insert

CASES = [ScopeCase(model, partial(insert, table=model._meta.db_table)) for model in PROBES]
