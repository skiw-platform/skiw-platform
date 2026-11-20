# Review — 2026-11-20-m4-rest-roles-jobs-design

## Round 6 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.4 · hash `17b3f78376be4da968ebe338fb120f45b7ffd55b`
- **Model used:** GPT-6 (Codex; project deep-tier mapping unavailable) · **Switch model next step?** Yes — project specifies its deep tier for auth, tenancy and spec review.

### Findings
No new defect findings in the changes reviewed. The remaining gate is missing owner decisions: the proposed permission matrix, reset timing, interim audit design and RLS exception depend on Q1–Q6, and the previously reported answers are not independently established in evidence available to this reviewer (spec lines 49–50, 205–212). The spec appropriately treats them as proposals and requires owner statements and the governing amendment in M4r-0. These business and security decisions are essential to approve this spec, not deferred P2 conditions.

### Previous findings
- Round 5 provenance P1: resolved in the revision at the design-record level; the relevant claims are now explicitly attributed to the builder's unverified account, and the conflicting visible evidence and independent confirmation gate are stated. This review does not independently verify the separate transcript or treat its reported answers as owner decisions.
- Round 4 event-count finding: resolved at design level. Earlier implementation controls remain unverified pending their PRs.

### Applicability and verification
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06; project tenant, job and module constraints. Compared the revision with prior findings and visible conversation; `git hash-object` returned the hash above. Static review only; no implementation, database or browser tests were run. Worker integration, RLS and concurrency assumptions require the specified implementation tests.

### Required to unblock
- Obtain and record the owner's actual decisions for Q1–Q6 with their real source; reconcile this spec and the governing amendment to those decisions, then request a new spec review. No approval to implement is implied.

### Deferred conditions
- None.

**Verdict: Blocked**

## Round 5 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.3 · hash `6413b23a3094df1add015ec73d21df394c8f6424`
- **Model used:** GPT-6 (Codex; project deep-tier mapping unavailable) · **Switch model next step?** Yes — project specifies deep tier for auth, tenancy and spec review.

### Findings

#### [P1] The spec still asserts the disputed Q5 and Q6 answers as facts
- Category: defect / consistency.
- Rule: evidence integrity; PROJECT §2.
- Evidence: spec lines 49, 201, 204–205 and 212. Decision 25 and §10.1 now require owner confirmation and treat reported answers as working assumptions, but M4 done-when still calls Q5 the owner's typed answer and Q6 says the owner typed confirm. In the visible conversation, the Q5 text is the assistant's recommendation and the Q6 exchange asks for advice, followed by the assistant's recommendation. The separately identified builder transcript has not been examined.
- Failure scenario: A reader treats either disputed attribution as an established historical owner answer despite the proposal-only gate; the working assumptions and normative text give different accounts.
- Why it matters: The decision history must distinguish verified statements from reported but unverified claims, especially where a prior owner decision would change.
- Required correction: Make these statements consistent with the evidence caveat throughout, including the done-when and Q6 heading; identify Q5 text as the assistant recommendation visible here and any separately claimed owner action as unverified pending evidence. Retain the new dated owner-decision gate in M4r-0.
- Owner: builder.
- Verification: Search the full revision for claims that Q1–Q6 have been answered or confirmed, compare each to available evidence, and check that the governing amendment records actual future owner statements only.
- Status: open.

### Previous findings
- Round 4 audit event-count P1: resolved at design level. Decision 32, main-spec amendment items 4 and 6, test plan and M4 done-when now specify one event per inserted/deleted row and per changed update field, two for both fields and none for a no-op.
- Round 4 provenance P1: M4r-0 no longer directs the builder to copy the quotation as an owner statement; conflicting claims remain, as described above.
- Earlier authorization, RLS, audit and concurrency changes remain design-level only. Owner answers and the governing amendment are prerequisites, not established by this review.

### Applicability and verification
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06 and project tenant, job and module constraints. Compared spec v1.3 against prior findings, the amendment text, and visible conversation; `git hash-object` returned the hash above. Static review only; no implementation, database or browser tests were run. Worker integration and concurrency assumptions remain unverified.

### Required before approval
- Reconcile the remaining answer-provenance statements with available evidence and resubmit.

### Deferred conditions
- None.

**Verdict: Revision required**

## Round 4 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.2 · hash `c2690314a896d4a37b93f757a92695a43720e5f2`
- **Model used:** GPT-6 (Codex; project deep-tier mapping unavailable) · **Switch model next step?** Yes — project specifies deep tier for security, auth and spec review.

### Findings

#### [P1] The governing amendment still contains an incorrect event-count rule
- Category: spec/guardrail mismatch.
- Rule: consistency; main-spec amendment §10.2 items 4 and 6.
- Evidence: slice spec lines 57, 132, 201, 218 and 220. The test and M4 done-when now specify two events for a move-and-rename and none for a no-op, but Decision 32 and the exact amendment text for the governing spec still say one per changed row.
- Failure scenario: M4r-0 copies its prescribed text into the governing spec, creating a conflict with the implemented two-event behavior.
- Why it matters: The main spec wins over this slice and its approval gate would leave a contradictory audit requirement.
- Required correction: Align all normative statements and amendment text on one event per insert/delete, one per changed update field, two when both change, and none on no-op.
- Owner: builder.
- Verification: Trace all audit invariant statements and the two-field/no-op tests into the proposed main-spec amendment.
- Status: open.

