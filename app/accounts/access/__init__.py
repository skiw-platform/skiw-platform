"""Roles as agency data (slice spec docs/specs/2026-11-20-m4-rest-roles-jobs-design.md, M4-rest).
`catalogue` is the fixed permission catalogue (Decision 4); `tables` holds the models of
`permission`, `role` and `role_permission` (Decision 1); `seed` gives each agency its Owner role
(Decision 5); `grants` evaluates a user's grants for one code from the stored ticks (Decisions 7,
8). Nothing calls `grants` yet: the wrapper's role step is M4r-3."""
