# PR 64 — docs(setup): reconcile PROJECT.md with spec v1.19

- **Merged:** 2026-10-25T03:38:38Z (GitHub) · **Merge commit:** `8f2261e022af4ae49a374c9d288af09d159cff23` · **Branch:** `docs/setup-reconcile-v1-19` (final head `e8bde12c3fdf9bbe2a979aaf0fff4c14d091e25a`)
- **Gate breaches:** none (1 file, +2 / −2, docs only)
- **Approval receipt:** `reviews/PR-64.receipt` on `agent-logs`, written 2026-10-25T03:38:18Z (before the merge, by 20 seconds); names head `e8bde12…`, review `reviews/PR-64.md` (hash `52793037…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 64` → MERGED, merge commit `8f2261e`, final head equals the reviewed head; `git merge-base --is-ancestor 8f2261e origin/main` succeeded.
- **Built by:** builder · **Final verdict:** Approved (Round 1)
- **Spec:** v1.19, hash `75ac19f61466445c35e4ff9341a0d0984a55249f` (review Round 22 Approved) · **Milestone:** M1j (reconcile before M1j-2)

## What changed
`agents/PROJECT.md` §2: **Spec hash at last reconcile** `0edfb3cd…` (v1.18) → `75ac19f6…` (v1.19); **Other standards** `none` → the amendment `docs/specs/2026-10-24-alert-channel-and-uptime-ping.md` (v1.2), so a builder loads its M1j-2 rules.

## Review rounds
- R1: Approved. No findings.

## Deferred conditions
- none.

## Follow-ups
- `build` M1j-2: Telegram transport, `alert_credential`, weekly heartbeat, `secret-store` rule, the two PR 60 deferred P2 items, runbook. Builder first checks the Telegram Bot API facts and cites them with a date.
