# PR 32 — feat(app): secret files and /readyz (M1b-1)

- **Merged:** 2026-10-13T12:17:40Z (GitHub) · **Merge commit:** `3bac2cbdfa14acb0b823848070db73c66dbcebce` · **Branch:** `feat/m1b1-app-readyz` (final head `fd1a2495276d997a9b8079c88ba23e35882c844c`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-32.receipt` on `agent-logs` (written before the merge); names head `fd1a249…`, review `reviews/PR-32.md`, CI green on that exact head (run 38390001345: checks, host, image, security).
- **Merge evidence:** `gh pr view 32` → MERGED, mergedAt 2026-10-13T12:17:40Z, merge commit `3bac2cb`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 3bac2cb origin/main` succeeded; `app/jobs/views.py` is on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1b-1 (app part of plan M1b; owner split the plan's M1b in two on 2026-10-13)

## What changed
`app/config/{env,settings}.py` read `DJANGO_SECRET_KEY_FILE` (`v<n>:<base64>` lines; newest is `SECRET_KEY`, older are `SECRET_KEY_FALLBACKS`) and `DATABASE_PASSWORD_FILE`; malformed or doubled sources stop startup without echoing content. New `/readyz` (`app/jobs/views.py`): 200 `ok` only when the connection is `skiw_app` and no migration is unapplied, else 503 `not ready`. `jobs.startup._pending` renamed `pending_migrations()`. Tests, `docs/runbooks/local-dev.md`, DECISIONS entry (M1b-1).

## Review rounds
- R1 (Revision required): [P1] self-check lacked UNI-08, UNI-16, UNI-19 rows → added. [P2] runbook still said `.env` only and `DJANGO_REQUIRE_DB_TLS=1` on all non-local deployments → scoped to local/CI, host TLS exception stated (H6).
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- `/readyz` lives in `app/jobs/views.py` because `health` and `jobs` stay independent and `jobs` is on the TEN-10 allow-list.
- M1b-2 (Compose stack, env files, Compose config tests, Makefile line, local-dev host-test row) is next. Its code exists as a local WIP commit on branch `feat/m1b-compose-stack` and is rebuilt on `main`.
- Port 5433 on this machine is held by another project's container; local live tests need a different `SKIW_DB_PORT`.
