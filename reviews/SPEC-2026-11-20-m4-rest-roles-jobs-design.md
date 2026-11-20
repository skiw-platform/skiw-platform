# Review — 2026-11-20-m4-rest-roles-jobs-design

## Round 2 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.1 · hash `a5a8d159ff6f3a087793386b7f2a414f2d44d0fc`
- **Model used:** GPT-6 (Codex; exact tier mapping unavailable) · **Switch model next step?** Yes — the project specifies its deep tier for auth, isolation and spec review.

### Findings

#### [P0] Recommendations are falsely recorded as owner decisions
- Category: defect — fabricated attribution
- Rule: reviewer evidence and severity rules; PROJECT §2 and §11.
- Evidence: slice spec lines 49–50 and 200–204. In this conversation, the user asked which Q1–Q5 option to choose; the assistant recommended options. The user did not state a selection or authorize a change to the earlier owner decision. Q5's purported verbatim owner quote is the assistant's own answer.
- Failure scenario: M4r-0 copies these claims to DECISIONS and changes the main spec, including moving a previously decided reset requirement, on the false premise that Ying approved them.
- Why it matters: Recommendations are not owner approvals; the audit trail and governing authorization would be materially false.
- Required correction: Remove the attributed quotations and claims of owner approval; label them as recommendations, and obtain and accurately record the owner's actual answers before relying on them. Retain the M4r-0 prerequisite.
- Owner: builder and owner.
- Verification: Compare recorded answers against the owner's direct statements and re-review the governing amendment.
- Status: open.

#### [P1] The database grants permit unaudited role and org changes
- Category: guardrail mismatch
- Rule: main spec §4.1 role-change audit; slice spec Decision 30 and M4 done-when.
- Evidence: slice spec lines 28, 55, 64–65, 78 and 194; M4r-1b grants direct INSERT/UPDATE/DELETE before M4r-5a's application change functions and event writer (lines 175–180). The database trigger checks event shape, not that a change has a corresponding event.
- Failure scenario: Direct SQL as skiw_app, or another code path using its existing grants, changes a role or org unit without calling `_record`. Even the period between M4r-1b and M4r-5a permits such writes without the proposed event.
- Why it matters: Atomicity of the designated helper does not establish the stated invariant that every committed change is recorded; missing events undermine the required audit trail.
- Required correction: Enforce the change/event invariant at the database boundary or restrict writes to a database-enforced audited path, including the deployment sequence. Specify any deliberately excluded threat and reconcile it with the governing requirement rather than asserting universal coverage.
- Owner: builder.
- Verification: Direct INSERT, UPDATE and DELETE through every granted path either produce the correct event in the same transaction or are refused; test rollback and intermediate migrations.
- Status: open.

#### [P1] Q6 permits cross-agency disclosure of change records
- Category: material risk / guardrail mismatch
- Rule: TEN-06–08; main spec D18 and §4.2 tenant isolation.
- Evidence: slice spec lines 55, 66 and 205 explicitly say Q6 option (a) allows agency B to read agency A's role-history events. The rows contain user and org identifiers and role information.
- Failure scenario: A request or SQL running as skiw_app in agency B reads agency A's role changes from the global table.
- Why it matters: This introduces a known cross-tenant disclosure into the proposed design. Describing identifiers as codes does not make the records non-tenant data.
- Required correction: Remove the unisolated option as a shippable design; specify and test enforced isolation for all tenant-bearing events, pre-tenant writers and no-token access, with the governing amendment. Obtain the owner decision on the permissible implementation.
- Owner: builder and owner.
- Verification: Live tests as skiw_app for A, B and no tenant prove no cross-agency read or write; pre-tenant and definer paths continue working.
- Status: open.

### Previous findings
- R1 governing conflict: **open**. M4r-0 is now a prerequisite, but its claimed owner answers are not established (P0 above).
- R1 action-line restriction: **resolved at design level** by Decisions 7–9 and 26 and the matching test plan; implementation remains unverified.
- R1 concurrent tree moves and last-owner revocations: **addressed at design level**, with explicit locks, isolation requirements and two-connection tests. Snapshot behavior is explicitly an assumption to prove in M4r-1b; no live test was run during this review.

### Applicability and evidence
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06; project module boundaries and tenant/job constraints. This is a design review, not verification of unbuilt implementation. Q6 is unanswered and the prerequisite governing amendment does not yet exist.

### Verification performed
- Compared v1.1 with Round 1, the current conversation, the governing project/spec/decision evidence and existing security_event grants.
- `git hash-object docs/specs/2026-11-20-m4-rest-roles-jobs-design.md` → `a5a8d159ff6f3a087793386b7f2a414f2d44d0fc`; spec remains untracked.
- Static review only; no implementation, database or browser tests run. The worker integration and database concurrency assumptions remain for their implementation gates.

