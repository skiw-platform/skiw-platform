# Review — 2026-11-20-m4-rest-roles-jobs-design

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
