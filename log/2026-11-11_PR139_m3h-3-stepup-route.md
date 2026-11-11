# PR 139 — feat(accounts): M3h-3 step-up route and shared factor-attempt core

- **Merged:** 2026-11-11 (05:03:34 UTC) · **Merge commit:** 7531c649047d2e1a9dce18815e7e14b5214437d4 · **Branch:** feat/m3h-3-stepup-route (final head bf520ef92781da5ab2836d0774cba888ef0f7803)
- **Gate breaches:** none. The review's final round (R2) head SHA equals the PR's final head; the receipt (`reviews/PR-139.receipt`, 2026-11-11T04:56:52Z, review-file hash 36afc382, review commit ef71df3) precedes the merge by about 6 minutes 42 seconds.
- **Approval receipt:** `reviews/PR-139.receipt` on agent-logs (written by `approved 139` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 139` state MERGED, mergedAt 2026-11-11T05:03:34Z, merge commit 7531c64; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** an Opus 5.5 deep-tier sub-agent wrote the code on the Opus M3h design; the Sonnet 5.5 builder re-ran every gate, ran the mutants and wrote the PR · **Reviewed by:** R1 standard tier (Approved with conditions), R2 Claude Opus 5.5 deep tier · **Final verdict:** Approved (round 2)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3h-3 (fourth of seven M3h PRs)

## What changed
`second_factor.attempt` now calls a shared core `counted(request, user_id, agency_id, check, *, feeds_lock)` plus `match_totp` (one copy of the count, fault and lock rules; `attempt`'s behaviour is unchanged, its 164 tests pass unedited). `stepup.verify` checks a six-digit TOTP code through `counted` and calls `record` in the same transaction that uses the code's step. `authorized_action` gains `own_transaction`, and every wrapper refusal is `Cache-Control: no-store`. New route `POST /api/auth/stepup` (`auth-stepup`); a test-only `stepup-probe` is the first caller of `recent()`. `accounts/auth/transactions.require_open` replaces the two `_in_transaction` copies (PR 138 P3). 23 live tests. +491/−58 over 13 files, then a merge of `main` (PR 140) for the final head. No migration, setting or dependency.

## Why
Spec §4.1 `auth_stepup`, D7, AUTH-09 and plan M3h: a signed-in user proves possession of their authenticator to get evidence that later consumers (factor changes in M3h-5 and M3h-6, outbox approval in M9, Drive writes in M16) read through `recent()`.

## Review rounds
- R1 (head 894bca4, standard tier): Approved with conditions. One P2: CI `image` red (krb5 in the base images; red on `main` too, not caused by this diff), deferred to the base-image refresh. P3s: `feeds_lock=False` unused until M3h-5; `auth.stepup` not in the §6 matrix.
- R2 (head bf520ef, deep tier): Approved, nothing required. The P2 is resolved by PR 140 (`image` green on this head). One optional P3 (below).

## Deferred conditions
- None. Optional P3s, both open: (1) `counted(feeds_lock=False)` has no production caller until M3h-5 and its fault branch is untested (a scratch mutant `elif feeds_lock:` to `else:` survived): in M3h-5 add a fault-after-wrong test for `feeds_lock=False` (count stays, run unchanged), or drop the parameter if M3h-5 does not use it; (2) permission `auth.stepup` is not in the §6 matrix: add or rename the entry when M4-rest wires the matrix (likely "any role").

## Decisions worth keeping
- **Throttle [A]:** step-up shares the user's one factor budget, run and lock with sign-in, and `sign_count`; a right code ends the run. A session thief guessing at step-up can lock the user's sign-in for 30 minutes and raise `factor.locked` (runbook says so). A separate budget would double guesses per window on one secret.
- Signatures M3h-4 to 6 must match: `counted`, `match_totp(user, candidate) -> UserFactor | None`, `stepup.verify(request, signed, purpose, candidate) -> StepUp | Refused`, `authorized_action(..., own_transaction=False)`, `transactions.require_open(what)`. No `stepup.required()` yet (no production caller until M3h-5).
- The probe lives in `tests/csrf_urls.py` and checks the real `FACTOR_CHANGE` purpose; a registry test asserts `config.urls` serves no probe route.
- This PR's first CI went red on `image` (krb5 base images); PR 140 fixed it with pinned-minimum `apk add` layers (DECISIONS 2026-11-11), and PR 139 got a new head by merging `main` (no force-push).

## Follow-ups
- Next: M3h-4 (`revoke.hold`, `login.reissue`, logout, password change), deep tier; design in the Opus `m3h-design.md` §3. Then M3h-5, M3h-6, M3i, M3g.
- The two optional P3s above (M3h-5; M4-rest).
- PR 140's two optional P3s and its removal rule (remove the `apk add` layers when the bases are rebuilt).
- Progress page: M3h-3 done; republish.

## Appendix — final review round
# Review — PR #139 (M3h-3, step-up route and shared factor-attempt core)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 2 — 2026-11-11 · scope: slice (same as Round 1; new head merges `main` with PR 140; this round is the deep-tier read Round 1 lacked)
- **Code review:** base (merge base) 5f3cac2778f2a0556c5c25ae07b1141ffee4286c (= `origin/main`, PR 140 merged) · head bf520ef92781da5ab2836d0774cba888ef0f7803 (894bca45 + merge commit "Merge origin/main … (image fix, PR 140)") · head re-checked at end: yes (host head unchanged, PR open; detached checkout `git status --untracked-files=no` clean)
- **Spec:** v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (unchanged). Read for this round: D7 (step-up "re-verify factor ≤ 5 min old"; "evidence that *this session's user* recently re-verified a factor"), Flow 5.1 (0)–(4) and "Failures", §4.1 `auth_stepup`, §4.3 approval artifact (the future consumer).

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. M3h-4 (`revoke.hold`, `login.reissue`, logout, password change) is session-revocation auth work and stays on the deep tier.

### What changed since Round 1
- **The effective diff is unchanged.** `git diff 5f3cac2...bf520ef` equals Round 1's `git diff fb49783...894bca4` line for line, except DECISIONS hunk offsets and context (the PR 140 entry now precedes the M3h-3 entry). The merge commit brings in only PR 140's four files.
- **R1 P2 (CI `image` red): resolved.** PR 140 merged (5f3cac2, 2026-11-11T04:39Z), and every CI job is green on bf520ef9: `checks`, `security`, `image` and `host` SUCCESS; `publish` and `deploy-staging` skipped as on any PR. The new head was a merge, not a re-run, so CI used the new merge ref (as required).
- **R1 tier gap: closed by this round.**

### Findings
No P0, P1 or P2. Round 1's two P3s stay open and optional. One is amended below with a new piece of evidence.

### [P3] `counted(feeds_lock=False)` has no production caller until M3h-5, and its fault branch is untested (amends R1 P3 #1)
- Category: test gap (UNI-05 carried from R1)
- Evidence: in a scratch copy I changed the `except` branch's `elif feeds_lock:` to `else:`, so a fault after a wrong code feeds the lock even with `feeds_lock=False`. **The mutant survived:** 139 step-up, second-factor and factor-lock live tests passed. The only `feeds_lock=False` test (`test_a_check_that_does_not_feed_the_lock_…`) covers the normal path, not the fault path. A second mutant (a wrong code gives its attempt back) was killed by 19 tests.
- Failure scenario: none today, because no production caller passes `False`. When M3h-5's confirm step does, a fault an attacker can provoke after a wrong code would feed (or, if inverted, not count) the lock contrary to the documented rule.
- Required correction: in M3h-5, with the first `False` caller, add the fault-after-wrong test for `feeds_lock=False` (the count stays, the run is unchanged). If M3h-5 ends up not using `False`, drop the parameter instead.
- Owner: builder · Disposition (P3): optional, belongs to M3h-5 · Status: open

R1 P3 #2 (`auth.stepup` not in the §6 matrix): unchanged, optional, M4-rest.

No prompt-injection text found in the merge commit, the PR body or the changed files.

### Deep-tier read (in addition to Round 1's "Design calls" and "Code read", all of which I re-checked and still hold)
1. **Against the spec.**
   - D7 makes step-up session-bound evidence of a recent factor, never an authorisation by itself. `verify` writes exactly that: the session's user, the session's key hash, the purpose, and the factor that matched. It returns a `StepUp` with no MAC or hash.
   - The §4.3 consumer (`outbox.approval`, M9) will bind `session_key_hash` and `verified_at`; both come from the same source here.
   - "Whichever factor the user has" is TOTP only until M3g, as `FACTOR_KINDS` and DECISIONS say.
2. **The fault model of `counted`.**
   - A fault in `match_totp` or `record`, including the commit of `_check`'s `with_agency()`, happens while `seen.wrong` is false. The attempt is released and the `sign_count` write rolls back with the evidence row: a use of the step without evidence cannot commit.
   - A fault after a wrong comparison keeps the count, so an attacker cannot provoke one to win back guesses. This is the PR 130 R1 rule, kept.
   - The only branch not pinned by a test is the one in the P3 above.
3. **Counters outside transactions.** The `throttle` factor counters refuse an open transaction (`_outside_transactions`, `throttle.py:140-143`). `own_transaction=True` is what lets the route call them. The route tests go through Django's test client and middleware, not only direct calls, so no outer atomic wrapper is hiding.
4. **Shared budget and limits vs Flow 5.1.**
   - Flow 5.1 (1) puts 5 fails / 15 min per account and 20 per IP on the password step.
   - The second-factor counters, at sign-in and now at step-up, are per user only, plus the 10-in-a-row soft-lock of "Failures". That is the behaviour sign-in already had, so step-up adds no new gap.
   - A session holder is limited to 5 guesses per 15 minutes on the one secret.
5. **Race and replay.**
   - Two step-ups racing with one code are serialised by the conditional `sign_count < step` UPDATE. One wins and the other is a wrong code that is counted and feeds the run.
   - A legitimate double-click therefore costs one count. That matches sign-in and is acceptable.
6. **AUTH-05 on a signed-in route.** `code-wrong`, `limited` and `signed-out` are distinguishable, but this route is reached only with a signed-in session, so they reveal nothing about whether an account exists. Every answer is `no-store`.

### Verification performed (this round)
| Command / check | Result |
|---|---|
| `diff <(git diff fb49783...894bca4) <(git diff 5f3cac2...bf520ef)` | identical except DECISIONS hunk offsets and context |
| Detached checkout `.agent/worktrees/review-139-bf520ef9` at bf520ef9 | created, reviewed, removed without `--force` |
| `git diff --check 5f3cac2...bf520ef` | clean |
| `make install lint typecheck test` | pass: contracts 10 kept, Semgrep 21 / 0 findings, rule tests 21/21, mypy 235 files, pytest 1745 (Round 1's 1738 plus PR 140's 7 planted host cases), vitest 4 |
| `make test-live` (own disposable DB, port 5437, project `review-139b`) | 810 passed |
| Mutant: `except` branch feeds the lock regardless of `feeds_lock` | **survived** (139 passed): P3 above |
| Mutant: a wrong code gives its attempt back | killed (19 failed) |
| CI on bf520ef9 | `checks`, `security`, `image`, `host` SUCCESS; `publish`, `deploy-staging` skipped |
| Cleanup | disposable DB `down -v`; scratch copy and `.env` deleted; worktree removed |

### Residual risks and test gaps
- The P3 fault-branch gap (no production effect until M3h-5).
- A stolen session can lock the user's sign-in for 30 minutes, which is accepted and in the runbook. No owner alert exists until Q4 (a).
- Not run by me: `host-test-live`, `secrets-test`, `e2e` (CI `host` and `security` green on this head).
- The builder's 20 mutants were not re-run. Across both rounds I ran 4: 3 killed and 1 survived (above).

### Required before merge
- None.

### Deferred conditions
- None. (R1's P2 deferral is resolved.)

### Optional improvements
- R2 P3 (M3h-5 fault test or drop the parameter); R1 P3 #2 (§6 matrix entry, M4-rest).

---

