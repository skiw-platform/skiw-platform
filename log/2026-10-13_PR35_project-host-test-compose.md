# PR 35 — docs(setup): PROJECT.md section 7 host-test includes the Compose config tests

- **Merged:** 2026-10-13T14:41:12Z (GitHub) · **Merge commit:** `ca76fa9aad740edb0591d7ec76d3ca55bc9fb7bf` · **Branch:** `docs/project-host-test-compose` (final head `ea8243d8d1ef07dc9af460c25a8d6c53d4d389ad`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-35.receipt` on `agent-logs` (written before the merge); names head `ea8243d…`, review `reviews/PR-35.md`, CI green on that exact head (run 38411573809: checks, host, image, security).
- **Merge evidence:** `gh pr view 35` → MERGED, mergedAt 2026-10-13T14:41:12Z, merge commit `ca76fa9`, final head equals the reviewed head of Round 1; `git merge-base --is-ancestor ca76fa9 origin/main` succeeded; `agents/PROJECT.md` on `main` has no `pending M1b` line.
- **Drafted by:** Claude Sonnet 5.5 (builder, direct edit) · **Final verdict:** Approved (Round 1; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`, unchanged · **Milestone:** follow-up to M1b-2

## What changed
`agents/PROJECT.md` section 7 only (+1/-2): the `make host-test` line now says it runs the infra/host unit tests and the Compose config tests (needs the `docker compose` CLI; skips locally without it, fails when `CI=true`); the `pending M1b` line is removed.

## Review rounds
- R1: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Still stubbed: `make host-test-live` until M1c, M1e and M1i fill it.
- Next: M1c (Caddy edge). Owner gates G9 (hostnames, DNS) and G13 (Caddy ports) matter for its host steps.
