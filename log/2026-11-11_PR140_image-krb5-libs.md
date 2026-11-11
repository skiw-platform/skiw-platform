# PR 140 — fix(image): pinned-minimum krb5-libs and libxslt layers until upstream rebuilds

- **Merged:** 2026-11-11 (04:39:43 UTC) · **Merge commit:** 5f3cac2778f2a0556c5c25ae07b1141ffee4286c · **Branch:** fix/image-krb5-libs (final head e43fd9617553948c6a21b2f845e517ad68bee26c)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-140.receipt`, 2026-11-11T04:39:22Z, review-file hash c37a99c2, review commit 2dab9dc) precedes the merge by 21 seconds.
- **Approval receipt:** `reviews/PR-140.receipt` on agent-logs (written by `approved 140` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 140` state MERGED, mergedAt 2026-11-11T04:39:43Z, merge commit 5f3cac2; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder (no deep-tier design needed: build inputs only) · **Final verdict:** Approved (Round 1, no revision round); **reviewed on the standard tier (Sonnet 5.5), not the deep tier the owner required (condition 3)**. The reviewer built and Trivy-scanned both images and probed the test rule, but did not give the backup path a deep-tier read.
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** none · **Milestone:** not a milestone: the base-image refresh PR that PR 139 R1 P2 deferred

## What changed
One `RUN apk add --no-cache` line per image: the app `Dockerfile` (runtime stage) `krb5-libs>=1.22.3-r0`; the dump image `krb5-libs>=1.22.3-r0` and `libxslt>=1.1.43-r4`. Both carry the marker `REMOVE-WHEN-UPSTREAM-REBUILDS (DECISIONS 2026-11-11, "base images krb5-libs")`. The dump image's Dockerfile test (`check_dockerfile`) forbade `apk` altogether; it now allows exactly one such layer of those two packages (`APK_FIX`) with seven planted cases. DECISIONS "2026-11-11 — Base images: a pinned-minimum apk add ...". +36/−1 over 4 files; no application code.

## Why
From 2026-11-11 CI `image` failed on `main` and every PR (found by PR 139 R1, P2): Trivy v0.75.0, 16 HIGH CVEs, all `krb5-libs` 1.22.2-r1 in the app image; the dump image (scanned after it) had 18 (`krb5-libs`, `libxslt`). Upstream had not rebuilt either base, so re-pinning (the 2026-11-07 route) did not work.

## Review rounds
- R1: Approved, nothing required. Two optional P3s, both open: (1) `APK_FIX` accepts lowered floors (`>=1-r0`), a duplicate package or a missing `libxslt`; compare the apk line to the exact string held in one constant, with a planted lowered-floor case; (2) the marker quotes `"base images krb5-libs"`, which is not a substring of the DECISIONS heading; make it one. Both: in the removal PR or the next change to this file.

## Deferred conditions
- None.

## Decisions worth keeping
- Owner chose, 2026-11-11 (`approved 139` chat), to allow pinned `apk` layers with four conditions: only these packages; `>=` recorded as a deliberate exception to "pinned inputs only" (UNI-14) with a removal note and the same marker in both Dockerfiles; its own PR on the deep tier with `image` green; PR 139 given a new head afterwards. Rejected: waiting for upstream, a Trivy ignore list, an exact pin.
- **Removal rule:** delete each `apk add` line when its base (`python:3.12.15-alpine`, `postgres:17.11-alpine3.24`) is re-pinned to a digest that ships the fixed versions, and delete `APK_FIX` and its planted cases with it. Check on every base digest bump (Dependabot).
- The dump image is scanned after the app image in one CI job, so a first failure hides the second image's findings; scan both locally when the job goes red.

## Follow-ups
- PR 139 (M3h-3): rebase on main (expect a DECISIONS.md end-of-file conflict, keep both entries), push a new head, wait for green `image`; the review covers head 894bca4, so ask the owner whether the reviewer must confirm the new head before `approved 139`.
- Optional P3s above (removal PR or next change to the files).
- **Tier gap:** condition 3 asked for a deep-tier review; this one was standard. Told to the owner at `merged 140`; the owner decides whether a deep-tier read of the backup-path change is still wanted.
- Watch for upstream rebuilds of the python and postgres alpine tags; remove the layers then.

