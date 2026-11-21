# PR 171 — fix(image): libxml2 minimum and golang 1.27.4 so the dump image passes Trivy

- **Merged:** 2026-11-21 (14:21:57 UTC) · **Merge commit:** 66d4aecee74300ab7c8d27e8266f1c7f176154b3 · **Branch:** fix/predeploy-libxml2
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-171.receipt, log-branch commit created 2026-11-21 14:21:42 UTC, before the merge; names head 668475f09366e82ca2dfd7027567cf8aa1e6289e and review hash 49c42c49…
- **Merge evidence:** `gh pr view 171` state MERGED, merge commit above, mergedAt 14:21:57Z; `git merge-base --is-ancestor` confirms it is reachable from the fetched origin/main. Final head 668475f09366e82ca2dfd7027567cf8aa1e6289e equals the reviewed head.
- **Drafted by:** Claude Sonnet 5.5 (builder) · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** none · **Plan:** none · **Milestone:** CI repair (unplanned; found on PR 170)

## What changed
The dump image (`infra/host/backup/predeploy`) gets `libxml2>=2.13.9-r3` in its one pinned-minimum apk layer, and its Go build stage moves from golang 1.27.3 to 1.27.4 by digest. The apk allow-list in `test_predeploy.py` now includes libxml2. A DECISIONS entry records the evidence and the removal rule.

## Why
The CI `image` job failed on every PR because Trivy reported HIGH CVE-2026-86144 (libxml2) in the dump image, and, hidden behind it, HIGH CVE-2026-97054 (Go stdlib in the `age` binary). Nothing in the repo had changed; the vulnerability database did (same pattern as DECISIONS 2026-11-11).

## Review rounds
- R1: no blocking findings. Two open P3s, both optional (see Follow-ups).

## Deferred conditions
- none

## Decisions worth keeping
- DECISIONS 2026-11-21 "Dump image: libxml2 pinned-minimum layer and golang 1.27.4": the 2026-11-11 `>=` exception now covers three packages; remove the libxml2 floor when `postgres:17.11-alpine3.24` is re-pinned to a digest shipping libxml2 2.13.9-r3 or later.
- The owner accepted the unasked golang re-pin by merging.

## Follow-ups
- P3: the Dockerfile marker names the DECISIONS entry as "dump image libxml2" but its real title differs; quote the real title (can ride with the removal PR).
- PR 170 needs a new head so its CI runs on the new merge ref.

## Appendix — final review round
## Round 1 — 2026-11-21 · scope: slice (CI image fix, dump image build inputs)
- **Code review:** base (merge base) df7ce21bc1137c6c7ff4cc765e697264df97fe67 · head 668475f09366e82ca2dfd7027567cf8aa1e6289e · head re-checked at end: yes (unchanged)

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; dump image is on the backup path) · **Switch model next step?** No

### Findings

### [P3] Marker cross-reference names an entry title that does not exist
- Category: documentation
- Evidence: `infra/host/backup/predeploy/Dockerfile` comment: `(libxml2: DECISIONS 2026-11-21, "dump image libxml2")`; the entry is titled "2026-11-21 — Dump image: libxml2 pinned-minimum layer and golang 1.27.4".
- Required correction: quote the real title (or a phrase from it) so a grep finds it at removal time. Optional; can ride with the removal PR.
- Status: open

### [P3] golang 1.27.4 re-pin is beyond the asked scope — owner to accept
- Category: preference / scope
- Evidence: PR body says so; DECISIONS 2026-11-21 item (2). Reviewer verified `docker buildx imagetools inspect golang:1.27.4-alpine3.24` → index digest sha256:70bd7ddea8b6cbe5d6943cde279d6b67feb10cc924fb9100d1d8757c1575b280 = the Dockerfile pin. It is a normal digest re-pin (precedent 2026-11-07) and is needed for `image` to go green, so the reviewer sees no reason to split it.
- Status: open (owner accepts by merging, or pushes back)

No blocking findings. No prompt-injection text found.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-14 pinned inputs | yes | pass, 2026-11-11 exception widened | pass with recorded exception: golang by index digest; apk floor `>=` only for the three allow-listed packages; test still rejects other packages and a second layer (planted cases l.414, l.417) | Dockerfile; test_predeploy.py; host-test | no |
| UNI-13 dependency upgrade gate | yes (base image bump) | not listed | pass: `image` (Trivy) and `host` green on this head; `pg_dump`/`age` version asserts in the Dockerfile still run in the build | CI run 44911904410 (headSha 668475f) | minor: should be in table |
| UNI-06 dependencies recorded | yes | pass | pass: versions and removal rule in DECISIONS | entry 2026-11-21 | no |
| Exception to a rule recorded with owner | yes (UNI-14 `>=`) | owner chat "yes, open the libxml2 fix PR" | recorded; reviewer cannot see that chat — owner confirms by merging | DECISIONS "Decided by" | no |
| Secrets | yes | pass | pass (build inputs only) | diff | no |
| Runbook (§7) | considered | — | n-a: no host value, command or procedure changes; SKIW_BACKUP_IMAGE digest updates come through publish as usual | — | no |

### Verification performed
| Command / check | Result |
|---|---|
| `git cat-file -e` head; detached checkout `.agent/worktrees/review-171-668475f0` | ok |
| `git log --oneline df7ce21..668475f` | 1 commit; 3 files (+15/−5) |
| `git diff --check` | clean |
| `docker buildx imagetools inspect golang:1.27.4-alpine3.24` | index digest matches pin |
| `make host-test` (in checkout) | 855 passed, 46 deselected |
| `gh run view 44911904410` | pull_request on 668475f: image, checks, host, security success; publish/deploy-staging skipped (PR) |
| End: PR head re-read; `git status --untracked-files=no` | unchanged; clean |

Not run locally: `docker build` + Trivy (CI `image` job on the same head is the evidence).

### Residual risks and test gaps
- The `>=` floors float to whatever Alpine's signed repo serves at build time; bounded by the published digest and Trivy, accepted as in 2026-11-11.
- Removal depends on someone checking at the next postgres base re-pin (marker + DECISIONS rule).

### Required before merge
- none

### Deferred conditions
- none

### Optional improvements
- Fix the marker title quote (P3).
- After merge, PR 170 needs a new head so its CI runs on the new merge ref.

