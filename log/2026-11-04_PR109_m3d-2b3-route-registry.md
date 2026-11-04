# PR 109 — feat(accounts): M3d-2b3 route registry (AUTH-02), wrapper registration checks, logged-in CSRF gate

- **Merged:** 2026-11-04 (12:15:51 UTC) · **Merge commit:** d9c104df00183e33e31095ca4987a3ea30310238 · **Branch:** feat/m3d-2b3-route-registry
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-109.receipt on agent-logs (log-branch commit a1c4a62, receipt time 2026-11-04T12:14:51Z, before merge; reviewed head cbd70dbc9dd66bfb73af497362de70395c73af45, review-file hash 3f461204c1e89c517cd522eac0f573626bfaca55, review commit 98f90eb)
- **Merge evidence:** `gh pr view 109` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head cbd70db
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 2); CI checks, security, image, host pass at cbd70db
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3d · **Milestone:** M3, M3d-2b3 (part 3 of 3; completes M3d)

## What changed
- `app/tests/test_route_registry.py` (new): every `config.urls` route is an `authorized_action` handler (`skiw_action`) or in the reviewed `PUBLIC_ROUTES` (`healthz`, `readyz`, `asset`, `shell`, each with a reason). These fail: neither, wrapped and listed, a stale entry, and (R1) a route name used by more than one route. `wrapper.SAFE_METHODS` is pinned to `config.routes.SAFE_METHODS`.
- `authorized_action` refuses an empty `permission` and an async handler (`ImproperlyConfigured`) and a session that isn't the accounts store (`TypeError`); `accounts/tests/test_action_wrapper.py` (4, no DB).
- CSRF gate: `tests.csrf_urls` gains a wrapped `action-probe`; the gate's `Pair` records `wrapped` (no session → the wrapper's 401 past CSRF). `test_csrf_gate_live.py` (10) signs in through `login()` server-side: the rotated token reaches the handler; none, wrong, cross-site and the pre-login token are refused.
- `docs/runbooks/local-dev.md` names the registry rule; DECISIONS "M3d-2b3". +289 −12 code/test, +30 docs. 12 mutants killed.

## Why
AUTH-02 (no middleware gate), AUTH-01, spec T6, UNI-19; plan M3 §3 M3d, §4 M3d row, Risk 4; DECISIONS M2d deviation (b), M3d-2b2; PR 108 R1 follow-ups.

## Review rounds
- R1: Changes requested (head c97ee92). P2 #1: an unwrapped route reusing a public route's name (`healthz`) passed the registry, because `PUBLIC_ROUTES` is keyed on the name and Django lets patterns share a name. The reviewer signed off the four `PUBLIC_ROUTES` entries and re-ran `make test-live` (469) and pytest unit (1557).
- Fix cbd70db: any name used by more than one route fails; two tests (unwrapped `healthz` reuse; two wrapped routes sharing a name).
- R2: Approved (head cbd70db), no findings. The reviewer re-ran the R1 probe (now flagged), a threshold mutant (`n > 99`, both new tests fail), and pytest unit (1559).

## Deferred conditions
- None.

## Decisions worth keeping
- A signed-in route is authorized only through `authorized_action`; the route registry is the AUTH-02 proof, and `PUBLIC_ROUTES` is a reviewed list (reviewer sign-off per entry), keyed on unique route names.
- `authorized_action` wraps sync handlers only, needs a non-empty `permission`, and only works on the accounts (MAC-checked) session store.
- The CSRF gate runs its mutating cases both without a session and signed in through `login()`; the pre-login token is refused after login.

## Follow-ups
- M3e: the login steps become the first public mutating `PUBLIC_ROUTES` entries (reviewer sign-off); the real login response sets the rotated CSRF cookie; the pending-row note from PR 107.
- M4-rest: the disable flow calls `revoke_user()` (DECISIONS M3d-2b2); keep the seen refresh after the role step (PR 108 note).
- Reviewer notes, no action: a hand-set `skiw_action` passes the registry (a WeakSet of views made by `authorized_action` would close it); the live accept test also allows 400/422.
- Superseded local branch `feat/m3d-2b3-action-registry` (ee8fed0, never pushed): delete only with the owner's yes.
- Earlier, still open: spec §4.1 / D6 gap for `session_revocation` (plan §9 item 2); `guard.auth_lookup_login` must name `public.citext` (M3e); `login()` is sync only; the clock rule assumes one host; PR 88 optional P3; PR 78, 77, 81 items → M3e; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3d-2b3" entry.

## Appendix — final review round
## Round 2 — 2026-11-04 · scope: delta since R1 (c97ee92 → cbd70db)
- **Code review:**
  - **Base:** merge base f177787cc4c04e5d871101e7ab3c34f4896711d0 (origin/main, unchanged).
  - **Head:** cbd70dbc9dd66bfb73af497362de70395c73af45, two commits (`c97ee92`, `cbd70db`). The delta
    is 2 files, +26 −10: `app/tests/test_route_registry.py` and `docs/DECISIONS.md`. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`. No database was needed: the delta
    touches one non-live test file.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 109` (builder), then merge. That completes M3d-2b. Then M3e.

### R1 P2 #1 (a duplicate route name passes the registry): resolved
- `unauthorized()` counts the names in the walk and reports any name used by more than one route
  (`"<name>: name used by N routes"`). Unnamed routes are left out of the count; they are already
  flagged, because `""` is never in `PUBLIC_ROUTES`.
- **Two new tests:**
  - an unwrapped route named `healthz`, which is my R1 case;
  - two wrapped routes sharing one name.
- The "wrapped and listed" test now lists its own route name, rather than reusing `shell`. That keeps
  it about the one problem it tests now that a reused name fails.
- **Reviewer probe:** I re-ran my R1 probe (an unwrapped POST route named `healthz`, in a temporary
  `app/tests/test_zz_review_probe.py`, deleted afterwards). It now returns
  `['healthz: name used by 2 routes']`.
- **Reviewer mutant:** with the duplicate threshold raised to `n > 99`, both new tests fail (2 failed, 7
  passed). The file was reverted.
- DECISIONS records the rule, the test count (9) and the extra mutant.
- **Status:** closed.

### Checks
- `make -o check-node test`: pytest gave 1559 passed. That is R1's 1557 plus the two new tests. pnpm
  isn't installed here; this PR has no web change, and CI runs the web tests.
- `make test-live` was not re-run: the delta has no live test and no app code. R1 ran it at c97ee92
  (469 passed), and CI `checks` passes at cbd70db.
- The worktree is clean.

### Findings
None open.

### Notes
R1's two notes still stand, with no action asked: the hand-set `skiw_action`, and the live success test
also accepting 400 and 422.

### Follow-ups
- **M3e:** the login steps become the first public mutating `PUBLIC_ROUTES` entries, with reviewer
  sign-off; the pending-row note from PR 107.
- **M4-rest:** the disable flow calls `revoke_user()` (DECISIONS M3d-2b2).

