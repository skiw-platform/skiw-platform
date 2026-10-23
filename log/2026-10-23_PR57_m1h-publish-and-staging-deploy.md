# PR 57 — ci: M1h publish by digest, gated staging deploy job and scripts/deploy-prod

- **Merged:** 2026-10-23T10:06:15Z (GitHub) · **Merge commit:** `70fe753d44138158d1c87f906a133e0147a755be` · **Branch:** `ci/m1h-publish-and-staging-deploy` (final head `68106df9ecec9754669ad7c18e736a6bc387b3ae`)
- **Gate breaches:** none (owner-approved size: one PR, about 1,354 lines, about 700 tests)
- **Approval receipt:** `reviews/PR-57.receipt` on `agent-logs`, committed 2026-10-23T09:37:36Z (before the merge); names head `68106df…`, review `reviews/PR-57.md` (hash `39b562bf…`, equal to the archived copy), CI green on that exact head (run 39929903286: checks, host, image, security).
- **Merge evidence:** `gh pr view 57` → MERGED, merge commit `70fe753`, final head equals the reviewed head of Round 1; `git merge-base --is-ancestor 70fe753 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved with conditions (Round 1)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1h (host proof M1k)

## What changed
CI `publish` job on push to `main` (after all four gate jobs; only job with `packages: write`): builds the app image once, adds `org.opencontainers.image.revision`, `skiw.migration-head`, `skiw.contract-migrations` by a `FROM` build (labels from `skiw_host.labels`, same parser as `skiw-deploy`), Trivy gate, image-ID check, push to `ghcr.io/skiw-platform/skiw-platform`, digest from `RepoDigests`, artifact `image-digest` (`digest.txt`). Dump image `ghcr.io/skiw-platform/skiw-predeploy` publish gated by repository variable `SKIW_PUBLISH_PREDEPLOY` (off: the image fails Trivy). `deploy-staging` gated by `SKIW_STAGING_DEPLOY` (off), pinned staging host key, bounded, never cancelled once running. Pull-request runs cancel older ones; `main` runs do not cancel a running one. `scripts/deploy-prod`: owner wrapper checking a green `main` push run, commit on `main`, exactly one unexpired `image-digest` artifact equal to the argument, then pinned SSH to production; config in `~/.config/skiw/deploy-prod.env`. Gates cover `scripts/` (ruff, mypy, Semgrep).

## First run on `main`
- Run 39936702015 on `70fe753`: checks, host, image, security, **publish** success; deploy-staging skipped (variable unset).
- Artifact `image-digest`: `digest.txt` = `sha256:91b0cb1c732d27b9be5414f463e945b300c86835991440ed16822c7392b2f6f2` (exactly one digest, no newline).
- Not checked here: package visibility and repository link (the builder's `gh` token has no `read:packages`).

## Review rounds
- R1: Approved with conditions. P2 lost journal and deploy-log line on a dropped SSH session (merged `record()` prints to stderr first) → deferred. P3 "never cancelled" wording (a waiting run is replaced by a newer push) → optional. P3 no test for the `labels` 1 MiB input bound → optional.

## Deferred conditions
- P2 `record()` stderr before journal and deploy log → the next PR (dump image fix), before any deploy can run.
- Optional: P3 wording in DECISIONS M1h (5), `ci.md`, `deploy.md`; P3 test for `labels.py` `MAX_INPUT`.

## Decisions worth keeping
- Dump image fails Trivy (Debian 13.7 base 66, gosu 26, age 4). A probe on `postgres:17.11-alpine` without gosu, `python:3.12.15-alpine`, age v1.3.2 built from source scanned clean. Owner chose the fix as the next separate PR.
- `compare/<sha>...main` must be `ahead` or `identical` with `behind_by` 0 (the brief had it the wrong way round).
- Owner to-do before CI staging deploys: dump image fix, then `SKIW_PUBLISH_PREDEPLOY` and `SKIW_BACKUP_IMAGE`; staging `SKIW_SSH_POLICY=fail2ban` (G7); staging key and `STAGING_DEPLOY_KEY` (G6/T25); read token for both packages (G10); staging address and host key in `staging.env`; then `SKIW_STAGING_DEPLOY`.

## Follow-ups
- Decisions are in the merged DECISIONS entry "2026-10-23 — M1h"; nothing missing.
