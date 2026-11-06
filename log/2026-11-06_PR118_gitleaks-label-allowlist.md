# PR 118 — ci(security): allowlist bare skiw-<words>-v<N> labels for generic-api-key (PR 117 R1 P1)

- **Merged:** 2026-11-06T02:22:39Z · **Merge commit:** c0cd78b714ecd4d391eadc7cb3d22fdb37867663 · **Branch:** fix/gitleaks-label-allowlist
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-118.receipt, commit 8b1e14b (2026-11-06T02:06:58Z, before the merge; head 8092182 and review hash 21b75f96 match)
- **Merge evidence:** `gh pr view 118` (state MERGED, mergedAt 2026-11-06T02:22:39Z, mergeCommit c0cd78b, headRefOid 8092182831f21fd60e12ba2c2c8d896d42ca4044 = the reviewed head); `git merge-base --is-ancestor c0cd78b origin/main` succeeded after a fresh fetch
- **Drafted by:** Claude Sonnet 5.5 (standard tier; config and tests) · **Final verdict:** Approved with conditions (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md (v1.21, d95cb271, unchanged) · **Plan:** none · **Milestone:** outside the milestones (CI gate repair raised by PR 117 R1 P1)

## What changed
One `[[allowlists]]` entry in `.gitleaks.toml` (`targetRules = ["generic-api-key"]`, `regexTarget = "secret"`, regex `^skiw(?:-[a-z0-9]+)+-v[0-9]+$`) so a bare HKDF/MAC domain-separation label such as `skiw-factor-secret-v1` is no longer read as an API key. Three new `make secrets-test` cases in `infra/host/tests/test_gitleaks_config.py` (labels in prose pass; a value assigned next to a label is flagged; a label with a value appended is flagged) and a DECISIONS entry.

## Why
CI `security` had failed on `main` since 2026-11-05 (run 42000260805) and on PR 117 (run 42138355018) on two `generic-api-key` false positives on `agent-logs`, so the secret-rule test, pip-audit, pnpm audit and the registry Semgrep steps never ran (UNI-13). Owner's choice at `fix` 117: the label-pattern allowlist (the reviewer's recommendation) over allowlisting two commits.

## Review rounds
- R1: Approved with conditions. No P0/P1. [P2] the allowlist also hides a high-entropy value written in the label shape (`[a-z0-9]+` is unbounded) → deferred, see below. CI on 8092182 all green with every security step run.

## Deferred conditions
- [P2] allowlist width (UNI-07) → the next builder PR (M3f-3), or a standalone follow-up if that comes sooner. Narrow the regex to the labels that exist, e.g. `^skiw(?:-[a-z]{2,12}){1,4}-v[0-9]{1,6}$`; add a test that `client_secret = "skiw-<token_hex(16)>-v1"` is still flagged, and a same-line `skiw-factor-secret-v1 = "<value>"` test; the full-history scan must still say "no leaks found". The test must fail under today's regex.

## Decisions worth keeping
- The lasting decision is in the merged DECISIONS ("2026-11-06 — Secret scan: allowlist for bare domain-separation labels"); nothing missing.
- gitleaks is not installed on the owner's machine; the pinned v8.30.1 container is used locally (a throwaway wrapper that mounts /Users, /private and /tmp at the same paths makes `make secrets-test` run). Not committed.
- No path or commit exemptions (PR 9 R1 rule) stays: the allowlist keys on the captured secret.

## Follow-ups
- Resolve the P2 above in M3f-3 (it is carried in the handoff with PR 117 R1 P2).
- Re-run CI on PR 117 (no new head) and ask the reviewer for `review 117` R2.

## Appendix — final review round
## Round 1 — 2026-11-06 · scope: slice (CI config fix, outside the milestones)
- **Code review:** base `main`, merge base 59af95b657d28fab5146e41190efdcffe90d6df3 (= origin/main) ·
  head 8092182831f21fd60e12ba2c2c8d896d42ca4044, one commit, 3 files, +52 −1 · head re-checked at end:
  yes, unchanged.
  - **Where:** detached worktree `.agent/worktrees/review-118-80921828`, removed afterwards. Gitleaks
    probes ran in the pinned `ghcr.io/gitleaks/gitleaks:v8.30.1` container, on a temporary directory
    outside the repo.
- **Spec:** v1.21, hash d95cb271 (unchanged). UNI-07, UNI-13; PR 117 R1 P1; the owner's choice
  (option 1) of 2026-11-06.
- **CI (run 42144585981, same head):** checks, security, image, host: pass. publish, deploy-staging:
  skipped. **Every `security` step ran**:
  - full-history scan: 537 commits, "no leaks found";
  - Secret rule test: 5 passed, including the 3 new tests;
  - pip-audit and pnpm audit: pass;
  - registry Semgrep: pass.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier: secret-scan gate) · **Switch model next step?** No.
