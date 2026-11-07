# PR 127 — fix(image): re-pin python:3.12.15-alpine to the rebuilt digest (Alpine 3.24.3)

- **Merged:** 2026-11-07 (11:30:47 UTC) · **Merge commit:** 05f42a63b8b85fc738c6a7fcc61e6caf9816f9ef · **Branch:** fix/base-image-digest-alpine-3-24-3 (final head dab2e8b007378afe569d7a9669a1bcb53ec5fb44)
- **Gate breaches:** none. The final review round (Round 2, Approved) names head dab2e8b, which equals the PR's final head; the receipt exists for that head and the final review-file hash, written 1 min 15 s before the merge.
- **Approval receipt:** `reviews/PR-127.receipt` on agent-logs, time 2026-11-07T11:29:32Z, review-file hash 50540ae4, review commit 6ef4c98.
- **Merge evidence:** `gh pr view 127` state MERGED, mergedAt 2026-11-07T11:30:47Z, merge commit 05f42a6; `git merge-base --is-ancestor 05f42a6 origin/main` true (origin/main tip is 05f42a6); `origin/main:Dockerfile` line 12 carries `@sha256:b658b05c…`.
- **Built by:** Sonnet 5.5 builder (reviewed by GPT-5 Codex) · **Final verdict:** Approved (Round 2; Round 1 Revision required)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22 (T17, D15) · **Plan:** none · **Milestone:** CI hygiene, unblocks PR 126

## What changed
`Dockerfile` line 12: `python:3.12.15-alpine` re-pinned from `@sha256:1b668429…` (Alpine 3.24.2) to `@sha256:b658b05c…` (Alpine 3.24.3; musl and musl-utils 1.2.6-r3, zlib 1.3.2-r1). Same Python version and tag. One `DECISIONS.md` entry. No allow-list, no `.trivyignore`, no `apk upgrade` layer.

## Why
The CI `image` job (Trivy 0.75.0, HIGH/CRITICAL, exit 1) began failing on 2026-11-07 on three fixed HIGH findings in the old digest (musl/musl-utils CVE-2026-107891, zlib CVE-2026-85091). The repo had not changed; the vulnerability database had (main was green at d1b7abb). Found by the PR 126 review R2 [P1] (UNI-13).

## Review rounds
- R1: Revision required. [P1] self-check cited UNI-06 for the digest pin and omitted UNI-14 → PR body edited (UNI-14 row added, UNI-06 marked n-a); head unchanged.
- R2: Approved. No findings.

## Deferred conditions
- none

## Decisions worth keeping
- A new vulnerability-database entry can turn a green image gate red with no repo change; the fix is to re-pin to the upstream rebuilt digest, not to ignore the finding. The dump image's scan step is skipped when the app-image scan fails, so scan both locally before claiming the dump image is clean (done here: 0 findings).
- Cite guardrails by their real IDs: UNI-13 (build and scans), UNI-14 (pinning), UNI-06 is only the new-dependency ladder. Read `agents/guardrails/universal.md` before writing a self-check table.

## Follow-ups
- Builder: push the PR 126 plan fix (local commit eceb3d9) on top of the new main, rebuild its self-check with the full universal list including UNI-13 and UNI-14, then `review 126` again; `approved 126` before merge.
- Open from earlier: Dependabot PR 14 (python 3.15, uv 0.13) not taken; Dependabot alerts 1 and 2 not looked at; D20 spec P3.

## Appendix — final review round
# Review — PR #127

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 2 — 2026-11-07 · scope: slice
- **Code review:** base (merge base) `d1b7abb9c641326300c7803e0c1aab69ef22dd42` · head `dab2e8b007378afe569d7a9669a1bcb53ec5fb44` · head re-checked at end: yes
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.22 · hash (`git hash-object`) `79a9a40ee1a686ae1082e8d11a73b299deb66d38`

**Verdict:** Approved
**Model used:** GPT-5 Codex · **Switch model next step?** No — review is complete and the builder's approval-archive step is mechanical.

### Findings

No blocking findings.

Round 1's P1 self-check finding is resolved: the PR body now cites UNI-14 for the pinned base-image digest and separately marks UNI-06 not applicable because no new dependency is introduced. The code head did not change.

### Self-check audit

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-06 | n-a: same Python version/tag and existing image dependency; only the rebuilt digest changes | n-a: no new dependency | n-a | Corrected PR body; two-file diff | No |
| UNI-07/08/09 | Applies as secrets/data hygiene; no secret source, data, or logging mechanism changes | UNI-07/09 pass; CI security confirms | pass | Round 1 changed-lines scan; exact-head `security` job passed | No |
| UNI-13 | Applies: production build, image scan, dependency audit, and secret scan must pass | pass for build and image scan; CI cited for all gates | pass | Round 1 local build/Trivy; exact-head CI `checks`, `host`, `image`, `security` all passed | No |
| UNI-14 | Applies: base image must remain pinned by digest | pass under the correct ID | pass | `Dockerfile:12`; exact OCI digest resolves | No |
| Spec T17 / D15 | Applies: pinned base image and zero HIGH/CRITICAL findings | pass | pass | Round 1 local/CI Trivy evidence; current exact-head CI remains green | No |
| Decisions log | Applies: durable rationale for the image security re-pin | pass | pass | `docs/DECISIONS.md:1122`–`1131` | No |
| Other universal rules and ticked packs | n-a: no application behavior, schema, UI, auth, files, jobs, money, finalized-records, deploy procedure, env, domain, or runbook change | n-a / unchanged | n-a | Effective diff unchanged from Round 1 | No |

### Verification performed

| Command / check | Result |
|---|---|
| `git fetch origin`; `gh pr view 127` | PR open, not draft, mergeable; exact head remains `dab2e8b00…` |
| PR-body self-check inspection | UNI-14 row present with digest evidence; UNI-06 correctly marked n-a; Round 1 fix note present |
| Fresh detached checkout `.agent/worktrees/review-127-dab2e8b0-r2` | exact head checked out; tracked state clean |
| Merge-base and three-dot inventory | base remains `d1b7abb9…`; only `Dockerfile` and `docs/DECISIONS.md`, 12 insertions and 1 deletion |
| `git diff --check d1b7abb9…...HEAD` | pass |
| `docker buildx imagetools inspect python:3.12.15-alpine@sha256:b658…` | exact OCI index digest resolves with official Docker Python source metadata |
| `gh pr checks 127` | `checks`, `security`, `image`, and `host` pass; publish/deploy correctly skipped for the PR |
| Final head and checkout check | host head unchanged at `dab2e8b00…`; checkout clean |

Round 1's local image build, runtime package inspection, Trivy 0.75.0 scan, secret-pattern scan, injection scan, exact-head CI-log inspection, and decision-log verification remain valid because the code head is unchanged.

### Residual risks and test gaps
- No app/unit/live suite was rerun locally in Round 2 because the code head is unchanged and the diff contains no application or schema change; exact-head CI remains green.

### Required before merge
- None. Approved is not a merge instruction; run `approved 127` to archive the review before Ying merges.

### Deferred conditions
- None.

### Optional improvements
- None.

### Handoff block (only when handing off)
<!-- roles/reviewer.md §10 -->

