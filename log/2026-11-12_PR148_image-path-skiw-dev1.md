# PR 148 — ci: image and repo paths follow the move to skiw-dev1

- **Merged:** 2026-11-12 (05:53:11 UTC) · **Merge commit:** f319bd9ff5fb49a1349963541329ea59ef161124 · **Branch:** ci/image-path-skiw-dev1 (final head 26a1124ebf48b6d038fb496b2547ce9d5c15556a)
- **Gate breaches:** none. The review's final round (R1) head SHA equals the PR's final head; the receipt (`reviews/PR-148.receipt`, 2026-11-12T05:52:14Z, review-file hash 273a5ee, review commit 225f511) precedes the merge by 57 seconds.
- **Approval receipt:** `reviews/PR-148.receipt` on agent-logs.
- **Merge evidence:** `gh pr view 148` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-12T05:53:11Z, merge commit f319bd9; reachable from fetched origin/main.
- **Built by:** the Sonnet 5.5 builder (mechanical rename, standard tier) · **Reviewed by:** Claude Opus 5.5 (deep tier), one round · **Final verdict:** Approved (round 1)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** none · **Milestone:** none (between M3h and M3i)

## What changed
Image names `ghcr.io/skiw-platform/{skiw-platform,skiw-predeploy}` became `ghcr.io/skiw-dev1/...` in `ci.yml` (`IMAGE`, `PREDEPLOY_IMAGE`), `infra/host/env/{ci,staging,production}.env`; repo name `skiw-platform/skiw-platform` became `skiw-dev1/skiw-platform` in `scripts/deploy-prod` (`REPO`, the provenance check), four host tests, and the deploy, ci and host-rebuild runbooks. New paragraph: `ghcr_read_token` must read `skiw-dev1` packages. DECISIONS "2026-11-12 — Image paths follow the repo". +47/-34 over 13 files. M1 plan and DECISIONS history left unchanged on purpose.

## Why
First real `publish` run on the new organization (run 43142490809, `2c19338`) failed at "Push by digest": `denied: permission_denied: The requested installation does not exist.` The job token can only write its own organization's packages.

## Review rounds
- R1 (head 26a1124): Approved, P3 only. Reviewer re-ran `make host-test` (854 passed) and killed one mutant (`REPO` reverted: 17 failures in `test_deploy_prod.py`). PR 147 P3 #1 (incomplete path list) resolved.

## Deferred conditions
- None. P3s, open: (1) `host-rebuild.md:326` cites DECISIONS 2026-11-11; the image-path entry is 2026-11-12 (fix in the next docs touch); (2) owner checks, no code action (below).

## Decisions worth keeping
- Images live at `ghcr.io/skiw-dev1/...`; naming the repo directly in `deploy-prod` no longer relies on GitHub's post-transfer redirect.
- Host code validates only the shape `ghcr.io/<owner>/<name>`; no organization is hard-coded in it.

## Follow-ups
- **Owner, after merge:** watch the first `publish` on main (run 43164337235 on f319bd9 was running at merge time). If denied again, the cause is an organization setting (Actions workflow permissions or package creation by `GITHUB_TOKEN` in `skiw-dev1`), not code. Optionally check whether the old organization still holds M1 images. Before any host is built, make `ghcr_read_token` read `skiw-dev1` packages.
- Next: M3i (first frontend PR, ask owner first), M3g, M3 gate review (deep tier).
- Open P3s carried: PR 143 regenerate `hold` race test; PR 139 permission matrix (M4-rest); PR 140 P3s and apk layer removal; PR 140 review tier gap.
- Progress page: no milestone change; not republished.

## Appendix — final review round
# Review — PR #148 (ci: image and repo paths follow the move to skiw-dev1)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 1 — 2026-11-12 · scope: deploy path (CI `publish` image names, host env `SKIW_IMAGE_REPOSITORY`, `scripts/deploy-prod` provenance `REPO`, host tests, runbooks, DECISIONS; no app code, setting, migration or dependency)
- **Code review:** base (merge base) 2c193385b7d10b038ee0e86ad7bd5d61551b5608 (= `origin/main`, PR 147 merged) · head 26a1124ebf48b6d038fb496b2547ce9d5c15556a · one commit · +47/−34 over 13 files · head re-checked at end: yes (PR open, main unmoved; detached checkout clean)
- **Spec:** v1.22, unchanged; no hit for the old organization in `docs/specs/`. Rules in play: spec §8.4 H3 (pull by digest from one repository), D15/Q42 (production deploy provenance), UNI-07, UNI-13, UNI-16. Carry-over: PR 147 R1 P3 #1 (incomplete list of old paths).
- **CI:** green on this head: `checks`, `security`, `image`, `host` success; `publish`, `deploy-staging` skipped (PR event). `publish` itself can only be proven by the first push to `main` after merge.

