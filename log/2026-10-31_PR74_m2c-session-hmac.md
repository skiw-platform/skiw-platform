# PR 74 — feat(accounts): key-bound HMAC on session data (M2c)

- **Merged:** 2026-10-31T04:46:12Z (GitHub) · **Merge commit:** ebe2c918814bdc64e1525969df0aeb5346816227 · **Branch:** feat/m2c-session-hmac
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-74.receipt` on agent-logs (review commit 7a4ed9e5fe554927cd7a0fa26a7bf1491130ab5f); head a607e2aa and review-file hash 2390fca7 match the final round; written 2026-10-31T04:30:50Z, before the merge
- **Merge evidence:** `gh pr view 74` state MERGED, merge commit above, merged 2026-10-31T04:46:12Z; commit is an ancestor of the fetched `origin/main`; final head SHA a607e2aaa65126625f5e1762cffc89ef9b4da4f1 equals the reviewed SHA
- **Drafted by:** Opus sub-agent (code), Claude Sonnet 5.5 (checks, commit, PR); reviewer Claude Opus 5.5 (Rounds 1 and 3), Codex GPT-5 (Round 2) · **Final verdict:** Approved with conditions (round 3)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 · **Plan:** docs/plans/2026-10-27-m2-headers-sessions-csrf.md · **Milestone:** M2 (M2c)

## What changed
`session_data` is now `v<n>:<mac>:<signed blob>`. The MAC is HMAC-SHA-256 under `tenant_source_key` over a fixed label, the stored key, `expire_date` and the blob. The newest key version signs and every listed version verifies. A row with edited data, copied data or an edited `expire_date` loads as an empty session, the cookie is deleted and the row is never updated in place. Adds a versioned key reader, a lazy key read, a start-up check in `config.asgi`, the key mount for `web` and `worker` only, and runbook notes. About 125 lines of production code; no new dependency.

## Why
Spec v1.20 section 9 M2: "a row with edited data, or data copied from another row, is rejected (logged out)"; TEN-11; plan Risk 7 (`expire_date` bound into the MAC).

## Review rounds
- R1: Approved with conditions. No P0/P1. One P2 and five P3 (below).
- R2: Blocked, written by a Codex reviewer started by the builder's auto-review script. Its sandbox could not reach GitHub, so head and CI were unproven. Findings matched R1. Builder lesson: do not run the auto-review script again.
- R3: Approved with conditions. Closed the R2 evidence gap (head a607e2aa and CI run 41090244916 green). Records the owner's answers Q1 = A and Q2 = A.

## Deferred conditions
- [P2] The session-reject warning on `django.security.SuspiciousSession` reaches no output when `DEBUG` is off → the first M3 PR, before any login route merges, with a test that reads real stderr (not `caplog`).
- [P3] Key versions of 7+ digits pass start-up but cannot verify their own seals → cheap, may ride along in the first M3 PR.
- [P3] No test proves a renewed deadline is re-MACed → add in the M3 login test.
- [P3] Handoff header named PR 73 → fixed by the builder's handoff update.

## Decisions worth keeping
- Owner Q1 = A: `make .env` generates the local `TENANT_SOURCE_KEY`; `.env.example` has no key line; no gitleaks allowlist. The M2c entry in `docs/DECISIONS.md` still says deviation (c) is "left to the owner to confirm". Record the confirmation through a normal reviewed PR.
- Owner Q2 = A: the M3 plan must add a server-side revocation (or generation) marker, so a deleted session row put back by an INSERT as `skiw_app` is rejected, with a test.
- `require_key` lives in `accounts.source_key` (no DB) because the TEN-10 contract stops `config.asgi` importing `accounts.session`.
- Every local `.env` needs a key line: `printf 'TENANT_SOURCE_KEY=v1:%s\n' "$(openssl rand -base64 32)" >> .env`.

## Follow-ups
- Record Q1 and Q2 in `docs/DECISIONS.md` (reviewed PR from a feature branch, or with the first M3 PR).
- First M3 PR: the P2 above, the version-range P3, the revocation marker (Q2).
- M2d is next: django-ninja CSRF reading, the `route()` registry, the gate and the redeploy proof.
- M1k real-host proof still waits for the bought VPSs.

## Appendix — final review round
## Round 3 — 2026-10-31 · scope: slice (M2c of plan `docs/plans/2026-10-27-m2-headers-sessions-csrf.md`)
- **Code review:** base (merge base) `33effaa732f41b111a1a6a2ee46327a8403ca74c` · head `a607e2aaa65126625f5e1762cffc89ef9b4da4f1` · head re-checked at end: yes (GitHub)
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371`
- Purpose: close the Round 2 evidence gap (host head and CI unproven). The code is the same commit that Round 1 reviewed and tested locally in this session, so no new review checkout was made and no local check was re-run in this round.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No — the next step (`approved 74`) is a builder step.

