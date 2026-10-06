# PR 1 — chore: M0a Django skeleton, /healthz, tooling, Compose

- **Merged:** 2026-10-06T13:10:05Z (GitHub) · **Merge commit:** `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · **Branch:** `chore/m0a-django-skeleton` (final head `fbde411df3be568dd8c09d5052c9633aa9e4abdf`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-1.receipt` on `agent-logs` (commit `f5978e3`, committed 2026-10-06T13:07:47Z, before the merge); names head `fbde411…` and review-file hash `e5d884fca05ebd1fcfadb1e281eb04647f8d831f`; the archived review `reviews/PR-1.md` (log-branch commit `a11ede5`) has the same hash.
- **Merge evidence:** `gh pr view 1` → state MERGED, mergedAt 2026-10-06T13:10:05Z, merge commit `b6abd9f`, final head `fbde411` (equals the reviewed head of Round 6); `git merge-base --is-ancestor b6abd9f origin/main` succeeded; `origin/main` log shows "Merge pull request #1".
- **Drafted by:** Claude Sonnet 5.5 (builder); M0 plan by Claude Opus (deep tier) · **Final verdict:** Approved with conditions (round 6; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 (`cf57625d`) · **Plan:** `docs/plans/2026-10-05-m0-scaffold.md` · **Milestone:** M0a (first of four M0 scaffold PRs)

## What changed
Django 5.2 ASGI skeleton with a database-free `GET /healthz`, a settings helper that fails closed, ruff / mypy strict / import-linter / pytest, a pinned-by-digest non-root Dockerfile, Docker Compose (Postgres 17.11 plus app) creating the `skiw_migrator` and `skiw_app` roles, Makefile, `.env.example`, a local-dev runbook and decisions entries. During review a minimal GitHub Actions workflow was added: install, lint, typecheck, unit tests, live database role checks and a Compose `/healthz` smoke test, with actions pinned by SHA and the runner pinned to `ubuntu-24.04`.

## Why
First PR of the scaffold milestone (spec §9 M0): fixes layout, toolchain and import boundaries that M0b–M0d and M1+ build on, and puts the TEN-01/02 role split in place from the first commit.

## Review rounds
- R1 (Blocked): [P1] default local database URL gave host-run app code the migration role → `DATABASE_URL` now `skiw_app`; new `MIGRATION_DATABASE_URL` (`skiw_migrator`) injected only by `make migrate` (`00c1dbb`).
- R1: [P1] database URL parsing discarded the required TLS settings → parser keeps `sslmode`/`sslrootcert`/`sslcert`/`sslkey`/`sslcrl`, rejects other options, `DJANGO_REQUIRE_DB_TLS=1` forces `verify-full`/`verify-ca`; tests added (`4da0d0c`).
- R1: [P2] M0c plan still says the app runs as the migration role → deferred to the M0c PR.
- R2–R4 (Blocked, no source findings): the reviewer's sandbox could not run Docker or Postgres, so TEN-02 (hard) lacked independent runtime proof. Owner chose option B → CI added with seven live role tests (`28dbd6a`).
- R2: [P2] invalid `DJANGO_REQUIRE_DB_TLS` value is treated as false → deferred to the M1 PR.
- R5: [P2] CI used a floating runner label (UNI-14) → `ubuntu-24.04`, recorded in the decisions log (`fbde411`).
- R6: Approved with conditions.

## Deferred conditions
- M0c PR: reconcile the M0 plan with `skiw_app` queue grants (R1 P2).
- M1 PR, before the staging deploy: reject invalid TLS flag values, set strict TLS in the CDK configuration, test an invalid flag and prove the live connection uses TLS (`pg_stat_ssl`) (R2 P2).

## Decisions worth keeping
- Runtime URL (`DATABASE_URL`, `skiw_app`) and migration URL (`MIGRATION_DATABASE_URL`, `skiw_migrator`) are separate; only `make migrate` reads the migration URL.
- Database URL accepts only the listed libpq TLS options; strict TLS is enforced with `DJANGO_REQUIRE_DB_TLS=1` for non-local deployments.
- Independent runtime evidence for hard rules comes from CI when the reviewer's sandbox cannot run Docker; CI runner and actions are pinned (`ubuntu-24.04`, action SHAs).
- Local database is published on host port 5433 because 5432 is used by another project on the owner's machine.
- All recorded in `docs/DECISIONS.md` on `main` (entries dated 2026-10-05 and 2026-10-06).

## Follow-ups
- M0b `feat/m0b-web-shell` next; the owner must confirm the pasted answers first (Node 24, `<html lang="en-MY">`, ASK-1 option a, ASK-6 option b).
- D5 wording change (synchronous `.defer()` inside `enqueue_in_tx` on the Django connection; UUID ids converted to strings) before M0c merges; owner to choose spec revision or an owner-approved decisions entry.
- M0d extends the CI workflow (web, e2e, secret scan, dependency audit, image scan).
- Owner to enable branch protection with required checks on `main` after M0d if the account supports it.
- The reviewer environment could not create `git worktree` checkouts; reviews used a separate clone.

## Appendix — final review round
<!-- Copied in full from .agent/reviews/PR-1.md (that file is local only). -->

## Round 6 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `fbde411df3be568dd8c09d5052c9633aa9e4abdf` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings
- No new findings. R5 P2 is resolved: `.github/workflows/ci.yml:17` uses the explicit `ubuntu-24.04` runner label, and `docs/DECISIONS.md:10` records the choice. GitHub reports `ci / python` success at this exact PR head (run `37445808806`).
- R1 P1 runtime-role and TLS-option corrections remain resolved. The R1 P2 M0c plan role drift and R2 P2 invalid TLS flag remain deferred to their named milestones.

### Self-check audit
- The R1 applicability list and R5 audit remain current: the only new changes are the runner label and its decision entry. The UNI-14 mismatch is corrected. The committed workflow still runs the live role checks and Compose smoke test; full UNI-13 gates remain scheduled for M0d by the approved plan.

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin` | Denied writing `.git/FETCH_HEAD` (`Operation not permitted`). The exact head object was already local; GitHub independently reported the same head SHA and open PR state. |
| Host PR and CI check | PR open at `fbde411df3be568dd8c09d5052c9633aa9e4abdf`; `ci / python` passed at that head. |
| `git worktree add --detach` | Still denied creating `.git/worktrees`. Used a separate local clone at `.agent/worktrees/review-clone-1-fbde411d`, detached at the exact host head; no tracked or staged changes. |
| Base and patch | Merge base remains `2425983`; only `.github/workflows/ci.yml` and `docs/DECISIONS.md` changed since R5; `git diff --check` passed. |
| Workflow and decision inspection | Versioned `ubuntu-24.04` label and SHA-pinned actions present; decision entry matches. |
| `docker compose --env-file .env.example config --quiet` | Passed in the isolated clone. |
| Independent lint, typecheck and unit tests | Not repeated: R5 ran these on the same application source, and this head changes only the workflow runner label and decision text. The new exact head has a successful host CI check. |

### Residual risks and test gaps
- Local Docker/PostgreSQL remains unavailable in this sandbox; the successful CI workflow is the live role and Compose evidence. Detailed Actions step logs remained unavailable through the GitHub API.
- This is approval of M0a only. M0c must reconcile queue grants and the plan; M1 must validate the TLS flag and prove live TLS before staging deploy.

### Required before merge
- None for this M0a slice.

### Deferred conditions
- M0c: reconcile the plan with `skiw_app` queue grants (R1 P2).
- M1 before staging deploy: reject invalid TLS flag values and prove live TLS (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the next step is the builder's approval archive.
**Verdict:** Approved with conditions

