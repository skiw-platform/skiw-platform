# PR 37 — docs(setup): PROJECT.md section 7 typecheck path and host-test-live after M1c

- **Merged:** 2026-10-14T03:21:19Z (GitHub) · **Merge commit:** `8cd538ed06a93270648cfc830e2725b9e1bade3e` · **Branch:** `docs/project-section7-m1c` (final head `982b2b34ff91c0546368882f3c5f1c26fda08b89`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-37.receipt` on `agent-logs` (written before the merge); names head `982b2b3…`, review `reviews/PR-37.md`, CI green on that exact head (run 38504593510: checks, host, image, security).
- **Merge evidence:** `gh pr view 37` → MERGED, mergedAt 2026-10-14T03:21:19Z, merge commit `8cd538e`, final head equals the reviewed head of Round 1; `git merge-base --is-ancestor 8cd538e origin/main` succeeded; `agents/PROJECT.md` on `main` says `mypy app infra/host`.
- **Drafted by:** Claude Sonnet 5.5 (builder, direct edit) · **Final verdict:** Approved (Round 1; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`, unchanged · **Milestone:** follow-up to M1c

## What changed
`agents/PROJECT.md` section 7 only (+2/-2): `make typecheck` is `mypy app infra/host`; `make host-test-live` runs the Caddy edge tests today (needs Docker, skips locally without it, fails when `CI=true`, CI job `host`), with roles (M1e) and the file store (M1i) added later.

## Review rounds
- R1: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Next: M1d (`bootstrap-secrets`: `init` and `restore`, inventory, age escrow bundle). Host runs need owner gate G5 (public age keys).
