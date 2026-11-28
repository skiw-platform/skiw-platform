"""Roles as agency data (slice spec docs/specs/2026-11-20-m4-rest-roles-jobs-design.md, M4-rest).
`catalogue` is the fixed permission catalogue (Decision 4); `tables` holds the models of
`permission`, `role` and `role_permission` (Decision 1); `seed` gives each agency its Owner role
(Decision 5); `grants` evaluates a user's grants for one code from the stored ticks (Decisions 7,
8), read by the wrapper's role step (accounts.auth.wrapper) and nowhere else; `scope` holds
`ScopedModel`, the base of every model read through `scoped()` (Decisions 9, 10; `scoped()` itself
lands in M4r-4b)."""