## Appendix — final review round
## Round 1 — 2026-11-11 · scope: slice (build inputs only: two Dockerfiles, one test rule, one decisions entry; no application code)
- **Code review:** base (merge base) fb497837f7e35c8d3a8acc5422ebae8b1151740c (= `origin/main`) · head e43fd9617553948c6a21b2f845e517ad68bee26c · head re-checked at end: yes (host head unchanged, PR open; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (equals PROJECT.md §2): §8.4 H3 step 4, H6 (the dump image is part of the backup path). DECISIONS 2026-10-23 "Dump image passes the Trivy gate", 2026-11-07, 2026-11-11. Carry-over checked: PR 139 R1 P2.

**Verdict:** Approved
**Model used:** Claude Sonnet 5.5 (standard tier). The PR asks for the deep tier because of the backup path; see Residual risks. · **Switch model next step?** Yes — PR 139 (new head) and M3h-4 are auth work; deep tier.

### Carry-over (re-inspected)
- **PR 139 R1 P2 (CI `image` red from krb5 in the base images): resolved by this PR, on the head.** CI `image` is SUCCESS on e43fd96. Independently, I built both images from the pinned head and scanned them with `aquasec/trivy:0.75.0 image --severity HIGH,CRITICAL --exit-code 1`: both exit 0. `apk info` shows krb5-libs 1.22.3-r0 in both and libxslt 1.1.43-r4 in the dump image.
- **The owner's four conditions (2026-11-11), each checked:**
  1. *Exactly these packages:* the dump image test accepts only `krb5-libs` and `libxslt`; my probe showed another package, `sh -c "apk …"`, and `/sbin/apk` are all rejected (but see P3: the floors are not pinned).
  2. *`>=` recorded as a deliberate exception, removal note, same marker in both Dockerfiles:* DECISIONS "Exception to a rule: yes, two"; the marker `REMOVE-WHEN-UPSTREAM-REBUILDS (DECISIONS 2026-11-11, "base images krb5-libs")` is identical in both files; the entry names the base re-pin that triggers removal and the test lines to delete.
  3. *Own PR, deep tier, `image` green:* own PR; `image` green; deep tier not met by this round (below).
  4. *PR 139 gets a new head afterwards:* still to do after this merges.

### Findings

### [P3] `APK_FIX` is looser than its comment and the DECISIONS entry say
- Category: preference / guardrail tightness
- Rule: UNI-14 (the recorded exception), owner condition 1
- Evidence: `infra/host/tests/test_predeploy.py` `APK_FIX = r'apk add --no-cache( "(krb5-libs|libxslt)>=[0-9][0-9.]*-r[0-9]+")+'`. I ran `check_dockerfile` on the dump Dockerfile with the apk line replaced. **Accepted:** floors of `>=0-r0` and `>=1-r0`; `krb5-libs` listed twice and no `libxslt`; `libxslt` alone. **Rejected:** any other package, `sh -c "apk …"`, `/sbin/apk`, a second apk layer.
- Failure scenario: a later edit lowers a floor to `>=1-r0` (or drops `libxslt`). The test passes, the build takes whatever Alpine's index holds, and only the Trivy scan, and only while its database still flags the old version, stands between that and a vulnerable shipped image.
- Why it matters: low. The Trivy gate is a real backstop and any change here is a reviewed PR. The test is meant to be the control for "exactly this, nothing else", and the regex does not say that for the floors.
- Required correction: compare the apk line to the exact string, `RUN apk add --no-cache "krb5-libs>=1.22.3-r0" "libxslt>=1.1.43-r4"`, held in one constant. The removal note already tells whoever deletes the line to delete the constant. Keep the planted cases.
- Owner: builder · Verification: a planted case with a lowered floor fails.
- Disposition (P3): optional; if taken, do it in the removal PR or with the next change to this file · Status: open

### [P3] The marker's DECISIONS reference does not match the entry's heading
- Category: documentation
- Evidence: both Dockerfiles say `DECISIONS 2026-11-11, "base images krb5-libs"`; the heading is "2026-11-11 — Base images: a pinned-minimum `apk add` for krb5-libs (and libxslt in the dump image) until upstream rebuilds". Searching for the quoted text finds nothing.
- Required correction: make the quote a substring of the heading (or the reverse). The marker `REMOVE-WHEN-UPSTREAM-REBUILDS` itself is identical and greppable, which is what matters.
- Owner: builder · Disposition (P3): optional · Status: open

No prompt-injection text found in the PR body, commit message, Dockerfiles, test or DECISIONS entry.

### What I checked beyond the self-check
- **Dump image still does its job.** In the image I built: `pg_dump` 17.11, `age` v1.3.2, `python3 -I` imports `ssl`, user `10003:10003`. The layer sits before the `COPY --from=python`, so the Python stdlib and `age` are unaffected, and `gosu` is still removed afterwards.
- **App image still runs.** Django 5.2.17 imports; user `skiw`. The new layer is before `adduser` and the `uv sync` step, so the dependency layers keep their cache behaviour except for the one new layer.
- **Image size:** 315 MB (app) and 469 MB (dump); no new tool beyond the two upgraded libraries (Trivy's package scan reports none).
- **What the exception costs.** Builds now read Alpine's package index at build time, so two builds on different days can differ. That is the owner-approved trade (an exact pin breaks when the index moves). The digest that ships is the one CI builds and publishes (M1h), and hosts name that digest, so a given release is still fixed bits.
- **Scope:** four files, no application code; `make lint`, `typecheck`, `test` (1730) and `host-test` (854) pass on the head, equal to the PR.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-04 | yes | pass | pass | contracts 10 kept; Semgrep 21 rules / 0 findings | — |
| UNI-07 (hard) | yes | pass | pass | CI `security` green; no key values in the diff | — |
| UNI-13 | yes | pass | pass | CI `image`, `security`, `host` green on this head; local Trivy on both images exit 0 | — |
| UNI-14 | yes | pass with recorded exception | pass with recorded exception | DECISIONS entry; P3 on the test's tightness | P3 |
| UNI-06 | n/a, no app dependency (apk packages are the recorded exception under UNI-14) | n/a | n/a accepted | no lockfile change | — |
| UNI-16 | n/a, build inputs only, no operator step | n/a | n/a accepted | no host config or runbook step changes | — |
| All other UNI, AUTH, TEN, FE, MON, REC, FILE, EVT rules | n/a, no application code | n/a | n/a accepted | `git diff --name-status`: Dockerfile, predeploy Dockerfile, one test, DECISIONS | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-140-e43fd961` at e43fd961 | created, reviewed, removed without `--force` |
| `git diff --check fb49783...e43fd96` | clean |
| `make install lint typecheck test host-test` | pass: Semgrep 21 / 0 findings, mypy 233 files, pytest 1730, vitest 4, host tests 854 |
| `docker build` of both Dockerfiles from the head | both built |
| `apk info` in both images | krb5-libs-1.22.3-r0 (both), libxslt-1.1.43-r4 (dump) |
| `aquasec/trivy:0.75.0 image --severity HIGH,CRITICAL --exit-code 1` on both | exit 0 each |
| Runtime checks in the images | dump: pg_dump 17.11, age v1.3.2, `python3 -I` ssl import, user 10003; app: Django 5.2.17 |
| `check_dockerfile` probe with nine edits to the apk line | 5 accepted (weak floors, duplicate, single package, line removed, python fetch), 4 rejected; see P3 |
| CI on this head at the end of the round | `security`, `image`, `host` SUCCESS; **`checks` still IN_PROGRESS** |
| Cleanup | both local images removed; worktree removed |

### Residual risks and test gaps
- **CI `checks` was still running when I finished.** My local `make lint typecheck test host-test` pass on the same head, but the builder must see `checks` green on the exact head before `approved 140` (DECISIONS 2026-10-10).
- **Review tier:** standard, not the deep tier the PR asked for. The change is small and I verified the behaviour by building and scanning, not only by reading; I still did not give the backup path a deep-tier read.
- **Not run by me:** `host-test-live`, `secrets-test`, `e2e`. The dump image was built and run only for its version checks, not through a real `predeploy` dump.
- **Builder's 6 mutants on the test rule:** not re-run; my probe above found the rule's gaps (P3).
- The fix lasts until upstream rebuilds. Someone must notice: the marker is greppable and the DECISIONS entry says to check on every base-image digest bump.

### Required before merge
- None. Process: `checks` green on the exact head before `approved 140`.

### Deferred conditions
- None.

### Optional improvements
- The two P3s above.

### Handoff block (only when handing off)
Not requested.
