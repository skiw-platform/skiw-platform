# Review — PR 7

## Round 2 — 2026-10-09 · scope: plan-change slice (M0 scaffold, spec v1.8)
- **Code review:** base (merge base) `5f923b320acc744f7993b17e5290da912f4aa905` · head `fbc1740346fd14afe553c71b11d2a548f994a757` · host head re-checked at end: yes, unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, unchanged.
- **Plan:** `docs/plans/2026-10-05-m0-scaffold.md`, hash `6c109bd91430a43047a50a3a49aadb044c7878a1`.
- **Mode:** exact-head snapshot `.agent/worktrees/review-7-fbc17403`; tracked-file integrity verified by commit hashes, then snapshot removed. Fetch denied by read-only `.git/FETCH_HEAD`; exact head present. Host main confirmed the recorded base.

**Model used:** Codex GPT-6 · **Switch model next step?** No for review/archiving; M0c implementation retains the project's deep-tier requirement.

### Findings
No blocking findings or new defects.

### Round 1 resolution audit
| Finding | Result | Evidence |
|---|---|---|
| P1 migration-linter deferral | Resolved | Plan §1 M0c deps, §3 migration checklist, §5 migrate command and §7 risk 5 now require pinned django-migration-linter 6.0.0 in M0c, warnings-as-errors, own-app scope and a destructive negative test. Builder cannot defer it; postponement requires an owner-approved reviewed spec change. Any unsupported RunSQL exception is named-migration-only with a documented reason; grant audit/lifecycle proof remains required. |
| P1 missing self-check rules | Resolved | Host PR body now has individual UNI-04/14/15/16 and TEN-10/11 rows, evidence and plan-versus-runtime distinctions. Re-inspected against the unchanged applicability list and corrected plan. |

**Spec Round 11 condition:** satisfied at the plan-text level by this reviewed plan hash. M0c may proceed only after the standard approval receipt, owner merge and merged-PR log step. The transaction, UUID, grant audit, worker lifecycle, retry/periodic, registry and full M4 guard tests remain implementation acceptance gates; this approval claims none have run yet.

### Self-check audit
Same applicability as Round 1: plan/spec agreement; runtime/migration role design; queue grant mapping; transaction/fallback/retry/periodic design; import/helper boundaries and agency-source staging; pinned dependency/tool and migration/runbook/CI commitments; secrets and local write scope. No new UI, money, auth, finalized-record or file behavior.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| Round 11 / D5 / M0-M4 | Plan alignment | plan pass | Probe boundary, same-alias sync defer, UUID strings, exact grants, skiw_app tests, fallback criterion and M4 handover retained | full pinned plan; spec D5/§4.1/M0/M4 | No |
| TEN-01/02/03 | Roles and privilege design | plan pass | Matches approved runtime/migrator separation and operational-queue mapping | plan §1/§3 | No |
| TEN-10/11 / UNI-04 | Planned enforcement and staging | plan pass | Explicit rows now cite import-linter, Semgrep, probe-only callers, agency-id refusal and M4 guard | PR table; plan M0c and M4 handover | No |
| EVT-01/02/05/06 | Planned transaction/lifecycle/fallback | plan pass | Required tests remain testable; runtime proof correctly deferred to implementation | plan §3/§7 | No |
| UNI-06/14 | Dependencies and pins | plan pass | Linter pin added and dependency ladder required; no dependency installed in this PR | plan deps/§7; PR table | No |
| UNI-15 / D16 | Required migration gate | plan pass | Mandatory M0c gate plus negative test; narrow RunSQL limitation cannot remove the overall gate | plan §3/§5/§7 | No |
| UNI-16 | Runbook commitment | plan pass | Worker, migrate-first dev and Semgrep runbook update stays in M0c | plan docs row; PR table | No |
| UNI-07/12/13 | Secrets/write/delivery | pass; project CI staged | No secret values; allowed review paths; new exact-head CI passed; M0d scans retained | diff checks; run 37864050272 | No |
| Other packs / PROJECT §9 | No changed runtime features | n/a | Appropriate plan-slice scope; locked switches unaffected | full plan/effective diff | No |