### Required before approval
- Correct the attributed owner decisions and obtain actual answers; resolve the audit enforcement and cross-agency isolation findings.

### Deferred conditions
- None.

**Verdict: Revision required**

## Round 1 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.0 · hash `f9da331de63b907f2079e401fa70d135c3f682c7`
- **Model used:** GPT-6 (Codex; exact tier mapping unavailable) · **Switch model next step?** Yes — project specifies its deep tier for auth, isolation and spec review.

### Findings

#### [P1] Governing requirements and owner decisions remain unresolved
- Category: spec/guardrail mismatch
- Rule: AUTH-03, AUTH-09; main spec §4.1, §6; PROJECT §2
- Evidence: slice spec lines 30–32, 37, 175–191; main spec line 142; decisions log lines 1248–1252.
- Failure scenario: The slice says it changes no main-spec rule, yet permits unaudited role changes and defers the owner reset previously required in M4-rest. Its own amendments and owner questions are left for a later revision, while the M4 completion criteria permit this design to proceed.
- Why it matters: The approved main spec and recorded owner decision still govern; suggested answers do not authorize changing them. Builders cannot know which requirements to implement or when the conflicting changes become authoritative.
- Required correction: Obtain and record owner answers, resolve the conflicts through an approved governing spec amendment and decision update, and make the prerequisite explicit before affected work. Define the interim authorization and audit treatment consistent with those decisions.
- Owner: builder and owner.
- Verification: Re-review the revised slice and governing requirements and trace each affected PR to an approved decision.
- Status: open.

#### [P1] Line restrictions are not enforced on actions
- Category: guardrail mismatch
- Rule: AUTH-03; main spec §6 line split.
- Evidence: slice spec lines 32–34, 103, 111–112; main spec line 564.
- Failure scenario: An insurance-only adviser invokes an investment-tagged connector action. The wrapper checks the permission and unions grants without checking an action line, and scoped() only filters model reads. No decision defines where a route supplies its line or how mixed-line grants are matched.
- Why it matters: The design can authorize operations outside the user's permitted business line even if all row-scoping tests pass.
- Required correction: Specify fail-closed action-line metadata and grant matching in the wrapper, including untagged actions, multiple roles and conditional step-up; add positive and negative route tests and a registry check for missing line declarations.
- Owner: builder.
- Verification: Test insurance, investment and both grants against both lines, including mixed role scopes and missing metadata.
- Status: open.

#### [P1] Concurrent tree moves can defeat the cycle check
- Category: defect
- Rule: main spec §4.1 no cycles; AUTH-03.
- Evidence: slice spec lines 27, 34 and 114.
- Failure scenario: Two transactions concurrently move sibling A beneath B and B beneath A. Each recursive ancestor check can see the old committed tree and pass, leaving a cycle after both commits.
- Why it matters: Team authorization relies on this hierarchy; a cycle can break or widen subtree evaluation.
- Required correction: Specify a database-enforced serialization strategy for hierarchy changes, including concurrent writers, and a bounded recursive query; test the two-transaction race using separate connections.
- Owner: builder.
- Verification: Concurrent opposing moves cannot both commit and subtree queries terminate with the correct visibility.
- Status: open.

#### [P1] Last-owner refusal has a concurrent revocation race
- Category: defect
- Rule: slice Decision 12; AUTH-12.
- Evidence: slice spec lines 37 and 75; milestone M4r-5 line 157.
- Failure scenario: Two operators concurrently revoke the only two owner rows. Each sees another owner and both deletes commit, leaving no owner.
- Why it matters: The stated recovery and administration invariant is lost.
- Required correction: Specify a per-agency transactional serialization or equivalent database constraint covering all owner revocations and test concurrent revocations, including rollback.
- Owner: builder.
- Verification: With two owner rows, concurrent revocations leave at least one owner after commit.
- Status: open.

### Applicability and evidence
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06; PROJECT §9 module boundaries and job/tenant constraints. Other active packs concern features outside this slice; no implementation self-check is claimed for this draft. Findings above identify material failures; this is not a certification of unimplemented controls.

### Verification performed
- Read project workflow, reviewer role, project identity, sources, paths, guardrails, slice spec, handoff, relevant governing spec and decisions entries.
- `git hash-object docs/specs/2026-11-20-m4-rest-roles-jobs-design.md` → `f9da331de63b907f2079e401fa70d135c3f682c7`; `git status --short` shows the draft is untracked.
- Static design review only; no implementation tests or browser checks run. Exact installed worker shutdown hooks and retry signatures remain unverified, as the draft itself notes.

### Residual risks and test gaps
- Concurrent behavior and library integration must be proved in the named implementation PRs; no running system was checked here.
- The owner questions and proposed governing amendments remain open; no owner answers were inferred.

### Required before approval
- Resolve the four P1 findings and submit the revised spec for another review.

### Deferred conditions
- None.

**Verdict: Revision required**
