# PR 137 — feat(accounts): M3h-2a step-up evidence MAC, factor_id required, Semgrep rule

- **Merged:** 2026-11-11 (00:40:12 UTC) · **Merge commit:** f1d5b2d6537a332b718288200a22ec4c1a5c625e · **Branch:** feat/m3h-2a-stepup-mac (final head 051f66dd3612b0a50c7a40506a6f4083cd30a907)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-137.receipt`, 2026-11-11T00:37:25Z, review-file hash 03169800, review commit 42f2acc) precedes the merge by about 2 minutes 47 seconds.
- **Approval receipt:** `reviews/PR-137.receipt` on agent-logs (written by `approved 137` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 137` state MERGED, mergedAt 2026-11-11T00:40:12Z, merge commit f1d5b2d; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder on an Opus 5.5 deep-tier design (reviewed by Claude Opus 5.5) · **Final verdict:** Approved (Round 1, no revision round)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3h-2a (second of seven M3h PRs)

## What changed
`accounts/auth/stepup.py` builds and verifies the step-up `evidence_mac` (4-byte `tenant_source_key` version, then HMAC-SHA-256 over `skiw-stepup-v1` and the seven other columns, each length-prefixed; newest key signs, any listed version verifies). Migration `accounts.0013` adds CHECK `auth_stepup_factor_named` (`factor_id IS NOT NULL`). Semgrep rule `auth-stepup-insert-stepup-only` (with fixture) confines the `AuthStepup` model and SQL writes to `stepup.py`, migrations and the accounts tests. 15 unit tests; the table test for a nullable factor became "every step-up names a factor". DECISIONS "M3h-2a" and a plan amendment. +356/−14 over 9 files. No route, setting or dependency; nothing calls `stepup.py` yet except its tests.

## Why
Spec §4.1 `auth_stepup` and plan M3h: step-up evidence must be unforgeable by SQL (T10, D25). The first half of M3h-2; it also takes PR 136 R2 P3 #2 (`factor_id` required). M3h-2 was split in two because the Opus design measured it at ≈ 790 lines against the ≈ 450 split point (builder's call under the size rule, recorded in DECISIONS, the plan and the PR body).

## Review rounds
- R1: Approved on 051f66dd, nothing required. Two P3s deferred to M3h-2b, plus the carried PR 136 R2 P3 #1.

## Deferred conditions
- **PR 136 R2 P3 #1 → M3h-2b:** `record` takes only the session user's own `totp` row (refuses a recovery row, a passkey, another user's factor, a missing id), with tests.
- **P3 #1 (optional) → M3h-2b:** `_message` raises on a timezone-naive `verified_at`, as `source_key._mac` does for `expire_date`, next to `record`.
- **P3 #2 (optional) → M3h-2b:** the Semgrep rule message says it covers reads; its SQL arm matches only write verbs, so a raw `SELECT … FROM auth_stepup` passes. Narrow the message, or add a read arm with care for M9's trigger SQL in outbox migrations.
- **Residual (2b):** the live tests include a stored-then-read signed row whose `verified_at` keeps its microseconds and instant. The age check uses the app clock on both sides [A].
- Standing: PR 135 P3 #2 (M3h-6 last-TOTP refusal); PR 134 R1 P3 wording; spec D20 P3 and the M3 row "AUTH-01..09"; owner Q4 (a) alert path before M17.

## Decisions worth keeping
- M3h-2 is two PRs (2a MAC; 2b `record`, `recent`, live tests); the M3h count is seven. Recorded in DECISIONS "M3h-2a" and the plan.
- `factor_id` is required by a CHECK, not `SET NOT NULL`: `AlterField(null=False)` is a contract operation with no rollback across it; an added CHECK is an expand step (UNI-15).
- `record(request, factor, purpose)` replaces the earlier design's `record(request, user, factor_id, purpose)`; M3h-3 must match it.
- Semgrep resolves imports, so the `AuthStepup` spellings overlap; deleting one spelling in the rule does not fail its fixture, deleting a group does.
- `factor.change` is not in the spec's purpose list; plan §9 item 16 takes it to the next spec revision.

## Follow-ups
- Next: M3h-2b (deep tier): the Opus files are in the builder's scratchpad `m3h2b/` (full `stepup.py`, 22 live tests, the `CALLS` tests); take the three deferred items above. Then M3h-3 … M3h-6, M3i, M3g.
- Progress page: M3h-2a done; republish.

