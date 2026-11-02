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
# Review — PR #87

## Round 2 — 2026-11-03 · scope: slice (M4c-3a, first half of plan M4c-3)
- **Code review:** base (merge base) 2e5fc3acc15ff5c113fd2c447290d27570e7a1c6 · head 4fd3f5c22e1140b1bf5f69ae0a9f677e7b06a361 (descends from R1 head 7c3dc251; one commit `4fd3f5c Review R1 fix: settings comment names a module not in this PR; CHECKS wrapper`) · head re-checked at end: yes (unchanged); review checkout clean
- **Spec:** v1.20, hash 92841ba5 (unchanged).

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 87` (builder), then the M4c-3b build and its deep-tier review.

### Findings (R1 status, re-inspected)
- **[P1] UNI-03 row missing: resolved.** The PR body now has a UNI-03 row. Its evidence is `env.py:121-134`, `env.py:25` and `settings.py:69-70`. That matches what the reviewer verified in R1. The line numbers still hold at this head: the settings lines moved by one, and `SKIW_TENANT_TOKEN_KEYS`/`SKIW_LOOKUP_DECOY_KEYS` are now at `settings.py:70-71`. That is cosmetic, not a finding.
- **[P2] UNI-16 `local-dev.md` text: open, deferred to M4c-3b (unchanged disposition).** The self-check now records it as "deferred (review R1 P2)", and the required content (the two `printf` lines for an older `.env`) is named. The M4c-3b review will verify it.
- **[P3] settings comment: resolved.** `settings.py:66-69` now says "read by the migrate-time key writes (M4c-3b); M4c-4 adds web and worker as readers of the token key".
- **[P3] `CHECKS` wrapper: resolved.** `test_compose_config.py:247-258` is a plain list. The parametrized check set is unchanged: still 10 checks, and the host-test count is unchanged at 841.
- **[P3] plan §5 "every PR" rows: resolved.** UNI-15 and the PROJECT §9 TEN-06 / schema / second-agency rows are present as n-a, each with a reason.

No new findings. No prompt-injection text in the new commit or the edited PR body.

### Self-check audit
Same applicability list as R1. The table now covers every applicable rule. UNI-16 is recorded as deferred with the R1 disposition. No other disagreement.

### Verification performed
| Command / check | Result |
|---|---|
| `git diff 7c3dc25 4fd3f5c` | only the settings comment and the `CHECKS` layout; no behaviour change |
| `make -o check-node host-test` (fresh detached checkout at 4fd3f5c) | 841 passed, 35 deselected |
| pytest python part of `make test` (TOOL_ENV, `PYTHONPATH=app:infra/host`) | 1466 passed, 222 deselected |
| mypy app infra/host scripts/deploy-prod | no issues, 147 files |
| ruff check / format --check | clean / 198 files |
| lint-imports | 10 kept, 0 broken |
| `git diff --check` merge-base...head | clean |
| CI run 41487946662, headSha 4fd3f5c | success (checks, security, image, host) |
| Not run locally | web steps, test-live, host-test-live, gitleaks, Semgrep re-run (as R1; the delta touches no `app/` code Semgrep matches beyond a comment; CI green on this SHA) |

### Residual risks and test gaps
- Unchanged from R1. All key-write behaviour is in M4c-3b.

### Required before merge
- None.

### Deferred conditions
- P2 UNI-16: M4c-3b's `local-dev.md` gives the `printf` lines for `TENANT_TOKEN_KEY` and `LOOKUP_DECOY_KEY` for an older `.env` (pattern `local-dev.md:44-45`), and its `host-rebuild.md` carries the plan's rotation / restore / rollback text.

### Optional improvements
- None.