**Verdict:** Approved.
**Model used:** Claude Opus 5.5 (deep tier, as the PR asked) · **Switch model next step?** No. Watching the post-merge `publish` run is an owner check, not review work.

### Carry-over
- **PR 147 P3 #1 (incomplete list of old paths): resolved.** The builder used `git grep` rather than the list. At the head, `git grep 'skiw-platform'` outside DECISIONS, `docs/plans/` and `docs/specs/` leaves only local names: the image tags `skiw-platform:unlabelled` and `:scan`, the runner temp dir, the project name in `pyproject.toml`, `package.json` and `uv.lock`, the spec file name, and the new prose in `host-rebuild.md`. All of these are correct to keep. `staging.env`, `host-rebuild.md` and both host test fixtures are now changed.

### Applicability (reviewer's own list) and self-check audit
UNI-07 (met: no secret in the diff, CI `security` green), UNI-13 (met: CI green, host-test re-run locally), UNI-16 (met: runbooks and the decisions entry say what is still unproven), H3/Q42 provenance (met, see below). AUTH, TEN, FE, MON, REC, FILE, EVT: n/a. I agree with the self-check. Its UNI-01/04/05 rows are right but carry little weight for a rename.

### What I checked on the deploy path
- **`scripts/deploy-prod`:** `REPO` is the only repository name. `run view`, `compare`, the artifact listing and `run download` all build from it (lines 147, 161, 172, 190), and `GH_REPO`/`GH_HOST` are stripped from the environment. Naming the new repo directly no longer depends on GitHub's post-transfer redirect from the old name. That redirect would break if a repo of that name were ever re-created in the old organization, so this is an improvement for provenance. **Mutant:** reverting `REPO` to the old name in a scratch copy fails 17 tests in `test_deploy_prod.py` (the fake `gh` checks `--repo` and the compare path). The guard is real.
- **CI `publish`:** only `IMAGE` and `PREDEPLOY_IMAGE` change. `org.opencontainers.image.source` comes from `$GITHUB_REPOSITORY`, so the label was already right after the move, and the new package links to this repo. Login is `GITHUB_ACTOR` plus the job token with `packages: write`, unchanged.
- **Host side:** `skiw_host/deploy.py:205-209` validates only the shape `ghcr.io/<owner>/<name>`, so no organization is hard-coded in host code. `test_deploy.py:464` still proves a `docker.io/...` repository is refused; the rename keeps that test's meaning.
- **The failure the PR fixes:** run 43142490809 (`push`, `2c19338`): the four gates green, `publish` failed at "Push by digest" with `denied: permission_denied: The requested installation does not exist.` This matches the PR.
- **Env files:** `ci.env` (test-only zero digests), `staging.env`, `production.env` each change one repository value and nothing else.

### Findings

### [P3] #1 The new `host-rebuild.md` paragraph cites the wrong DECISIONS entry
- Category: docs accuracy
- Evidence: `host-rebuild.md:326` says the images live under `skiw-dev1` "(DECISIONS 2026-11-11)". The image-path decision is the new entry "2026-11-12 — Image paths follow the repo"; 2026-11-11 is the repo move.
- Required correction: cite 2026-11-12, or both. Optional; fold it into the next docs touch.

### [P3] #2 Owner checks after merge (no code action)
- The first green push to `main` is the only proof `publish` works. If it is denied again, the cause is an organization setting (Actions workflow permissions, or package creation by `GITHUB_TOKEN` in `skiw-dev1`), not code, as the PR says.
- I could not list packages in either organization (my `gh` token lacks `read:packages`). If the old organization still holds images from M1 runs, nothing points at them now. Deleting them, or confirming there are none, is tidy but not required, since no host exists yet.
- Before the first host is built: `ghcr_read_token` must read `skiw-dev1` packages (the new `host-rebuild.md` paragraph says so).

### Builder's questions
- **Leaving the M1 plan unchanged:** agreed. It records what M1 built, and DECISIONS records the move.
- **Hits the sed pattern could miss:** none found. A plain `git grep 'skiw-platform'` (no anchoring) at the head leaves only the local names listed above.
- **Deep tier:** done.

### Verification performed
Full diff read; `git diff --check` clean; `git grep` for every form of the old name at the head; `deploy-prod`, the CI `publish` job and `skiw_host/deploy.py` repository checks read; failed `publish` run log read; `make host-test` in a detached checkout at the head: 854 passed; one mutant (`REPO` reverted): killed, 17 failures. Not run locally: lint, typecheck, app tests, gitleaks (CI ran them green; the diff has no app code).

### Residual risks
- `publish` is unproven until the first push to `main` after merge.
- Lost-authenticator recovery still unbuilt (owner reset, M4-rest must-have before real data).
