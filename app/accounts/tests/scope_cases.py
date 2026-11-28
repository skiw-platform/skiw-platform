"""The scope harness's cases for accounts (accounts/tests/scope_harness.py)."""

from accounts.tests import scope_probe
from accounts.tests.scope_harness import ScopeCase

CASES = [ScopeCase(scope_probe.ScopeProbe, scope_probe.insert)]