### Findings

No P0 or P1 findings. No P2 is marked `before merge`.

- **Round 2 [Blocked] "The PR head and CI state cannot be proved from the git host": resolved.** `gh pr view 74`: state OPEN, base `main`, head `a607e2aaa65126625f5e1762cffc89ef9b4da4f1`, one commit, MERGEABLE, last updated 2026-10-30T16:28:39Z (before Round 1). `gh run list --branch feat/m2c-session-hmac`: run 41090244916 on `a607e2aa`, completed, success (checks, host, image, security pass; publish and deploy-staging skipped, as on every PR). `origin/main` is still `33effaa`, so the merge base is unchanged.
- **Carried forward unchanged from Rounds 1 and 2 (same commit, all still open):**
  - [P2] The session-reject warning reaches no output when `DEBUG` is off. Disposition: deferred to the first M3 PR, before any login route merges.
  - [P3] Key-file versions of 7 or more digits pass start-up but cannot verify their own seals.
  - [P3] No runtime test proves a renewed deadline is re-MACed.
  - [P3] A deleted session row can be resurrected by an attacker who can INSERT as `skiw_app` (owner to decide in the M3 plan).
  - [P3] PR-body text addressed to the reviewer, re-read on GitHub this round, still exactly: `Reviewer: say if you prefer the allowlist.` A harmless question with no gate effect. My opinion on the ASK: keep the generated key and add no gitleaks allowlist. The owner decides.
  - [P3] The handoff header still names PR 73 as current.
- Note on Round 2: it was written by a different reviewer session (GPT-5 Codex). Its findings match Round 1, and its only blocker was missing host access. Its snapshot `.agent/worktrees/review-74-a607e2aa-round2` no longer exists.

### Owner decisions (Ying, in this reviewer session, 2026-10-31)
- **Q1 = A:** keep the PR as it is: `make .env` generates the local `TENANT_SOURCE_KEY`, `.env.example` holds no key line, and gitleaks gets no allowlist. The ASK and the PR-body text addressed to the reviewer are closed.
- **Q2 = A:** the M3 plan adds a server-side revocation (or generation) marker, so that a deleted session row put back by an INSERT as `skiw_app` is rejected, with a test. The P3 "deleted session row can be resurrected" finding stays open until the M3 plan carries this.
- The reviewer does not write `docs/DECISIONS.md` (Rule 0). The builder records both answers there, either in this PR's M2c entry (deviation (c) "left to the owner to confirm" → confirmed) or in the M3 plan PR.

### Self-check audit
Unchanged from Round 1 (same head, same PR body). Every rule ID of the universal, auth and tenancy-rls packs is in the builder's table. My only disagreements are the UNI-09 routing (P2) and the UNI-03 version range (P3).

### Verification performed
| Command / check | Result |
|---|---|
| `gh pr view 74` (state, base, head, commits, mergeable, updatedAt) | OPEN · `main` · `a607e2aa` · 1 commit · MERGEABLE · 2026-10-30T16:28:39Z |
| `gh pr checks 74`, `gh run list --branch feat/m2c-session-hmac` | run 41090244916 on `a607e2aa`: success |
| `git fetch origin`; `git rev-parse origin/main origin/feat/m2c-session-hmac`; merge base | `33effaa` · `a607e2aa` · `33effaa` |
| Local checks on this SHA (Round 1, this session) | ruff, lint-imports, mypy, 1085 unit, 124 live, 818 host-test: pass |
| End: GitHub head re-read | still `a607e2aa` |

### Residual risks and test gaps
- Same as Round 1. Semgrep, `host-test-live`, e2e and the web checks rest on CI for this exact SHA, not on local runs.

### Required before merge
- None.

### Deferred conditions
- P2 session-reject warning reaches no output with `DEBUG` off → the first M3 PR, before any login route merges.

### Optional improvements
- The P3 items above.
