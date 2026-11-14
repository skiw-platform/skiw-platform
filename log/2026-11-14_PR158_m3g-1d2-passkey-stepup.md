# PR 158 — feat(accounts): M3g-1d-2 step-up with a passkey

- **Merged:** 2026-11-14 (11:39:23 UTC) · **Merge commit:** cedc9e256685a4147a37766d8f04ed4888671d02 · **Branch:** feat/m3g-1d2-stepup (final head 60fa52be9114127dbe0b42e20f9062c2e3287340)
- **Gate breaches:** none. The final round (R2) head SHA equals the PR's final head; the receipt (2026-11-14T11:25:57Z, review-file hash be03ed4b, log-branch commit 740992d) precedes the merge by 13 minutes 26 seconds.
- **Approval receipt:** `reviews/PR-158.receipt` on agent-logs (review at commit 740992d; receipt commit b1b12c4).
- **Merge evidence:** `gh pr view 158` (skiw-platform/skiw-platform) state MERGED, mergedAt 2026-11-14T11:39:23Z, merge commit cedc9e2; reachable from fetched origin/main.
- **Drafted by:** a deep-tier (Opus) sub-agent for the design and code, Sonnet 5.5 for the gates, mutant re-runs, commit and PR body · **Reviewed by:** Claude Opus 5.5 (deep tier), two rounds · **Final verdict:** Approved (round 2)
- **Spec:** v1.22 (unchanged) · **Plan:** M3 §1 M3g row · **Milestone:** M3, package M3g (sixth server PR, 1d-2; last passkey server piece)
- **Repository:** `skiw-platform/skiw-platform`; public while the PR was open, set private again at this merge.

## What changed
Step-up with a passkey: `POST /api/auth/stepup/passkey` (begin, 409 `no-passkey`) and `/api/auth/stepup/passkey/confirm` (body `{purpose, credential}`, one 401 `passkey-wrong`). `assertion.counted_assertion` is now the single entry point for sign-in and step-up (take challenge, reserve, autocommit discovery returning a sealed `Discovered`, verify inside the tenant transaction, then the step-up record). `discover` and `match` are private. `stepup.FACTOR_KINDS = {totp, passkey}`; the evidence names the passkey. +557/−73 over 10 files (630 changed lines counted together, over the 600 rule; the body asked the owner, who approved by merging).

## Why
Owner decision D7 (a passkey for every step-up purpose, 2026-11-13), AUTH-05/06/09. Resolves the PR 157 R2 deferred P2 (reuse contract) and PR 154 R1 P2 #2 (stale-save replay) for step-up.

## Review rounds
- R1 (Blocked, no code finding): exact-head CI did not run (every job failed in 2 s on a billing refusal) → re-run once the repo was public; no code change.
- R2 (Approved): CI attempt 2 green on the same head, all steps executed; no P0, P1 or P2.

## Deferred conditions
- none (two optional P3s below)

## Decisions worth keeping
- One entry point for assertions; direct use of discovery or verification is not a supported path (typed, sealed `Discovered`).
- A passkey satisfies every step-up purpose; the evidence records the passkey as the factor, so it is in the MAC.
- Owner [A], open: step-up evidence stays valid up to 5 minutes after the passkey that proved it is removed.

## Follow-ups
- Optional P3 #1: runbook / DECISIONS wording on the [A] removal behaviour (one sentence is wrong).
- Optional P3 #2: challenge-spent assertions on the limited (locked) path.
- M3g-2 (screens, virtual-authenticator e2e, one challenge per session, passkey label or created time; deep tier), then the M3 gate review and the image-path PR moving `ghcr.io/skiw-dev1` back to `skiw-platform`.
- Carried: owner checks (`ghcr_read_token`; fix the G9 hostname before the first passkey; main checkout `.env`); PR 152 conditions; older P3s; 13 open Dependabot PRs.

## Appendix — final review round
## Round 2 — 2026-11-14 · scope: slice (re-check of the Round 1 blocker; no code change)
- **Code review:** base (merge base) 95185a824f431567f9fb8221c27eba41f61cfad3 (= `origin/main`, unmoved) · head 60fa52be9114127dbe0b42e20f9062c2e3287340 (unchanged since Round 1, one commit) · head re-checked at end: yes
- **CI:** run 43572946965, **attempt 2**, on head 60fa52be: **success**. The steps ran this time:
  - `checks`: lint, typecheck, unit tests, live database role checks, end-to-end tests;
  - `security`: gitleaks v8.30.1 full-history secret scan, secret rule test, Python and web dependency audits, Semgrep registry rulesets;
  - `image`: image build and pre-migration dump image, both Trivy-scanned;
  - `host`: host tooling tests and live host stack tests.

  `publish` and `deploy-staging` were skipped, as normal for a PR event.

**Verdict:** Approved. The Round 1 blocker (exact-head CI did not run) is resolved, and there is no P0, P1 or P2. The two Round 1 P3s stay open as optional work (runbook / [A] wording on removal; the challenge-spent assertions on the limited path), for M3g-2 or a docs/test PR.
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** The standard tier is enough for the P3s. Use the deep tier for M3g-2 (screens, virtual-authenticator e2e) and the owner reset.

### Round 1 resolution audit
| Round 1 item | Round 2 result | Evidence |
|---|---|---|
| Blocker: exact-head CI did not run (UNI-13) | resolved | attempt 2 of run 43572946965 is green on 60fa52be with every job's steps executed (above) |
| UNI-07 (hard) not verified | resolved | CI `Secret scan (full history)` success |
| P3 #1 runbook / DECISIONS [A] on removal | open (optional) | no new commit |
| P3 #2 challenge spent when limited | open (optional) | no new commit |

Verification: I re-checked the PR head, merge base, `main` and the CI run's `headSha` and steps. I did not re-run local checks: the code is byte-identical to Round 1, which passed 1935 unit, 45 vitest and 1106 live tests (twice).

### Required before merge
- none

