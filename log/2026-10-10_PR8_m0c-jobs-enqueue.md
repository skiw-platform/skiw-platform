# PR 8 — feat(jobs): M0c queue, enqueue_in_tx subset, queue grants

- **Merged:** 2026-10-09T09:58:53Z (GitHub) · **Merge commit:** `a70d1e1656a2461962b035b815676cb40ac0d662` · **Branch:** `feat/m0c-jobs-enqueue` (final head `2aeffa64bef5eb0ff04dbdae784d0229502253c4`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-8.receipt` on `agent-logs` (commit `27515ed`, written 2026-10-09T09:46:59Z, before the merge); names head `2aeffa6…` and review-file hash `5a8293384a4663d525f96f1dc6fbffea2abda1a7`; the archived review `reviews/PR-8.md` (log-branch commit `1f1b086`) has the same hash.
- **Merge evidence:** `gh pr view 8` → state MERGED, mergedAt 2026-10-09T09:58:53Z, merge commit `a70d1e1`, final head `2aeffa6` (equals the reviewed head of Round 2); `git merge-base --is-ancestor a70d1e1 origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder); implementation by Claude Opus 5.5 (deep tier subagent) · **Final verdict:** Approved with conditions (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8 (`67e36a52…`) · **Plan:** `docs/plans/2026-10-05-m0-scaffold.md` · **Milestone:** M0c

## What changed
Procrastinate 3.10.0 Django integration with same-transaction enqueue (`jobs.enqueue_in_tx`, M0c subset: synchronous `.defer()` through `DjangoConnector`, uuid ids as strings, refusals before any SQL, probe task `jobs.noop` only). Migration `jobs.0001` grants `skiw_app` exactly the spec §4.1 queue privileges (and SELECT on `django_migrations`), run as `skiw_migrator`. Registry with explicit task names, Semgrep ban on direct `.defer()`, import-linter contracts, `django-migration-linter==6.0.0` gate in `make migrate`, Compose `worker` service via the new `runworker` command, and a startup gate that refuses to start web or worker against unapplied migrations. 49 live tests run as `skiw_app` (enqueue, grant audit, worker lifecycle, startup gate, roles).

## Why
Spec D5 (owner ASK-1 a, 2026-10-06), owner TEN-03 queue mapping (2026-10-07), plan M0c (PR 7). Result of the key risk test: the same-transaction guarantee holds with `DjangoConnector`; the `job_outbox` fallback was not needed.

## Review rounds
- R1 (Revision required): [P1] startup did not fail closed on unapplied migrations (D16) → `jobs.startup.require_migrated()` in `config.asgi` and `runworker`, run in a short thread because the ASGI server imports the app inside a running event loop; 6 startup-gate tests (`2aeffa6`). [P1] UNI-08/UNI-09 self-check rows mislabelled → corrected, UNI-09 added. [P2] worker-side enqueue needs a reviewed design before M4 → deferred.
- Earlier, before review: first CI run failed in `make e2e` (`docker compose --wait` rejects the worker with a disabled healthcheck) → e2e starts `app` only (`a7fedd2`).
- R2: Approved with conditions.

## Deferred conditions
- [P2] M4 worker-enqueue spec-change PR (reviewed spec solution, then worker-side same-transaction and tenant tests) before any task-handler enqueue or periodic agency fan-out. The `enqueue_in_tx` refusal of a non-`DjangoConnector` stays until then.
- Standing: M0d (CI scans, image web build stage, named asset cache constant), M1 (production secret manager, TLS flag validation), M2 (CSP nonce), Q32 (queue isolation and job retention).

## Decisions worth keeping
- Task names are explicit and stored in every job row (`jobs.noop`).
- `lintmigrations` runs in `make migrate` (needs a database), so CI runs it through `make test-live`; the linter does not understand GRANT/REVOKE, so privileges are proven by the grant audit and lifecycle tests.
- Startup gate lives in `jobs.startup`; `skiw_app` has SELECT only on `django_migrations`.
- Lesson: run `make e2e` after any Compose or Makefile change; test entrypoints inside an event loop the way the ASGI server loads them.
- All M0c decisions are in `docs/DECISIONS.md` (entry 2026-10-09).

## Follow-ups
- M0d next (standard tier). ASK-3 and ASK-4 asked of the owner before M0d.
- API Anything / FAME design-time spike: parked until the Browser Bridge milestone, only with the owner's written yes.
- UI kit order (emilkowalski/skills, shadcn/ui, SmoothUI): needs a decisions entry and a spec D2 change before the product frontend.

## Appendix — final review round
## Round 2 — 2026-10-09 · scope: slice (M0c startup gate and self-check fixes)
- **Code review:** base (merge base) `7c889c502c75d75ac9cda9749bd7f4dd4999ab1e` · head `2aeffa64bef5eb0ff04dbdae784d0229502253c4` · head re-checked at end: yes, unchanged and OPEN.
- **Spec:** v1.8 at `docs/specs/2026-10-05-skiw-platform-stack-design.md`, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, unchanged.
- **Plan:** `docs/plans/2026-10-05-m0-scaffold.md`, hash `a8153570c81970e3388c267cdbc99a597779d48f`; worker command and linter placement reconciled.
- **Mode:** exact-head snapshot `.agent/worktrees/review-8-2aeffa64`; fetch denied by read-only .git/FETCH_HEAD; exact head already local. Host main matched recorded base. Source integrity verified by tracked-file hashes. Snapshot removed; isolated tmpfs Postgres container `skiw-review8-2aeffa64`, port 55438, stopped and automatically removed. No builder stack/database touched.

**Model used:** Codex GPT-6 · **Switch model next step?** No for archive/merge workflow; M4 worker-enqueue design needs the project's deep-tier review.

### Findings
No blocking findings or new defects. Both Round 1 P1 findings are resolved. The existing P2 condition remains deferred as below.

#