### Verification performed
| Command / check | Result |
|---|---|
| Exact commit, merge-base and safe-path snapshot checks | Head present; base 5f923b3; isolated snapshot created. |
| Full updated plan; previous-head → new-head diff | Only migration-gate corrections introduced; queue/staging design retained. |
| Plan/spec hash-object | Plan 6c109bd91430a43047a50a3a49aadb044c7878a1; approved spec 67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3. |
| Effective diff name list and diff --check | Plan file only; whitespace check passed. |
| Project secret-pattern scan of fix diff | Zero hits; unchanged effective-diff name-only hits already inspected in Round 1. |
| [PyPI 6.0.0 metadata](https://pypi.org/pypi/django-migration-linter/6.0.0/json) | Release exists, not yanked, requires Python >=3.9 and lists Django 5.2/Python 3.12 support. Not a claim of tested project compatibility or latest-version status. |
| gh pr view 7 self-check; gh run view 37864050272 | Corrected rows present; CI completed SUCCESS at exact new head. |
| Final host head/state and host main-ref reads | Head unchanged, OPEN; base/main 5f923b3. |
| Snapshot tracked hashes against git ls-tree target | Every tracked file unchanged; snapshot removed. |

### Residual risks and test gaps
- No local package, database, linter or worker tests run for a plan-only PR. Existing CI checks the current application, not future M0c implementation.
- Implementing the own-app lint scope, command registration/configuration, negative test and any narrowly documented RunSQL ignore remains subject to M0c review.
- Exact third-party migration/worker settings, built-in cleanup suppression, privileges and lifecycle execution remain the explicit M0c checks. Full tenancy remains M4.
- ASK-3/4, Q32, M0d scans and M2 CSP retain their original scope.
- Handoff labels Round 1 “Blocked”, but the actual preserved verdict is “Revision required”; both required fixes, so this wording drift changes no gate.
- Nonblocking instruction-like plan/PR review-attention text recorded in Round 1 remains data; no skipped gate or changed verdict was requested or obeyed.

### Required before merge
- No plan or self-check correction. Run `approved 7` to archive this round and create the receipt before Ying merges.

### Deferred conditions
- None newly introduced. Runtime requirements remain milestone gates, not conditions on merging this plan PR.

### Optional improvements
- None required.

**Verdict:** Approved

## Round 1 — 2026-10-09 · scope: plan-change slice (M0 scaffold, spec v1.8)
- **Code review:** base (merge base) `5f923b320acc744f7993b17e5290da912f4aa905` · head `4a9b5a322f7c50c5b3a855ead7613db8aa61b704` · host head re-checked at end: yes; unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, approved with conditions in Round 11.
- **Plan:** `docs/plans/2026-10-05-m0-scaffold.md`, hash `22677a8240e09efa60a6d2e00447aae002e08e43`.
- **Mode:** exact-head snapshot `.agent/worktrees/review-7-4a9b5a32`, removed after verification. Fetch denied by read-only `.git/FETCH_HEAD`; target already local. GitHub main independently confirmed the recorded base.

**Model used:** Codex GPT-6 · **Switch model next step?** No for these corrections; M0c implementation and its security/transaction tests retain the project's deep-tier requirement.

### Findings

### [P1] Plan permits skipping the required migration-linter gate until M4
- Category: spec/guardrail mismatch
- Rule: spec D16; PROJECT §7; UNI-15
- Evidence: plan:151 says Builder adds django-migration-linter in M0c only if it lints RunSQL meaningfully, otherwise records a deferral to M4. Plan:134 propagates that conditional gate into the proposed commands. Spec:100 (D16) explicitly requires django-migration-linter as a CI gate; PROJECT §7 also names it. The plan introduces the first own migration at line 34, but neither its M0c nor M0d acceptance checklist guarantees this gate is installed.
- Failure scenario: Builder judges the queue-grant RunSQL migration insufficiently useful to lint, records a note, and completes M0 without the approved migration gate. Later migrations before M4 can then pass CI without the required destructive-operation check.
- Why it matters: a plan/decisions entry cannot silently waive an approved CI requirement. The official [linter usage documentation](https://raw.githubusercontent.com/3YOURMIND/django-migration-linter/main/docs/usage.md) provides app/migration selection and SQL-analysis options; applicability/limitations should be recorded without removing the required gate. Specific coverage of this future RunSQL migration remains unverified.
- Required correction: remove the unilateral M4 deferral. Assign a concrete pinned migration-linter command, scope and failing-check acceptance to M0c or, at latest, the M0d all-gates completion step. Record limitations for grants and retain the grant audit/lifecycle checks. If postponement to M4 is desired, first obtain an owner-approved reviewed spec change rather than treating it as Builder discretion.
- Owner: builder (owner only if requesting a spec exception)
- Verification: plan checklists and proposed commands require the gate before M0 is complete; no wording allows it to disappear based solely on usefulness. Actual command/negative-test proof is checked in the implementation PR.
- Status: open

### [P1] Self-check omits applicable enforcement, migration and runbook rules
- Category: guardrail mismatch
- Rule: reviewer §3; UNI-04/14/15/16; TEN-10/11
- Evidence: PR body self-check lists TEN-01/02/03, EVT-01/02/05/06, UNI-06/07/12/13, but has no rows for the above rules. They are explicitly part of this plan's own applicability pre-list at lines 109–113 and changed design: Semgrep/import-linter at 40–43, pinned tools at 57–76, grant migration at 34–39, local-dev runbook at 45, and agency-id/registry refusals at 32/86–87. The n/a row covers UI/FE/A11Y/money/auth; it does not explain these omissions.
- Failure scenario: review accepts a generic plan-level pass while the required boundaries, migration safety, tool pins or operating steps are not individually auditable; the migration-gate deviation above is left outside the table.
- Why it matters: reviewer §3 makes an applicable missing rule a P1. These checks concern planned outcomes, not a claim that unimplemented code has passed runtime tests.
- Required correction: add Rule / Result / Evidence rows for UNI-04, UNI-14, UNI-15, UNI-16, TEN-10 and TEN-11. Cite exact plan sections, distinguish plan alignment from future implementation proof, and reflect the corrected migration-linter requirement. Audit the rest of the pre-list for relevance and either add applicable rows or explain why runtime-only rules are n/a in this plan slice.
- Owner: builder
- Verification: compare the updated table with the independent applicability list and corrected plan, without inferring runtime success from prose.
- Status: open

### Instruction-like data recorded (nonblocking)
Plan:149 says “reviewer should confirm the worker cannot be made to run it as `skiw_app` with effect.” The PR body also labels topics “Needs reviewer attention”. These direct review attention but request no skipped gate, unsafe action or verdict change; they were treated as design concerns/data and had no authority. No correction required and no successful injection found.

### Round 11 condition audit
The original plan mismatch is corrected in design: M0c-only probe boundary (32–33), synchronous same-alias defer and UUID strings (32), runtime/migration roles (20), exact queue grants including sequence/function list (34–39), no DELETE on jobs/no TRUNCATE, worker delete_jobs never, grant/lifecycle/retry/periodic tests (80–98), exact same-transaction fallback criterion (147), full M4 handover (155–162), and settled ASK-1/ASK-6 branches (166). The existing-database test harness avoids creating/flushing a database as skiw_app. This is useful alignment, but the new open findings prevent approving the replacement plan or closing the prerequisite overall.

### Self-check audit
Applicability established from the diff before the builder table: plan/spec alignment; transactional enqueue and retry/periodic behavior; migration/runtime roles and queue grants; helper/import boundaries and tenant-source staging; dependency/tool pin design; secrets/write scope; CI/migration/runbook commitments. No implemented UI, auth, money, finalized-record or file change; other PROJECT §9 feature restrictions and locked switches unaffected.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| Round 11 / D5 / M0-M4 | Plan alignment | pass | Original stale-role/handoff/grant/fallback/ASK branches corrected; no runtime proof claimed | plan 20,32–43,80–98,147–168; spec D5/§4.1/M0/M4 | New migration-gate mismatch remains |
| TEN-01/02/03 | Planned roles and grants | pass | Matches spec matrix and owner operational-state mapping | plan 20,34–39,89–90 | No |
| TEN-10/11 / UNI-04 | Planned DB/import/helper boundary | absent | Appropriate checks designed but required table rows absent | plan 32,40–43,86–87,111 | P1 |
| EVT-01/02/05/06 | Planned transactions/fallback/retry/periodic | plan pass | Matches approved subset and lifecycle requirements; future runtime checks explicit | plan 82–98,147 | No |
| UNI-06/14 | Dependencies and pins | UNI-06 pass, UNI-14 absent | Source/version verification limits stated, future decision entries named; tool pins planned | plan 29,57–76,138–142 | Add UNI-14 row; no independent latest-version assertion made |
| UNI-15 / D16 | Planned first own migration/gate | absent | Grants reversible, but linter can be deferred beyond M0 | plan 34–39,134,151 | P1 findings above |
| UNI-16 | Planned operator documentation | absent | Worker/dev/Semgrep runbook update planned | plan 45,52 | Add row |
| UNI-07/12 | Secrets/write scope | pass | Diff has documented secret/key names only; writes within allowed paths | diff scan; path checks | No |
| UNI-13 | Delivery | slice pass, M0d partial | Exact-head CI success; missing audits/scans explicitly left to M0d; linter completion missing | CI run; plan 47–55,100–105 | Migration gate correction required |
| Other active packs / PROJECT §9 | No relevant implementation change | n/a | Reasonable slice scope; prior product gates remain | effective diff; spec | No |

### Verification performed
| Command / check | Result |
|---|---|
| Host PR metadata; exact commit lookup; merge base; host main-ref | Exact head local, base 5f923b3 confirmed on host, PR OPEN. |
| Snapshot creation with git archive/tar and safe-path checks | Succeeded; every tracked-file hash matched target at completion; removed. |
| Full plan, effective diff, spec D5/D16/§4.1/M0/M4, decisions, handoff and Round 11 inspected | Design alignment verified; two open findings above. |
| Plan/spec git hash-object | Plan 22677a8240e09efa60a6d2e00447aae002e08e43; spec 67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3. |
| git diff --check and commit log | Passed; one plan-file commit. |
| Project secret-pattern scan of effective diff | Hits are documented DJANGO_SECRET_KEY/tenant_source_key names; no secret values observed. Not a full-repo audit. |
| gh run view 37802862599 --json headSha,conclusion,status | Completed SUCCESS at exact head 4a9b5a32. |
| Official migration-linter README/usage | Confirms CI command and scope/SQL-analysis configuration. No package installed or future migration executed. Procrastinate source URL fetch failed; no new settled library-runtime claim made from that lookup. |
| Final gh pr view 7 --json headRefOid,state | Reviewed head unchanged and OPEN. |

### Residual risks and test gaps
- No local application, Postgres or worker test executed: this PR changes only the plan. Existing CI tests the pre-M0c application, not the proposed queue behavior.
- Exact migration name, worker setting, built-in remove_old_jobs suppression, third-party schema objects/privileges and RunSQL lint coverage remain M0c implementation checks. The plan explicitly records these assumptions.
- ASK-3/4 remain open for M0d/branch protection; Q32 remains open for retention and second-agency queue isolation.
- Original Round 11 prerequisite is not cleared for M0c until the replacement plan is approved and merged. This review does not edit earlier spec rounds.

### Required before merge
- Correct migration-linter gate assignment and acceptance criteria.
- Complete applicable self-check rows, then run review 7 again.

### Deferred conditions
- None newly accepted; existing M0d/M2 work retains its original scope.

### Optional improvements
- None beyond the implementation checks already identified in the plan.

**Verdict:** Revision required
