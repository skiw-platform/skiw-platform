# PR 23 — docs(setup): reconcile PROJECT.md with spec v1.18

- **Merged:** 2026-10-12T14:26:27Z (GitHub) · **Merge commit:** `30b4f57e307b4518e404f8d4d9c11d6f99e1ec5d` · **Branch:** `docs/reconcile-spec-v1.18` (final head `667921ebe907178da0f074c8695d861656b2c03b`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-23.receipt` on `agent-logs` (written before the merge); names head `667921e…`, review `reviews/PR-23.md`, CI green on that exact head (run 38257500879).
- **Merge evidence:** `gh pr view 23` → MERGED, mergedAt 2026-10-12T14:26:27Z, merge commit `30b4f57`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 30b4f57 origin/main` succeeded; `origin/main:agents/PROJECT.md` carries spec hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`.
- **Drafted by:** Claude Sonnet 5.5 (builder; PROJECT.md text by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` (was v1.13 `e3141585…`) · **Milestone:** setup reconcile; reconcile gate cleared, `build` unblocked.

## What changed
`agents/PROJECT.md` only (+43/-31): identity (iCore VPS), spec hash, layout (`infra/host/`, CDK removal staged to M1), commands, pack parameters, project rules (G-AI/G-DRIVE route-change locks, five real-data gates, owner-held production key, `file_tombstone`, residency), secrets lines.

## Review rounds
- R1 (Revision required): [P1] self-check lacked FILE-01 to 04 and TEN-04 to 08 alignment rows, and UNI-15/UNI-19 labels → rows added. [P2] `scripts/deploy-prod` not an allowed path → section 3 allows that one wrapper.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Out of sync and owned by the M1 PR: `.gitleaks.toml`, `Makefile`, `.github/workflows/ci.yml` (CDK `infra` job), `pyproject.toml` infra group, `infra/` CDK skeleton, `.env.example` line 2, runbooks, Dependabot `docker-compose` entry.
- Still open: Bedrock extended-thinking row until Q39; name of the `infra/host` test command (`pending M1`); owner-open values Q34 to Q41.
