# PR 53 — chore: repo moved to the organization; image path, PROJECT.md remote, TEN-10 worker probe

- **Merged:** 2026-10-22T02:40:06Z (GitHub) · **Merge commit:** `f17dc4995c82d1f566523a330a1f00e1ebcd9ffd` · **Branch:** `chore/image-path-org` (final head `457237be801c48d1cc30dac024b2231c79b7f656`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-53.receipt` on `agent-logs` (written before the merge); names head `457237b…`, review `reviews/PR-53.md`, CI green on that exact head (run 39629772416: checks, host, image, security).
- **Merge evidence:** `gh pr view 53` → MERGED, merge commit `f17dc49`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 457237b origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder) · **Final verdict:** Approved (Round 2; reviewer Codex)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** follow-up to M1g-1, needed before M1h

## What changed
Image path is now `ghcr.io/skiw-platform/skiw-platform` in `infra/host/env/{ci,production,staging}.env`, three host tests and the plan's M1h text. `agents/PROJECT.md` Remote is the new repo. The TEN-10 ops-access mapping lists the `skiw-deploy` worker-registration probe. `docs/DECISIONS.md` has a 2026-10-21 entry for the move, the image path and the probe.

## Review rounds
- R1 (Revision required): [P2] the plan's TEN-10 row and the reason for `postgres` over `skiw_readonly` were missing → plan row updated; DECISIONS gives the reason (`roles.sql` grants `skiw_readonly` no table rights yet).
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- The probe runs as `postgres` until `skiw_readonly` gets table grants.
- Next: `go M1g-2`, then M1h (the org `GITHUB_TOKEN` needs package write permission).