#### [P1] The provenance correction still directs the builder to copy an unverified quotation as an owner statement
- Category: defect / spec consistency.
- Rule: evidence integrity; PROJECT §2.
- Evidence: slice spec lines 50, 177, 205 and 211. Section 10.1 now says the reported builder-session answers are unverified working assumptions and must not be copied as owner statements, but Decision 25 and M4r-0 still direct a DECISIONS entry to record Q5 as the owner's typed text verbatim. The quotation exactly matches this reviewer's earlier recommendation in the visible conversation; the separately identified builder transcript was not accessible or verified during this review.
- Failure scenario: M4r-0 copies the quotation into the durable log as a historical owner statement despite the lack of accessible supporting evidence, even if the owner subsequently agrees to the option.
- Why it matters: A later confirmation establishes a new decision, not the provenance of an earlier quotation.
- Required correction: Remove the instruction to attribute or copy the historical quotation unless its actual source is independently verified; state consistently that current values are proposals, and record any owner answer as a new decision with its actual source and date. Preserve the requirement for confirmation before dependent work.
- Owner: builder.
- Verification: Inspect the corrected Decision 25, M4r-0 and owner-question text and trace the eventual record to evidence.
- Status: open.

### Previous findings
- Round 3 provenance P0: the added evidence caveat and independent-confirmation gate reduce the immediate risk; the conflicting copy instruction remains open as P1 above. The separate builder transcript has not been inspected, so this review does not conclude what happened there.
- Round 3 event-count P2: M4 done-when and test table are corrected, but governing amendment text and Decision 32 remain inconsistent, as P1 above.
- Round 2 database audit and tenant isolation: addressed at design level; no implementation or live tests were run.

### Applicability and verification
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06, and project tenant, job and module constraints. Compared the current spec with prior rounds, its amendment text, and the visible conversation. `git hash-object` returned the hash above. The file changed since Round 3 but still declares version 1.2; fix workflow should bump the version when revising. Static review only; database concurrency, worker integration, and RLS tests are unverified.

### Required before approval
- Correct the governing amendment's event count and reconcile decision provenance throughout the spec.

### Deferred conditions
- None.

**Verdict: Revision required**

## Round 3 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.2 · hash `3538b1fc34c29c06f517b5f11b4b9f31a700b42e`
- **Model used:** GPT-6 (Codex; project deep-tier mapping unavailable) · **Switch model next step?** Yes — auth, tenancy and spec review call for the project's deep tier.

### Findings

#### [P0] The Q5 recommendation is still presented as the owner's verbatim answer
- Category: defect — fabricated attribution.
- Rule: reviewer evidence and severity rules; PROJECT §2.
- Evidence: slice spec lines 49–50, 205 and 211. The text at line 211 is the assistant's recommendation in this conversation, not a message typed by the user. The revision describes it as the owner's own words and instructs M4r-0 to copy it into DECISIONS as the owner's answer.
- Failure scenario: The governing amendment records assistant advice as an owner decision. The planned later confirmation cannot establish that this text was an earlier owner statement.
- Why it matters: The provenance record would be false, even if the owner later agrees with the proposed option.
- Required correction: Identify the text accurately as assistant advice; mark Q5 unconfirmed unless an independently evidenced owner answer exists, and record any subsequent confirmation as a new decision with its real source. Apply the same evidence standard to Q1–Q4 and Q6: the exchanges visible in this review are requests for advice, not selections. A separate builder session may exist, but its claimed selections are unverified here and must not be presented as established without evidence.
- Owner: builder.
- Verification: Compare every attribution against the actual source, and inspect the corrected M4r-0 decision record.
- Status: open.

#### [P2] The audit event count contradicts the allowed two-field update
- Category: consistency.
- Rule: spec §9 done-when; Decision 32.
- Evidence: slice spec lines 57, 132 and 201. Decision 32 permits one org-unit update changing both parent and name and requires two events; M4 done-when requires exactly one event per changed row.
- Failure scenario: A valid move-and-rename produces two events and fails the milestone criterion, or a builder suppresses one and loses required detail.
- Why it matters: The completion gate and the audited behavior cannot both hold.
- Required correction: State the exact invariant consistently, including two events for one update that changes both fields and zero for a no-op.
- Owner: builder.
- Verification: Trace the revised done-when to the multi-field and no-op tests.
- Disposition: before merge.
- Status: open.

### Previous findings
- Round 2 P0 remains open: the draft adds a confirmation gate but still misattributes the Q5 recommendation. Q6 is also not confirmed by the exchange visible in this session; the assistant recommended confirmation.
- Round 2 audit-bypass P1: addressed at design level by database triggers and grants sequenced after them (Decision 32). Implementation and intermediate migration tests remain unverified.
- Round 2 cross-agency P1: addressed at design level for change rows by Decision 33 and its three-context test plan; Q6 and the governing amendment remain subject to owner confirmation. Pre-tenant rows remain shared as explicitly stated.
- Round 1 action-line and concurrency findings: addressed at design level; implementation and snapshot assumptions remain to be tested.

### Applicability and verification
Applicable: UNI-03/04/06/09/13/16; AUTH-01/02/03/09/12; TEN-01–11; EVT-01/03/05/06; project tenant, job and module constraints. Compared the revision with prior rounds, relevant project and governing-spec evidence, and the visible conversation. `git hash-object` returned the hash above. Static review only: no implementation, database or browser tests run; worker integration and database concurrency assumptions remain unverified.

### Required before approval
- Correct the decision provenance and align the audit completion criterion.

### Deferred conditions
- None.

**Verdict: Revision required**

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
