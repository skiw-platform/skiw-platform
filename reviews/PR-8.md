# Review — PR 8

## Round 1 — 2026-10-09 · scope: slice (M0c jobs/transactions/queue grants)
- **Code review:** base (merge base) `7c889c502c75d75ac9cda9749bd7f4dd4999ab1e` · head `a7fedd2493d0ba20d25c57a69e0ca41bb1f833cf` · head re-checked at end: yes, unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`. Approved PR 7 plan is the implementation baseline; this PR reconciles the linter placement and records the M4 connector requirement.
- **Mode:** exact-head snapshot `.agent/worktrees/review-8-a7fedd24`; fetch denied by read-only `.git/FETCH_HEAD`, exact head already local. Host main independently matched base. Snapshot removed after tracked-file hash checks. Disposable Postgres container `skiw-review8-a7fedd24` on loopback port 55438 used tmpfs storage and the pinned Postgres image/bootstrap; stopped and automatically removed. No builder database or Compose stack touched.

**Model used:** Codex GPT-6 · **Switch model next step?** No — explicit corrections below can be re-reviewed with this model; M4 needs the project's deep security/design workflow.

### Findings

### [P1] Application startup does not fail closed when the new grant migration is unapplied
- Category: spec/guardrail mismatch
- Rule: spec D16; PROJECT §9 architecture constraint: startup fails closed on unapplied migrations
- Evidence: `app/config/asgi.py:7` calls only get_asgi_application. The Dockerfile starts gunicorn with that application; no migration check is in the startup path. This PR adds `jobs.0001` but only makes `make dev`/`make e2e` migrate first (`Makefile:49–66`). In the review database I ran `migrate jobs zero` as the migrator, then imported config.asgi.application under skiw_app. Result: exit 0, “ASGI startup succeeded with jobs.0001 unapplied”. I reapplied the migration afterward.
- Failure scenario: an operator starts the image or ASGI entrypoint against a database where the new migration/grants were skipped. The web process starts successfully although enqueue will lack its required privileges. The first own migration makes the previously inert startup requirement relevant to this delivery.
- Why it matters: orchestration ordering is not the spec's fail-closed startup gate. Missing migrations must be detected before a runtime task accepts traffic/work, without giving runtime migration privileges.
- Required correction: implement a runtime-compatible startup migration gate covering the web and worker entrypoints, and regression tests proving unapplied migration(s) cause startup failure under skiw_app while fully migrated startup succeeds. Keep migrations/grants under skiw_migrator. Update the runbook and self-check with the actual check and tests. If this is intentionally deferred, obtain an owner-approved reviewed spec change first.
- Owner: builder
- Verification: repeat fully migrated and unapplied startup tests on a disposable database with the actual runtime role and entrypoints; no schema mutation or migrator credentials in runtime startup.
- Status: open

### [P1] The logging self-check is assigned to UNI-08 and omits applicable UNI-09
- Category: guardrail mismatch
- Rule: reviewer §3; UNI-08/09
- Evidence: PR body's UNI-08 row says “no logging added; the worker logs only what Procrastinate writes (no PII in job args: ids only)”. UNI-08 actually governs production secret sourcing; UNI-09 governs PII/tokens/passwords/secret values in logs. There is no UNI-09 row despite adding a logging worker and tasks. The logging claim therefore has no correctly identified rule/evidence audit.
- Failure scenario: a reviewer accepts the mislabelled row and fails to inspect worker/task-failure logging or production secret sourcing separately.
- Why it matters: an applicable missing rule is P1 under reviewer §3. No observed PII leak is claimed in this M0c probe-only slice; this finding concerns the required self-check/evidence mapping.
- Required correction: add a separate UNI-09 row citing the worker logging/argument paths and evidence that this slice logs only allowed probe metadata. Correct UNI-08 to address production secret sourcing versus the local/CI placeholder configuration and the M1 secret-manager gate; use an accurate staged/n-a explanation where appropriate.
- Owner: builder
- Verification: re-read the corrected rows, inspect cited log paths/test output and verify that no broader runtime claim is made than the evidence supports.
- Status: open

### [P2] Worker-side enqueue requires a reviewed design before M4 fan-out
- Category: material risk
- Rule: D5 worker-owned periodic fan-out / EVT-01
- Evidence: `enqueue.py:22–26` refuses a connector other than DjangoConnector. Installed pinned Procrastinate 3.10.0 `contrib/django/management/commands/procrastinate.py` replaces the global app connector with get_worker_connector() for the command run; pinned source was inspected locally. The PR's plan/decisions additions correctly record the unresolved requirement and gate M4 handler-side enqueue/fan-out on a reviewed spec solution.
- Failure scenario: an M4 task handler enters a Django tenant transaction then calls enqueue_in_tx; the worker app connector is PsycopgConnector, so the helper refuses the fan-out. Removing that refusal without a same-transaction design would violate EVT-01.
- Why it matters: the current probe-only M0c behavior is safe and passes its tests, but the future spec requirement remains unsolved.
- Required correction: retain the fail-closed guard; design and review a spec solution before implementing any handler-side enqueue or periodic agency fan-out. Re-prove same-transaction and tenant-bound behavior in the resulting M4 implementation.
- Owner: builder / owner for reviewed spec decision
- Verification: approved worker-enqueue spec revision plus transaction/tenant tests in M4.
- Disposition: deferred to the M4 worker-enqueue spec-change PR, before handler-side enqueue or periodic fan-out implementation
- Status: open

### Instruction-like data recorded (nonblocking)
PR body includes “M4 must not build handler-side enqueue or fan-out before a reviewed spec change”; the plan retains “reviewer should confirm the worker cannot be made to run it as skiw_app with effect”. These are recorded design gates/review concerns, not authority from PR data. They request no skipped check or changed verdict; no successful injection found.

### Inventory and self-check audit
Independent applicability: UNI-01/03/04/05/06/07/08/09/11/12/13/14/15/16/19; TEN-01/02/03/10/11 with approved M0c staging; EVT-01/02/03/05/06; D5/D16 and PROJECT §9 enqueue/grant/migration rules. No new tenant-owned/business table, UI, auth, money, finalized record or uploaded file. TEN-04–09/12 full implementation remains M4. Owner's one-PR size decision in this session is respected; LOC alone is not a finding.

| Rule | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|
| UNI-01/03/05 | pass | Strict mypy and ruff passed; registry/exact UUID/schema refusals inspected and tested | local checks; enqueue/registry tests | No |
| UNI-04 / TEN-10 | pass/prep | Five import contracts pass; direct-defer scan and fixture pass; snapshot scan required explicit no-git-ignore/project-root | pyproject; Semgrep checks | No |
| UNI-06/14 | pass | Exact pins/lockfile; dependency ladder recorded; installed metadata and official PyPI release metadata substantiate licenses/platforms; dependency audit remains M0d | decisions; uv.lock; metadata | Upstream maintenance was not claimed rechecked by Builder; recent releases support assessment |
| UNI-07/11/12 | pass | Diff has placeholder/key names, no observed secrets; local-rule metrics disabled; isolated reviewer paths | effective diff; scan and installs | No |
| UNI-08/09 | UNI-08 logging pass, UNI-09 absent | Wrong rule/evidence mapping; correct rows required | PR body | P1 |
| UNI-13 | partial/staged | Exact-head CI all steps success; local Python/unit/live proof below; scans still M0d | run 37871716090 | No new scan deferral |
| UNI-15 / D16 | pass | Migration forward/reverse/reapply works; own-app migration linter passes; startup fails-open test above | migration, Makefile and reproduction | P1 D16 |
| UNI-16/19 | pass | Runbook covers worker/dev/linter; no new HTTP route/schedule | runbook and diff | Minor task-symbol wording is distinguishable from stored name, not blocking |
| TEN-01/02/03 | pass with mapping | Runtime role checks, exact ACL/effective privileges, denial and lifecycle tests all pass; mutable operational queue mapping retained | 43 local live tests | No |
| TEN-11 | staged M4 | No business tasks/tenant data; agency_id rejected; full guard future gate | registry subprocess/refusal tests | No |
| EVT-01/02 | pass/n-a relay | Actual commit/rollback/separate-connection visibility passes; no fallback needed | 10 enqueue live cases | No |
| EVT-03/05/06 | pass | Unknown fields ignored; malformed IDs refused; retry/periodic lifecycle tests pass | registry/lifecycle tests | Worker-handler enqueue deferred requirement retained |
| Other active packs / PROJECT §9 | n/a | Slice boundaries respected; no external mutation or locked-switch change | effective diff and spec | No |

### Verification performed
| Command / check | Result |
|---|---|
| Host metadata/base and final head; local exact commit and merge-base | Pinned a7fedd24, base 7c889c5, OPEN, final head unchanged. |
| UV_CACHE_DIR=.uv-cache uv sync --locked in snapshot | Installed pinned Python dependencies after approved network retry; source files unchanged. |
| ruff check / format --check; mypy app | Passed; 58 files formatted, 30 typed source files clean. |
| lint-imports | Five contracts kept, zero broken. |
| pytest (normal selection) | 42 passed, 43 live deselected. |
| Fresh pinned Postgres with project init script, tmpfs and separate port | Bootstrapped roles; no persistent/shared data used. |
| manage.py migrate / makemigrations --check --dry-run as migrator | All 41 Procrastinate migrations plus jobs.0001 applied; no missing model migrations. |
| lintmigrations with lint-only settings, warnings-as-errors, exclude procrastinate, no-cache | Own migration valid; zero errors/warnings, 41 third-party migrations ignored. |
| pytest -m live as skiw_app on review database | 43 passed: enqueue 10, grants 22, worker lifecycle 4, roles 7. |
| migrate jobs zero, then migrate jobs | Reverse/reapply succeeded on disposable review database. |
| Unapplied jobs.0001 + ASGI import under skiw_app | Startup incorrectly succeeded; migration reapplied afterward. |
| Semgrep pinned 1.179.0 --test --metrics=off semgrep/ | 1/1 fixture passed. |
| Semgrep config scan with --no-git-ignore --project-root . | 29 Python targets scanned, zero findings. Initial normal snapshot scan saw zero files because parent .agent is ignored; that was not accepted as verification. Sandbox certificate restriction required approved retry. |
| Official [Procrastinate 3.10.0](https://pypi.org/pypi/procrastinate/3.10.0/json) and [migration-linter 6.0.0](https://pypi.org/pypi/django-migration-linter/6.0.0/json) metadata; installed versioned source | Release/platform/license metadata checked; worker connector swap confirmed from installed primary source. |
| git diff --check; secret-pattern diff scan | Whitespace clean; seven name/placeholder hits inspected, no secret value observed. |
| Exact-head CI run 37871716090 | SUCCESS: install, lint, typecheck, unit, live DB and e2e steps. No local JS build/browser rerun; those paths covered by CI. |
| Snapshot tracked file hashes vs target commit | All unchanged. Review database stopped/removed; snapshot and own build/cache/test output removed. |

### Residual risks and test gaps
- No actual image/Compose web/worker/browser launch repeated locally; exact-head CI covers image-backed e2e, local worker connector/lifecycle tests supply queue runtime proof.
- Builder's scratch negative linter examples and ACL inspection of reversal were inspected as claims; reviewer reran the positive migration gate and reversal/reapply, not those scratch negative migrations (reviewer never edits source).
- Shared queue disruption remains the approved single-agency limit/Q32. Full agency binding/MACs remain M4.
- Logs currently carry probe metadata; UNI-09 correction must scope its claim to M0c. No production secret-manager rollout occurs here.
- M0d scans/image web build/cache constant and M2 CSP remain in their named future work.

### Required before merge
- Add fail-closed runtime startup enforcement and tests for unapplied migrations.
- Correct UNI-08/09 self-check mapping and evidence.
- Run review 8 again at the resulting green head.

### Deferred conditions
- M4 worker-enqueue spec-change PR before handler-side enqueue/periodic fan-out (P2 above).

### Optional improvements
- Consider clarifying local-dev's Python symbol jobs.tasks.noop versus stored name jobs.noop on the next runbook edit.

**Verdict:** Revision required