## Appendix — final review round

## Round 1 — 2026-11-10 · scope: slice (M3h-2a; MAC functions, one CHECK migration, one Semgrep rule; no caller yet)
- **Code review:** base (merge base) 3f72512368d11c18976d6731526eace8af38b5cd (= `origin/main`, PR 136 merged) · head 051f66dd3612b0a50c7a40506a6f4083cd30a907 · head re-checked at end: yes (host head unchanged, PR open, CI finished; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (unchanged): §4.1 `auth_stepup` ("HMAC under the app-held `tenant_source_key` over all other columns"; "inserted only by `accounts.auth` (lint)"), AUTH-09. Plan §1 and §3 M3h; DECISIONS "M3h-1" (the fixed layout). Carry-overs checked: PR 136 R2 P3 #1 and #2.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. M3h-2b (`record`, `recent`, live forgery tests) is auth work and stays deep.

### Carry-overs (re-inspected, not taken from the PR body)
- **PR 136 R2 P3 #2 (`factor_id` nullable with no use): resolved.**
  - `accounts.0013` adds CHECK `auth_stepup_factor_named`, and `test_every_step_up_names_the_factor_that_proved_it` shows it refusing as `skiw_app`.
  - `_message` has no empty case: `_factor` raises before signing, and `test_a_row_without_a_factor_is_never_signed` covers that.
  - **The CHECK instead of `SET NOT NULL`: confirmed.** It has the same effect on writes. It is an added constraint (expand, UNI-15), the same way `0010` was done. Down to 0012 and up again is clean.
- **PR 136 R2 P3 #1 (`record` refuses a recovery factor): carried to M3h-2b, accepted.** `record` doesn't exist yet, so nothing can name a recovery row.
  - DECISIONS "M3h-2a" designs it more tightly than I asked: `record` re-reads the factor and requires one of the **session user's own** rows of kind `totp`.
  - That also closes a gap I had not named: the composite FK checks only the agency, so another user's factor in the same agency would pass it.
  - Still open, for 2b.

### The split (2a / 2b)
Accepted. The design measured about 790 lines (tests about 470) against the 450 split point. The standing size rule applies, as it did for the M3h split, and each half is safe on its own:
- 2a has no writer;
- 2b adds the first writer and its forgery tests together.

It's recorded in DECISIONS and in the plan (amendment note, §1 row, §3 list). No owner decision is needed: it applies a rule the owner already accepted rather than changing scope.

### Findings

### [P3] Two small hardenings
1. **A naive `verified_at` is MACed silently as local time.** `_message` calls `astimezone(UTC)` with no check. `source_key._mac` refuses a naive datetime (`"expire_date must be timezone-aware"`). With `USE_TZ` on and `record` setting `timezone.now()` in 2b, no naive value should reach `_message`. Still, if one did, the row would be signed for a different instant than Postgres stores, depending on the process's time zone, and would then never verify. Mirror the session check: raise on `utcoffset() is None`, with a one-line test.
2. **The Semgrep rule's message promises more than its SQL arm checks.** The message says "Only accounts.auth.stepup writes or reads auth_stepup … a read elsewhere would trust a row recent() would refuse". The ORM arms do catch reads: my probe flagged `S.objects.filter(...)`, `.update(...)` and `.raw(...)`. But the SQL arm matches only write verbs, so a raw `SELECT … FROM auth_stepup` in app code passes. Either add a read arm (with care: M9's trigger SQL will read the table from outbox migrations) or say "ORM access and SQL writes" in the message.
- Owner: builder · Disposition: deferred to M3h-2b (optional; #1 belongs next to `record`) · Status: open

No prompt-injection text found in the PR body, commit message, code, tests or docs.

**Design calls [A], reviewer answers:**
1. **The MAC layout:** confirmed. It matches DECISIONS "M3h-1" exactly, which `test_evidence_is_the_newest_version_then_the_mac_of_every_other_column` checks against a hand-built message.
   - Every column is covered on its own (parametrised).
   - The same instant in another zone verifies.
   - The newest version signs (`require_key()` is documented newest-first, `source_key.py:26-28`).
   - An older listed version still verifies; a removed one, or one that is listed but isn't the signer, does not.
   - An unlisted version doesn't fall back to the newest key. The builder found that surviving mutant and killed it.
2. **The label `skiw-stepup-v1`:** confirmed. The test proves it is not a prefix of, and has no prefix among, the session, recovery and throttle labels. That matters because the throttle HMACs have no length prefix.
3. **`PURPOSES = {factor.change}` as a closed list, with consumers adding theirs:** confirmed. `factor.change` isn't in the spec's example list, and plan §9 item 16 takes it to the next spec revision.
4. **`compare_digest` mutant "not killable":** accepted. It's a timing property, and reading confirms it's there.

**Code read (beyond the self-check):**
- `_genuine` slices the version off a value the CHECK keeps at exactly 36 bytes. A shorter value can't be stored, and in memory `compare_digest` would just return False.
- No key, MAC or message is logged, or put in an exception. The `ValueError` text carries no data.
- **Semgrep probe** (a scratch file, run with the PR's rule, then deleted): an f-string INSERT, a concatenated INSERT, an UPDATE, ORM `.update()` and `.raw()` were all flagged.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy strict, 232 files | — |
| UNI-02 | yes | pass | pass | no new value | — |
| UNI-03 | yes (DB CHECK) | pass | pass | NULL factor refused live | — |
| UNI-04 | yes | pass | pass | Semgrep 21 rules / 0 findings; rule tests 21/21; probe above | P3 #2 (message) |
| UNI-05 | yes | pass | pass, caller pending | used by tests until 2b, as M3h-1's table was | — |
| UNI-07 (hard) | yes | pass | pass | CI `security` green; derived test values | — |
| UNI-09 | yes | pass | pass | nothing logged; no secret in exceptions | — |
| UNI-13 | yes | pass | pass | CI green on 051f66dd; local runs below | — |
| UNI-15 | yes | pass | pass | 0013 down to 0012 and up; `makemigrations --check` no changes | — |
| UNI-16 | n/a, no env var or host step | n/a | n/a accepted | runbook already covers step-up under `tenant_source_key` | — |
| AUTH-09 | yes (MAC half) | pass | pass | unit tests per column, version, rotation, removal | — |
| TEN-02/03 | yes | pass | pass | no grant change; live tests as `skiw_app` | — |
| TEN-04..08 | yes (unchanged) | pass | pass | `check_tenancy_schema` ok | — |
| UNI-17/18/19, AUTH-01/02/05/07, TEN-09..12 | n/a, no route, query or revocation | n/a | n/a accepted | — | — |
| FE, EVT, MON, REC, FILE | n/a | n/a | n/a | — | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-137-051f66dd` at 051f66dd | created, reviewed, ignored output cleaned, disposable DB removed (`down -v`), worktree removed without `--force` |
| `git diff --check 3f72512...051f66d` | clean |
| `make install lint typecheck test test-live` (Compose DB on port 5436) | pass; Semgrep rule tests 21/21; mypy 232 files; test 1717 + web 4; test-live 755 (all match the PR) |
| `pytest` on `test_auth_stepup.py` and `-m live` on `test_stepup_table_live.py`, 3 runs | 15/15 and 31/31 each run |
| `migrate accounts 0012`, then `migrate`; `check_tenancy_schema`; `makemigrations --check` | 0013 unapplied and reapplied OK; schema check ok; no changes |
| Semgrep probe of the new rule (scratch file, deleted) | f-string, concatenation, UPDATE, ORM `update`/`raw` all flagged |
| `source_key.require_key()` ordering | "newest first" (`source_key.py:26-28`); `seal` and `throttle` use `[0]` the same way |
| CI on head 051f66dd | checks, security, image, host: pass; publish/deploy-staging skipped |
| Host head SHA at end | 051f66dd3612b0a50c7a40506a6f4083cd30a907, unchanged |
| Not run | builder's mutants (list reviewed); `host-test`, `secrets-test`, `e2e` (CI covers the first two; no UI) |

### Residual risks and test gaps
- No live test signs a row, stores it and verifies it after a Postgres round trip yet. That needs `record`, so it belongs to 2b's live forgery tests. Those should include a stored-then-read row whose `verified_at` keeps its microseconds and its instant.
- The age check in 2b uses the app clock on both sides ([A] in DECISIONS). Acceptable while the DB and app share the host clock.

### Required before merge
- None.

### Deferred conditions
- PR 136 R2 P3 #1: carried to M3h-2b (`record` takes only the session user's own `totp` row, with tests for a recovery row and another user's factor).
- P3 #1 and #2 above: M3h-2b (optional).

### Optional improvements
- None beyond the P3s.
