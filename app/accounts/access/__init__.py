"""Roles as agency data (slice spec docs/specs/2026-11-20-m4-rest-roles-jobs-design.md, M4-rest).
`catalogue` is the fixed permission catalogue (Decision 4); `tables` holds the models of
`permission`, `role` and `role_permission` (Decision 1). Nothing grants or evaluates a permission
from them yet: the wrapper's role step is M4r-2."""
