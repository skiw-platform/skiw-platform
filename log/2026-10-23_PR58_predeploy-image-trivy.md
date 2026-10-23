# PR 58 — fix(infra): dump image passes the Trivy gate; deploy log written before stderr

- **Merged:** 2026-10-23T11:16:35Z (GitHub) · **Merge commit:** `9ad73e8d2cddbefc33cabde4e792682971790c66` · **Branch:** `fix/predeploy-image-trivy` (final head `a9e97284e137f22840e71eb48c5c978e8525d73f`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-58.receipt` on `agent-logs`, committed 2026-10-23T11:15:49Z (before the merge); names head `a9e9728…`, review `reviews/PR-58.md` (hash `a14f6268…`, equal to the archived copy), CI green on that exact head (run 39942227650: checks, host, image with the dump image Trivy scan, security).
- **Merge evidence:** `gh pr view 58` → MERGED, merge commit `9ad73e8`, final head equals the reviewed head of Round 1; `git merge-base --is-ancestor 9ad73e8 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved (Round 1)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1h follow-up (owner chose a separate PR)

## What changed
Pre-migration dump image on Alpine 3.24, every base by digest: final `postgres:17.11-alpine3.24` with `gosu` removed; Python interpreter and stdlib copied from `python:3.12.15-alpine3.24` (no pip); `age` v1.3.2 built from the checksummed source archive with `golang:1.27.3-alpine3.24` (`CGO_ENABLED=0`, `-trimpath`, `GOFLAGS=-mod=readonly`, `GOTOOLCHAIN=local`). Build-time version checks (pg_dump/pg_restore 17.11, age v1.3.2, Python imports). CI `image` job builds and Trivy-scans the dump image on every PR and push. `record()` writes journal and deploy log before stderr; `say()` contains a failed stderr write and swaps the stream so the exit code is kept (PR 57 P2). Cancel wording corrected; test for the `labels` 1 MiB bound (PR 57 P3s).

## Review rounds
- R1: Approved. Two optional P3: no test for the bootstrap mains' switch to `say()`; the build check imports a fixed module list, not `predeploy.py`.

## Deferred conditions
- none.

## Decisions worth keeping
- Base choice: postgres alpine plus copied Python (all pg client libraries visible to Trivy) over python alpine plus copied pg client (five libraries outside any apk package).
- Trivy cannot match advisories against `age` itself (module `(devel)`, no VCS data); it scans its dependencies and the Go stdlib.
- A lost stderr line only means the caller did not see it; the journal and deploy log are the record; the exit code is the one the run earned.
- Owner next: set `SKIW_PUBLISH_PREDEPLOY=enabled`; the next push to `main` publishes the dump image and its `predeploy-digest`; then `SKIW_BACKUP_IMAGE` on hosts.

## Follow-ups
- Decisions are in the merged DECISIONS entry "2026-10-23 — Dump image passes the Trivy gate; deploy log written before stderr"; nothing missing.
- Out of scope, noted: `deploy.log` append has no fsync; `docker rm --force skiw-predeploy` without `-v` leaves an anonymous volume (base `VOLUME`); `.github/dependabot.yml` does not cover `infra/host/backup/predeploy`; `skiw-deploy-ssh`, `apply`, `check-hardening` use raw `print`; the two optional R1 P3s.
