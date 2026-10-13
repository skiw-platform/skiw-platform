# PR 29 — docs(setup): PROJECT.md section 7 host test commands after M1a

- **Merged:** 2026-10-13T03:36:57Z (GitHub) · **Merge commit:** `95c6567b5015f6c16df82827cf01e933db7121f3` · **Branch:** `docs/project-host-test` (final head `2f7dc40c2ae6424a1224e707104fe1b9e1b17c99`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-29.receipt` on `agent-logs` (written before the merge); names head `2f7dc40…`, review `reviews/PR-29.md`, CI green on that exact head (run 38340477231: checks, host, image, security).
- **Merge evidence:** `gh pr view 29` → MERGED, mergedAt 2026-10-13T03:36:57Z, merge commit `95c6567`, final head equals the reviewed head of Round 1; `git merge-base --is-ancestor 95c6567 origin/main` succeeded; `origin/main:agents/PROJECT.md` has the `make host-test` line and no `pending M1` line.
- **Drafted by:** Claude Sonnet 5.5 (builder, direct edit) · **Final verdict:** Approved (Round 1; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`, unchanged · **Milestone:** follow-up to M1a

## What changed
`agents/PROJECT.md` section 7 only (+5/-2): `make host-test`, `make host-test-live` (stub until M1c, M1e, M1i), `make secrets-test`, and `pending M1b` for the Compose config tests.

## Review rounds
- R1: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- When M1b adds the Compose config tests, the `pending M1b` line in PROJECT.md section 7 needs another tiny docs update (fold it into the M1b PR only if the reviewer accepts a PROJECT.md edit there; otherwise a follow-up PR).
- PRs 12 to 18 and 26 to 28 are open Dependabot PRs; not touched.
