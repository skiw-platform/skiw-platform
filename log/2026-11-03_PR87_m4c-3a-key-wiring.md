# PR 87 — feat(tenancy): wiring for the guard key writes (M4c-3a)

- **Merged:** 2026-11-02 (17:54:27 UTC) · **Merge commit:** 1f7ecf733bf2f40acc43337d812d7b071b7b365d · **Branch:** feat/m4c-3a-key-wiring
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-87.receipt on agent-logs (receipt time 2026-11-02T17:41:08Z, before merge; reviewed head 4fd3f5c22e1140b1bf5f69ae0a9f677e7b06a361, review-file hash 65ed8afba2e3db2cbf28b58ea723e332855504c2, review commit ffda4b2)
- **Merge evidence:** `gh pr view 87` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 4fd3f5c2
- **Drafted by:** Opus 5.5 sub-agent (deep tier); split, verified and PR drafted by the Sonnet 5.5 builder · **Final verdict:** Approved with conditions (round 2)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-11-01-m4-core.md §3 M4c-3 (first half) · **Milestone:** M4-core, M4c-3a

## What changed
Wiring only, about 67 added lines, no behaviour change: lazy `SKIW_TENANT_TOKEN_KEYS` / `SKIW_LOOKUP_DECOY_KEYS` readers (cap 999_999), host `migrate` gets `TENANT_TOKEN_KEY_FILE` and `LOOKUP_DECOY_KEY_FILE` with a new Compose `file_secrets` check (two planted failing cases), `make .env` appends generated `TENANT_TOKEN_KEY` / `LOOKUP_DECOY_KEY` lines, DECISIONS entry "M4c-3a".

## Why
First half of plan M4c-3, split off by the plan §1 size rule (whole change was about 516 lines; owner chose the two-PR split 2026-11-03). M4c-3b (the `migrate` key writes) needs these in place first.

## Review rounds
- R1: Revision required.
  - [P1] UNI-03 row missing from the self-check → row added to the PR body.
  - [P2] UNI-16 `local-dev.md` text for the new env vars → deferred to M4c-3b.
  - [P3] settings comment named a module not in the PR → reworded.
  - [P3] `CHECKS` wrapper → plain list.
  - [P3] plan §5 "every PR" n-a rows → UNI-15 and three §9 rows added.
- R2: Approved with conditions. No new findings.

## Deferred conditions
- P2 UNI-16 → M4c-3b: `local-dev.md` gives the two `printf` lines for an older `.env` (pattern `local-dev.md:44-45`), and `host-rebuild.md` carries the rotation / restore / rollback text.

## Decisions worth keeping
- Runbooks were moved to M4c-3b on purpose (they describe its behaviour); the reviewer accepted this as P2 with isolated impact (nothing reads the variables yet).
- `file_secrets` maps `/run/secrets/<x>` to a mount whose source is `<x>`; a long-syntax secret with a different target would give a false alarm (fails closed). None exists today.
- Owner decision 2026-11-03 for M4c-3b: a retired `tenant_mac_key` version listed again stops `migrate`, whatever the bytes, no override flag (recorded in the M4c-3b DECISIONS entry, not yet merged).
- Local checks for this PR ran without the web steps (Node 26 only); CI ran everything and was green.

## Follow-ups
- Name the PR that carries the spec change for plan §9 items 2 and 6 before M4c-3b merges.
- M4c-3b: bring `feat/m4c-3-guard-key-writes` up to date with main, re-run all checks, open the PR, deep-tier review.
- Settings comment: when M4c-4 adds web/worker as readers of the token key, check the comment still holds.
- Still open from earlier rounds: PR 85 P3 long-string regex → M4c-4b; PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR.

## Appendix — final review round