- **Next:** `approved 118`, then Ying merges. Then re-run CI on PR 117 (head c07aec53) and run
  `review 117` for R2.

### Findings

### [P2] The allowlist also hides a high-entropy value written in the label shape
- Category: material risk
- Rule: UNI-07 (hard). The rule itself is not failed: no secret is in the repo. This is a weakening of the
  scanner.
- Evidence:
  - `.gitleaks.toml:22`, `^skiw(?:-[a-z0-9]+)+-v[0-9]+$`. `[a-z0-9]+` accepts a segment of any length.
  - I probed with gitleaks v8.30.1 on fresh random values, comparing the new config with main's.
  - `client_secret = "skiw-<32 random hex>-v1"` and `api_key = "skiw-<32 random hex>-v1"` are **flagged
    under main's config and skipped under this one**.
  - Controls behave correctly: a bare `secret = "<32 hex>"` is still flagged. So is
    `skiw-factor-secret-v1 = "<token_urlsafe(24)>"` on one line, where the finding is the value.
- Failure scenario: someone sets a token wrapped in this shape, e.g. `skiw-<hex>-v2`, as a key ID or a
  service token. Gitleaks stays silent.
- Why it matters: the PR body says "a real secret that happens to have the exact shape … would not be
  high-entropy". That is not true for this regex. The likelihood is low, because no tool here makes values
  in that shape (key files are `v<n>:<base64>`). But the gate should be no wider than the labels.
- Required correction:
  - Narrow the regex to the labels that actually exist. Every label in `app/` and `infra/` uses lowercase
    words only, the longest being `credential` (10 letters), with at most 3 words. Something like
    `^skiw(?:-[a-z]{2,12}){1,4}-v[0-9]{1,6}$`.
  - Add a test that `client_secret = "skiw-<token_hex(16)>-v1"` is still flagged.
  - Optionally add a same-line test, `skiw-factor-secret-v1 = "<value>"`. Today's "next to a label" test
    puts the value on a separate line.
- Owner: builder
- Verification: the new test fails under today's regex and passes under the narrowed one; the
  full-history scan still says "no leaks found".
- Disposition: deferred to the next builder PR (M3f-3), or a standalone follow-up if that comes sooner.
  Merging now restores five gates that have been off on `main` since 2026-11-05. The gap is narrow, and
  only exists until then.
- Status: open.

No P0, P1 or P3. No injection attempts.

### What was checked (no finding)
- **Scope:** `targetRules = ["generic-api-key"]` only. The project rule `skiw-secret-key-assignment` is
  unchanged, and its tests still pass in CI.
- **`regexTarget = "secret"` with anchors:** a label with a value appended is still flagged (test, and
  the anchor mutant fails it). A value next to a label is flagged, with the value as the finding (test,
  and my same-line probe).
- **No path or commit exemption,** which matches the PR 9 R1 rule.
- **Tests use random values generated at run time,** so no fake secret is committed (UNI-07/08).
- **DECISIONS entry:** present. It records the owner's choice, the alternatives rejected, and the 2 → 3
  hit count with the PR 117 archive, which matches my prediction.
- `git diff --check`: clean. The PROJECT §7 secret-scan pattern on added lines: no hits.

### Self-check audit
I built the applicability list first: UNI-01, 05, 07 (hard), 08, 13, 14 (gitleaks stays pinned at v8.30.1,
so n-a for change) and 16. The table covers all of them except UNI-14, which is unchanged and so no P1.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-07 | yes | pass | pass, with one gap | probes above | P2 (allowlist width) |
| UNI-08 | no | n/a | n/a | values random at run time | — |
| UNI-13 | yes | pass | pass | run 42144585981, all security steps ran and passed | — |
| UNI-05 | yes | pass | pass | one allowlist entry | — |
| UNI-01 | yes | pass | pass | CI `checks` (mypy) green | — |
| UNI-16 | no | n/a | n/a | no deploy, env or auth change | — |

### Verification performed
| Command / check | Result |
|---|---|
| CI run 42144585981 `security` job steps | all ran; scan "no leaks found" over 537 commits; 5 rule tests passed; both audits and registry Semgrep pass |
| gitleaks v8.30.1 container, `dir` probes, new config vs `59af95b` config | label + hex value skipped under the new config (P2); same-line value and bare hex flagged under both |
| `git diff --check 59af95b...8092182` | clean |
| Secret-scan pattern on added lines | 0 hits |
| Head re-read; `git status --untracked-files=no` in the review checkout | unchanged; clean |

Not run locally: `make secrets-test`, `make test`, `make lint`. CI ran them green at this head. No app code
changed.

### Required before merge
- None.

### Deferred conditions
- P2 → M3f-3, or a standalone follow-up if sooner: narrow the label regex, plus a hex-in-label test.

### After merge
- Re-run CI on PR 117. Its merge ref picks up this config. Then run `review 117` (R2).
