# Review — 2026-10-05-skiw-platform-stack-design

## Round 9 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.7 · hash (`git hash-object`) `cf57625da85c77d9be83995721fce9ed45907a07`
- **Code review:** n/a. No new-platform source or Git repository is present locally. The old application's repository is identified in `docs/DECISIONS.md` but was not accessed in this round.

**Verdict:** Approved
**Model used:** Codex GPT-6 · **Switch model next step?** No — implementation can proceed through the specified milestone gates.

### Findings

No open P0, P1, or P2 findings for this spec hash.

### Round 8 resolution audit

| Round 8 finding | Round 9 result | Evidence |
|---|---|---|
| M11 expected a dispatched, potentially billed call to expire | Resolved: M11 now requires the committed-dispatch call to stay counted until `settle`, or remain `unknown`; direct `expire` is rejected. The never-dispatched case alone expires to zero. | §4.1, Flow 5.8, T9 and M11, lines 169, 458, 516 and 612 |
| T9 and Q31 retained the absolute no-send claim | Resolved: D12, Flow 5.8, T9 and Q31 now use the dispatch-commit boundary and explicitly allow a pre-pause dispatched call to send afterward. | D12, Flow 5.8, T9 and Q31, lines 96, 458, 516 and 669 |

### Self-check audit

`agents/PROJECT.md` remains unfilled. Applicable packs are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. No application implementation or PR self-check exists locally, so rule-level execution remains unverified. No instruction-like spec content directed the reviewer to change the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `cf57625da85c77d9be83995721fce9ed45907a07`. |
| Read spec v1.7, Round 8, decisions log and handoff | Rechecked the AI ledger trigger, dispatch and pause boundary, T9 tests, M11 acceptance criteria and Q31; both Round 8 conflicts are resolved. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- Approval applies to this feature-complete design and this hash only. The old application's source remains unverified; Doc1/Doc2 claims are document evidence.
- Bedrock token bounds, target-account configuration, audit integrity, tenant isolation and connector behavior require the milestone tests and release gates named in the spec; they have not been exercised here.
- Owner decisions in §10 remain open. The spec's G-AI and G-DRIVE gates keep the affected capabilities disabled until their required decisions are recorded.

### Required before merge
- None for this spec hash. Initial `setup` Part B must populate `agents/PROJECT.md` and reconcile it to this approved hash before build work.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 8 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.6 · hash (`git hash-object`) `6e8768725e94885a4148b0c2ebd9635b78cfb499`
- **Code review:** n/a. No new-platform source or Git repository is present locally; the old source identified in `docs/DECISIONS.md` was not accessed.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — these are exact cross-reference corrections.

### Findings

### [P1] M11 expects a dispatched, potentially billed call to expire
- Category: defect
- Rule: D12; §4.1 `ai_usage_ledger`; Flow 5.8; T9; M11
- Evidence: spec line 612's new race case has B commit `dispatch`, pause before the Bedrock send, then send after A's overrun; it then says B “is later `expire`d” and has ledger `reserve` + `expire` = 0. The ledger trigger at line 169 rejects `expire` when `dispatch` exists; Flow 5.8 at line 458 sends B and keeps any ambiguous outcome counted. T9's corresponding case at line 516 instead expects B to settle within its reservation.
- Failure scenario: B's request is billed after its committed dispatch, but M11's stated outcome would release its entire reservation. The acceptance test either fails the database trigger or, if implemented by bypassing it, understates spend and permits another reservation at the cap edge.
- Why it matters: the milestone's completion test contradicts the billable-call invariant that protects the budget across crashes and pauses.
- Required correction: in the M11 case where B's `dispatch` committed, require B to `settle` (or remain counted as `unknown` if its outcome is lost), never `expire`. Keep `reserve` + `expire` = 0 only for a reservation whose `dispatch` never committed. Align M11 with T9's case (vi) and the ledger trigger.
- Owner: builder
- Verification: with B paused after its committed `dispatch`, A's overrun commits, B resumes and the fake provider bills it; B remains counted until a valid `settle`, and a direct `expire` is rejected. A never-dispatched reservation can still expire to zero.
- Status: open

### [P2] The old absolute no-send claim remains in T9 and Q31
- Category: spec mismatch
- Rule: D12; T9; Flow 5.8; Q31
- Evidence: D12 and Flow 5.8 (lines 96 and 458) now correctly say that the pause stops new `dispatch` commits but a call whose dispatch committed earlier can be sent afterward. T9's control text (line 516) still says “no request is sent after it commits”; Q31 (line 669) still says already-admitted, not-yet-sent calls are stopped. T9's new case (vi) itself demonstrates the exception.
- Failure scenario: an operator reads T9 or Q31 and expects a pre-send, already-dispatched call to be stopped after the pause, while the documented flow allows it to reach Bedrock.
- Why it matters: the threat-model guarantee and owner decision text disagree with the actual safety boundary.
- Required correction: use the dispatch-commit boundary in T9 and Q31, explicitly distinguishing an undispatched reservation from a committed dispatch awaiting its network send.
- Owner: builder
- Verification: D12, Flow 5.8, T9, M11 and Q31 state the same boundary and the suspended-after-dispatch test has one consistent billable outcome.
- Disposition: before merge
- Status: open

### Round 7 resolution audit

| Round 7 finding | Round 8 result | Evidence |
|---|---|---|
| No-send guarantee exceeded the dispatch transaction boundary | Partially resolved: D12 and Flow 5.8 now describe the boundary and T9 adds case (vi); stale T9/Q31 language and contradictory M11 outcome above keep the correction incomplete | D12, Flow 5.8, T9, M11, Q31, lines 96, 458, 516, 612 and 669 |

### Self-check audit

`agents/PROJECT.md` remains unfilled. Applicable packs are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. No implementation or PR self-check exists locally, so rule-level execution remains unverified. No instruction-like spec content directed the reviewer to change the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `6e8768725e94885a4148b0c2ebd9635b78cfb499`. |
| Read spec v1.6, Round 7, decisions log and handoff | Compared D12, ledger trigger, Flow 5.8, T9, M11 and Q31 for the dispatch-commit boundary. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- Old-source claims remain document evidence, not code-verified facts.
- Bedrock token bounds, account configuration and audit implementation remain milestone checks; none could be exercised here.
- Owner decisions in §10 remain open, with the specified release gates where applicable.

### Required before merge
- Resolve the P1 and P2 marked `before merge`, bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 7 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.5 · hash (`git hash-object`) `46d27f6e04a0b557ce4d08f412ffe940d5227eaf`
- **Code review:** n/a. The old application's private repository is named in `docs/DECISIONS.md` but was not accessed; no new-platform source or Git repository exists locally.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the remaining correction is narrow.

### Findings

### [P2] The pause cannot guarantee that no request is sent after it commits
- Category: spec mismatch
- Rule: D12; T9; Flow 5.8; M11
- Evidence: spec lines 96 and 516 say that no request is sent after an `overrun` commits. Flow 5.8 (line 458) commits the `dispatch` marker, thereby releasing the shared transaction advisory lock, **before** sending the Bedrock request. The overrun can then take its exclusive lock and commit between those two steps. The race tests in T9 and M11 cover calls that have not committed `dispatch`, but not a process suspended after `dispatch` commits and before the network send.
- Failure scenario: B commits `dispatch`, pauses before its HTTP call, A commits an overrun and pauses the agency, then B resumes and sends a Bedrock request. B is correctly counted among the calls whose dispatch committed before the pause, so the stated cost bound still holds; the absolute no-send promise does not.
- Why it matters: operators and tests may treat the pause as stopping every later network call, which this transaction boundary cannot ensure.
- Required correction: state that no **new dispatch marker** commits after the pause, and that an already-dispatched call may still be sent afterward, or use a protocol that actually holds the exclusion through the network send. Align D12, T9, M11 and the race test with the chosen guarantee.
- Owner: builder
- Verification: suspend B after its `dispatch` commit but before its fake Bedrock call, commit A's overrun, then resume B; the observed behavior matches the documented guarantee and B's cost remains within the pre-pause dispatched-call allowance.
- Disposition: before merge
- Status: open

### Round 6 resolution audit

| Round 6 finding | Round 7 result | Evidence |
|---|---|---|
| Overrun did not stop earlier reservations from dispatching | Resolved in design: reserve and overrun take one agency admission lock exclusively; dispatch takes it shared and rechecks pause; the pre-send boundary above remains | D12, §4.1, Flow 5.8, T9, M11, lines 96, 169, 458, 516 and 612 |
| Audit verifier omitted history before the last anchor | Resolved in design: daily full verification from genesis, checks of every retained anchor and the head-to-archive boundary; historical tamper tests added | §4.1, T19, M5, lines 166, 526 and 606 |

### Self-check audit

`agents/PROJECT.md` remains unfilled. Applicable packs are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. There is no application implementation or PR self-check locally, so rule-level execution remains unverified. No instruction-like spec content directed the reviewer to change the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `46d27f6e04a0b557ce4d08f412ffe940d5227eaf`. |
| Read spec v1.5, Round 6, decisions log and handoff | Both earlier findings re-inspected; the dispatch-commit/network-send boundary checked against the new lock protocol. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- Old-source claims remain document evidence, not code-verified facts.
- Bedrock token bounds, account configuration and audit implementation remain milestone checks; none could be exercised here.
- Owner decisions in §10 remain open, with the specified release gates where applicable.

### Required before merge
- Resolve the P2 marked `before merge`, bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 6 — 2026-10-05 · scope: unchanged feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.4 · hash (`git hash-object`) `a539c1e6a8f9001e577aa15e25131f5b329dce75`
- **Change since Round 5:** none. The spec's version, content hash and handoff fingerprint are unchanged. This round records the repeated review request; the Round 5 findings remain open.
- **Code review:** n/a. No new-platform source or Git repository is present locally; the old source named in `docs/DECISIONS.md` was not accessed.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder needs to revise the spec.

### Findings

### [P1] An overrun does not stop previously reserved AI calls from dispatching
- Category: defect
- Rule: D12; T9; Flow 5.8; M11
- Evidence: spec line 447 checks the overrun pause only during `reserve`; `dispatch` checks only terminal status and expiry. The overrun settlement does not take the agency-period admission lock. D12 (line 87) says AI pauses for the agency after an overrun. No text changed since Round 5.
- Failure scenario: B reserves before A records an overrun, then B dispatches afterward under the invalid price bound. A concurrent C may pass the pause check before A's overrun commits.
- Why it matters: the pause does not prevent further calls after a broken bound is known, and the stated limit to already-dispatched overruns does not hold.
- Required correction: serialize the pause with admission, check it again at dispatch, and define a safe terminal path for undispatched reservations blocked by the pause.
- Owner: builder
- Verification: race tests show a reserve concurrent with the overrun cannot be admitted after the pause commits, and a pre-reserved but undispatched call sends no Bedrock request after the pause.
- Status: open

### [P2] Incremental audit verification does not cover events before the last anchor
- Category: material risk
- Rule: T19; §4.1 `audit_event`; M5
- Evidence: spec line 157 starts verification “from the last anchored head,” while lines 157, 515 and 595 claim detection of edited and removed events. No archive-to-database comparison or full historical verification was added since Round 5.
- Failure scenario: an event from before yesterday's S3 anchor is modified by a privileged database actor; checking only the new segment accepts the later chain.
- Why it matters: the daily verification does not meet its stated historical tamper-detection scope.
- Required correction: compare anchored history against the immutable export or reverify from genesis on a defined schedule, and test changes before the latest anchor.
- Owner: builder
- Verification: a pre-anchor row modification in a disposable database causes the daily verifier to alarm; valid new segments still pass.
- Disposition: before merge
- Status: open

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `a539c1e6a8f9001e577aa15e25131f5b329dce75`, identical to Round 5. |
| Re-read v1.4 version header, AI and audit references, Round 5 and handoff | No spec revision or resolution evidence found. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- The old source remains unverified; Bedrock and audit implementation checks await their milestones.
- Owner decisions in §10 remain open under the spec's release gates.

### Required before merge
- Resolve the P1 and P2 above, bump the spec version and request review of the changed hash.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 5 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.4 · hash (`git hash-object`) `a539c1e6a8f9001e577aa15e25131f5b329dce75`
- **Code review:** n/a. `docs/DECISIONS.md` names the old application's private repository as read-only reference. The earlier read-only access attempt failed; old-source claims remain unverified from code.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can resolve these bounded design gaps.

### Findings

### [P1] An overrun does not stop previously reserved AI calls from dispatching
- Category: defect
- Rule: D12; T9; Flow 5.8; M11
- Evidence: spec line 447 checks for an `overrun` only during `reserve` and says new reserves refuse until repricing. The later `dispatch` check tests only terminal status and expiry, then sends the request. The `overrun` settlement does not take the agency-period admission lock. D12 (line 87) says AI is paused for the agency after an overrun and bounds excess spend by overruns of calls already dispatched.
- Failure scenario: calls A and B reserve under the same pricing version. A settles above its bound, writes an `overrun`, and pauses AI. B has not yet dispatched; its dispatch still passes the stated checks and sends under the same invalid bound. A concurrent C can also pass the reserve pause check before A commits its overrun because settlement does not share the admission lock.
- Why it matters: the incident pause does not actually stop new provider calls, so a broken bound can cause further excess spend after the first overrun is known. The claimed limit to calls already dispatched is false.
- Required correction: make an overrun's pause atomic with the agency-period admission decision, and check the current pause state again in `dispatch` immediately before allowing a request to be sent. Specify what happens to existing undispatched reservations (for example, expire or release them only after proving no dispatch) and test both races.
- Owner: builder
- Verification: with A's overrun concurrent with C's reserve, C cannot be admitted after the pause commits; with B reserved but not dispatched when A's overrun commits, B sends no Bedrock request. The ledger remains correct for B's reservation.
- Status: open

### [P2] Incremental audit verification does not cover events before the last anchor
- Category: material risk
- Rule: T19; §4.1 `audit_event`; M5
- Evidence: spec line 157 says the verifier walks each agency “from the last anchored head,” while lines 157, 515 and 595 claim it detects edited and removed events and require a tampered-row test. The daily S3 Object Lock export contains events and a chain head, but no comparison of the archived segment with the current database or full-chain verification is specified.
- Failure scenario: after yesterday's head at sequence 100 is anchored, a privileged database actor edits event 50. A verifier that starts at sequence 101 sees a valid continuation and raises no alarm, even though the current database no longer matches the immutable export. Append-only grants prevent ordinary `skiw_app` SQL from making this edit, but the specified tamper test and breach-detection claim include row modification.
- Why it matters: the verifier's stated detection scope is broader than the portion of the chain it examines.
- Required correction: make the verifier compare the anchored segment against its immutable export, or reverify from genesis on a defined schedule, including the archived head-to-database boundary. State which checks run daily and on demand.
- Owner: builder
- Verification: modify an event before the latest S3 anchor in a disposable test database; the daily verifier detects it and alarms. Also verify a changed or missing anchor and a valid new segment.
- Disposition: before merge
- Status: open

### Round 4 resolution audit

| Round 4 finding | Round 5 result | Evidence |
|---|---|---|
| Unsupported metadata-only Bedrock reconciliation | Resolved in design: invocation logging disabled; unknown dispatched calls stay counted for their period; M11 checks the target account configuration | D12, D17, §4.1, Flow 5.8, M11, lines 87, 92, 160, 447 and 601 |
| Positive-cost path contradicted the ledger constraint | Resolved for settlement: frozen prices/FX, stated token bound, a separate counted `overrun` and a truthful cap caveat; new pause gap above | D12, §4.1, Flow 5.8, T9 and M11, lines 87, 160, 447, 505 and 601 |
| Concurrent audit appends lacked ordering | Resolved in design: per-agency `audit_head` lock and gapless commit sequence, with concurrency and rollback tests; historical verification gap above | §4.1, T19 and M5, lines 157–158, 515 and 595 |

### Self-check audit

`agents/PROJECT.md` remains unfilled. Applicable packs are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. There is no implementation or PR self-check locally, so rule-level execution remains unverified. No instruction-like spec content directed the reviewer to change the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `a539c1e6a8f9001e577aa15e25131f5b329dce75`. |
| Read spec v1.4, Round 4, decisions log, handoff and relevant guardrails | Re-inspected all three Round 4 corrections, the AI state transitions, and the audit append and verifier protocol. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- The old application's repository is identified but was not accessible for this round; Doc1/Doc2 claims remain document evidence, not code-verified facts.
- The Bedrock token bound, target-Region logging configuration and audit protocol are specified as milestone checks; none could be exercised without an implementation or AWS account.
- Owner decisions in §10 remain open, with the stated release gates where applicable.

### Required before merge
- Resolve the P1 and P2 marked `before merge`; bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 4 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.3 · hash (`git hash-object`) `9e39502d54627979ab7f438fa930a444f8407272`
- **Code review:** n/a. `docs/DECISIONS.md` identifies the old application's private repository as read-only reference; the earlier `gh api` attempt failed because the GitHub connection and token were unusable. No old-source claim was verified from code.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can resolve the specified design gaps.

### Findings

### [P1] Bedrock invocation logs cannot provide the specified metadata-only reconciliation
- Category: guardrail mismatch
- Rule: UNI-09; D12; D17; Flow 5.8; M11
- Evidence: spec lines 435 and 590 require an in-region invocation log containing `requestMetadata` and token counts but no prompt or response text. [AWS model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html) says text invocation records include input and output JSON bodies (up to 100 KB inline, larger bodies in S3); [AWS LoggingConfig](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_LoggingConfig.html) exposes a text-data delivery switch, not a metadata-only text mode. [AWS request metadata documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-request-metadata.html) says that metadata is recorded in invocation logs only when logging is enabled.
- Failure scenario: enabling text invocation logging to reconcile a killed AI request also sends its prompt, tool context and model response to CloudWatch or S3. Those bodies can contain client information despite identifier pseudonymisation, conflicting with UNI-09 and the spec's logging promise. Disabling text logging removes the proposed evidence for reconciling `unknown` reservations.
- Why it matters: M11's release test asserts an AWS logging configuration that the documented service does not provide; an implementation following the current flow risks creating an unapproved second store of client data.
- Required correction: choose and specify a supported, privacy-safe source for per-request usage evidence, with a real AWS configuration and captured log proving that neither body is delivered. If none exists, remove provider-log reconciliation and keep `unknown` reservations counted at their upper bound; update Flow 5.8, M11 and Q29 accordingly. Do not enable full-body invocation logging under the current UNI-09 rule.
- Owner: builder
- Verification: inspect the actual Bedrock logging configuration and a text-invocation record in the target Region, or test that logging is disabled and an unresolved dispatched call remains counted without reconciliation.
- Status: open

### [P1] The positive-cost path contradicts the ledger constraint and hard-cap claim
- Category: defect
- Rule: D12; T9; §4.1 `ai_usage_ledger`; Flow 5.8
- Evidence: spec line 150 requires every `settle` and `reconcile` amount to be ≤ 0, while line 435 says a price change can make `actual − estimate` positive and that the event is still recorded. The same flow estimates cost from counted input tokens and a maximum output token setting, but does not establish that these cover every billable token category or the actual provider input count. D12 and T9 call the cap hard (lines 78 and 493).
- Failure scenario: a call consumes the remaining cap and its provider-reported cost exceeds the reservation. The specified positive `settle` cannot pass the database trigger. If that check is relaxed, the positive charge puts final spend above the cap; the next-reserve refusal occurs too late to prevent it.
- Why it matters: the stated recovery branch is impossible under the schema, and the claimed cap depends on an upper bound the spec has not proved.
- Required correction: define and verify a conservative reservation bound for all billable usage with fixed pricing and FX, and remove the positive-delta branch if it is impossible. If over-reservation cannot be guaranteed, specify how positive settlement is recorded and correct the hard-cap claim and M11 acceptance test; an AWS Budgets alert alone is not a hard cap.
- Owner: builder
- Verification: provider-shaped fixtures for input/output and any other billed token categories, a price/FX change and an actual-cost-above-estimate case show a valid terminal ledger event and a truthful cap invariant; the schema and Flow 5.8 agree.
- Status: open

### [P2] Concurrent audit appends need an ordering protocol
- Category: material risk
- Rule: T19; §4.1 `audit_event`; M5
- Evidence: spec lines 148, 503 and 584 require a per-agency `prev_hash` chain and verification for every client view, but do not say how two transactions appending events for the same agency serialize or how the verifier chooses the predecessor when IDs are assigned before commit.
- Failure scenario: two client views insert audit events concurrently, both read the same current chain head, and both commit with that `prev_hash`. A daily verifier either alarms on ordinary activity or silently accepts a fork, depending on its traversal.
- Why it matters: routine concurrent traffic can make the audit chain unreliable precisely when it is needed for incident investigation.
- Required correction: specify a per-agency append lock or another atomic head/sequence protocol, including rollback and commit ordering, then make the verifier reject forks and gaps.
- Owner: builder
- Verification: two overlapping audit transactions for one agency produce a single verifiable chain in commit order; a deliberately forked chain fails verification.
- Disposition: before merge
- Status: open

### Round 3 resolution audit

| Round 3 finding | Round 4 result | Evidence |
|---|---|---|
| Generic step-up reusable for another CRM action | Resolved in design: action-bound MAC artifact, DB verifier and single-use send; implementation untested | D11, §4.1–4.3, Flow 5.5, M9/M13, lines 77, 145–146, 315–395, 429 and 588–592 |
| Unknown AI call released on expiry | Resolved in design: only undispatched reservations expire; dispatched unknowns remain counted; new logging and upper-bound gaps above | D12, §4.1, Flow 5.8, T9 and M11, lines 78, 150, 435, 493 and 590 |
| Signed job could enter another tenant | Resolved in design: enqueue derives the current tenant and checks referenced IDs under RLS | D5, §4.1, M4, lines 71, 167 and 583 |
| Plain hash chain accepted forged appends | Resolved against forged SQL inserts by keyed `event_mac` and external anchor; concurrent ordering gap above | §4.1, T19 and M5, lines 148, 503 and 584 |

### Self-check audit

`agents/PROJECT.md` is still unfilled. Applicable packs are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. There is no application implementation or PR self-check locally, so rule-level execution remains unverified. No instruction-like text in the spec directed the reviewer to change the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `9e39502d54627979ab7f438fa930a444f8407272`. |
| Read spec v1.3, prior rounds, decisions log, handoff, reviewer rules and relevant guardrails | Re-inspected all four Round 3 corrections and checked the revised AI ledger and audit design. |
| AWS Bedrock documentation | Logging configuration and sample record show text bodies in invocation logs; request metadata appears there only with logging enabled. No live AWS configuration or invocation was available. |
| Application checks | Not run: no new-platform source, CI, staging environment or Git repository exists locally. |

### Residual risks and test gaps
- The old application's source is identified in `docs/DECISIONS.md` but was not accessible for this round; Doc1/Doc2 claims remain document evidence, not code-verified facts.
- AWS behaviour in the target account and Region is not tested; the M11 gate must validate any replacement reconciliation source before enabling AI chat.
- Owner decisions on Google Workspace, Drive filing, AI cross-border use, CRM terms and client display code remain open, with release gates where specified.

### Required before merge
- Resolve both P1 findings and the P2 marked `before merge`; bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 3 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.2 · hash (`git hash-object`) `266abf435872704ed95d7b467107b2482ab20602`
- **Code review:** n/a. The old application's private repository is identified in `docs/DECISIONS.md`; read-only `gh api` access was attempted in the preceding turn and failed because the GitHub connection failed and the configured token was invalid. No old source claims were reverified.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can address the specific remaining design gaps.

### Findings

### [P0] A genuine step-up can approve a different CRM action through SQL
- Category: security defect
- Rule: D11; T10; AUTH-09
- Evidence: spec lines 114, 285–323 and 422. `auth_stepup.evidence_mac` authenticates the step-up row's user, purpose, time and session, but contains no `external_action` id or approved payload hash. The DB trigger permits any `draft → approved` transition with a recent step-up for that user and purpose; the executor verifies the same step-up MAC.
- Failure scenario: a user performs a real `outbox.approve` step-up for action X. During its five-minute window, injected SQL running as `skiw_app` creates or changes another draft Y within that agency, sets Y's approval fields to the user's valid step-up and Y's current payload hash, then moves Y to `approved`. The trigger and executor checks pass even though the person never reviewed Y; the executor sends Y to CRM.
- Why it matters: the core “a person submits” invariant is still bypassable under the SQLi threat the spec explicitly models. The new MAC prevents a fake step-up row, but not reuse of a real one for a different action.
- Required correction: bind an app-generated, unforgeable approval artifact to the specific action id, canonical payload/diff hash, approver, session and expiry after the human confirms that exact diff; verify that binding before execution and enforce one-time or action-specific use. A recent generic step-up can remain a prerequisite but must not itself authorize arbitrary rows.
- Owner: builder
- Verification: under `skiw_app`, direct SQL using a genuine recent step-up for action X cannot approve or execute action Y; a payload change invalidates the artifact; the intended X approval succeeds once.
- Status: open

### [P1] Expiring an unresolved AI call can exceed the hard budget cap
- Category: defect
- Rule: T9; MON-01/05
- Evidence: spec lines 70, 140, 363 and 421. The sweeper inserts `expire` and releases the full reserved estimate after a timeout; a late billed call then inserts `adjust` for its actual cost. The flow explicitly allows that late-settle path while promising a hard stop at 100%.
- Failure scenario: call A reserves the remaining monthly budget and is billed but its process pauses before settlement. The sweeper expires A, releasing the budget; call B reserves and spends it. A then records a late `adjust`, leaving actual spend above the cap.
- Why it matters: the ledger balances eventually, but the claimed hard budget limit is not enforced during an unknown billing outcome.
- Required correction: keep an unresolved billable call's upper-bound reservation counted until provider outcome is known or a provable cancellation/no-charge result is recorded; otherwise state that the cap is not hard and provide an independent provider-side cap. Test process suspension across the expiry boundary, not only process death.
- Owner: builder
- Verification: with a late billed A and concurrent B at the cap edge, B is refused and final spend never exceeds the configured hard cap.
- Status: open

### [P1] Bind signed job tenant arguments to the current tenant
- Category: material risk
- Rule: D18; TEN-11; T1
- Evidence: spec lines 63, 157, 226–230 and 270. `jobs.enqueue_in_tx(task, agency_id=…, **ids)` signs caller-supplied arguments inside `with_agency()`, but no check requires that its `agency_id` equals the transaction's `guard.current_agency()`. The worker trusts a valid `args_mac` before minting its own tenant token.
- Failure scenario: a web handler accidentally passes a client-supplied or wrong agency B id to `enqueue_in_tx` while serving agency A. The app signs it, so the worker mints a valid B token and can read B rows. MAC verification proves the job came from the app, not that it was authorized for A.
- Why it matters: a web bug can cross the tenant boundary through an async job even if injected SQL cannot forge the token.
- Required correction: derive `agency_id` inside `enqueue_in_tx` from the verified current transaction rather than accepting it independently, or reject a mismatch before signing; ensure each job's referenced rows are checked under that tenant. Test wrong-agency enqueue from a valid A transaction.
- Owner: builder
- Verification: an A transaction cannot enqueue a valid B job, and a forged B job cannot enter `with_agency(B)`.
- Status: open

### [P2] A plain audit hash chain does not detect forged appended events
- Category: spec mismatch
- Rule: T19; UNI-10
- Evidence: spec lines 138, 232–245 and 431. The app role may INSERT `audit_event`; the row has `prev_hash` and `hash`, and §4.2 says forged audit rows are detectable by the app-side hash-chain check. No keyed MAC, external sequence anchor or trusted signer is specified for an inserted row.
- Failure scenario: SQL running as `skiw_app` reads the latest event and inserts a fabricated next event with a correctly calculated `prev_hash` and `hash`; a plain chain verifier accepts it.
- Why it matters: the documented detection claim overstates what the audit control proves during incident investigation.
- Required correction: either limit the claim to detecting edits/removals while preserving valid append order, or add an app-keyed event MAC / trusted external anchor that arbitrary app-role SQL cannot compute, with an insertion-forgery test.
- Owner: builder
- Verification: the test inserts a syntactically valid forged event under `skiw_app`; the chosen integrity check detects it, or the threat model no longer claims that it will.
- Disposition: before merge
- Status: open

### Round 2 resolution audit

| Round 2 finding | Round 3 result | Evidence |
|---|---|---|
| Forgeable tenant GUC | Resolved against arbitrary SQL setting changes; new signed-job provenance gap above | D18 and §4.2, lines 76 and 179–270 |
| Pre-tenant hash exposure | Resolved in design with opaque ciphertext and definer hardening | §4.1, lines 112–114 and 162–177 |
| Premature scan-step completion | Resolved in design | D25 and Flow 5.7, lines 83 and 361 |
| Lost notification race | Resolved in design with waiter-first check and race test | D26 and M14, lines 84 and 519 |
| Append-only ledger lacked settlement | Event model specified; new hard-cap expiry defect above | §4.1 and Flow 5.8, lines 140 and 363 |
| Drive operation before client | Resolved in design | D25 and Flow 5.6, lines 83 and 359 |
| Schema-check exceptions | Resolved | §4.1–4.2 and M4, lines 110, 133, 141, 248–258 and 509 |
| Drive policy release gate | Resolved | D25, M16 and Q24, lines 83, 521 and 566 |

### Self-check audit

`PROJECT.md` remains unfilled. Applicable packs from the spec are universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records; public-links and payments are out of scope. No PR self-check or application implementation exists locally, so rule-level execution remains unverified. No instruction-like content in the spec directed the reviewer to alter the verdict or skip a gate.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `266abf435872704ed95d7b467107b2482ab20602`. |
| Read spec v1.2, previous review rounds, decisions log and applicable guardrails | Eight round-two changes re-inspected; four new findings recorded. |
| Old-repo access | The decisions log names the old private repo; prior `gh api` attempt failed due connection and invalid token. No source code or runtime checks were performed. |

### Residual risks and test gaps
- The old application's source is remotely identified but was not accessible for this round; all Doc1/Doc2 claims remain document evidence, not code-verified facts.
- No new-platform source, CI, staging or Git repository is present locally.
- Owner decisions on Google Workspace, Drive filing, AI cross-border use, CRM terms and client display code remain open, with the spec's named release gates where applicable.

### Required before merge
- Resolve the P0, both P1 findings and the P2 marked `before merge`; bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 2 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.1 · hash (`git hash-object`) `0ebdd25eff3803609b059034ec56bdb55646ec0b`
- **Code review:** n/a; this folder still has no application source or Git repository.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can address the specific design and sequencing issues below.

### Findings

### [P0] The tenant GUC does not contain arbitrary SQL injection
- Category: defect
- Rule: D4, D18, T1; TEN-02/09/11
- Evidence: spec lines 55, 69, 166–168, 187–189 and 329. T1 explicitly includes SQLi and says RLS stops cross-tenant reads, but the policy trusts `current_setting('app.agency_id')`. [PostgreSQL accepts arbitrary two-part custom settings](https://www.postgresql.org/docs/17/runtime-config-custom.html); `skiw_app` can set this one through the same SQL channel used by `with_agency()`.
- Failure scenario: a SQL injection that can execute a statement runs `set_config('app.agency_id', '<other agency uuid>', true)` within its transaction, then reads or changes that agency's rows under the current RLS policy. `FORCE RLS` and `NOBYPASSRLS` still apply, but they now evaluate against the forged tenant value.
- Why it matters: the stated database boundary against SQLi is false and could expose or alter another agency's client records when multi-agency use begins.
- Required correction: either make the tenant identity in the RLS predicate unforgeable by arbitrary SQL available to `skiw_app` (and test an attacker-set tenant), or explicitly remove SQLi containment from T1/D4 and require a separately justified control before multi-agency launch. A rule banning plain `SET` in application source does not stop injected SQL.
- Owner: builder
- Verification: under the production runtime DB role, an attacker-controlled SQL statement cannot switch to agency B and read or write B's rows; a regression test attempts `set_config` inside agency A's transaction.
- Status: open

### [P1] Pre-tenant lookup exposes cross-agency password hashes to the app role
- Category: security defect
- Rule: T1; TEN-10/12; AUTH-04/05
- Evidence: spec lines 153–157 grant `skiw_app` execution of `auth_lookup_login(email)`, owned by a `BYPASSRLS` role, and return `password_hash`, status, user ID and agency ID for any email. The spec does not define `REVOKE EXECUTE FROM PUBLIC` or a safe function `search_path`. [PostgreSQL's SECURITY DEFINER guidance](https://www.postgresql.org/docs/current/sql-createfunction.html) requires careful EXECUTE grants and a trusted search path.
- Failure scenario: SQL executing as `skiw_app` repeatedly calls the function with guessed emails and obtains password hashes and account metadata across agencies despite the RLS policy. An unsafe search path would add a separate privilege-escalation route.
- Why it matters: the authentication escape hatch weakens the tenant boundary and increases account-takeover impact from a DB-level injection.
- Required correction: move password verification into a narrowly scoped definer function that returns only a uniform authentication result, or otherwise keep raw hashes inaccessible to arbitrary `skiw_app` SQL; revoke default PUBLIC EXECUTE, pin a trusted `search_path`, and test direct function calls under `skiw_app`.
- Owner: builder
- Verification: direct SQL under `skiw_app` cannot enumerate cross-agency hashes or account status; function privileges and search path are asserted in migrations/tests.
- Status: open

### [P1] A scan case step is completed before the file is filed
- Category: defect
- Rule: D25; Flow 5.7; T13
- Evidence: spec lines 123, 278 and 295. The confirmation transaction ticks `case_step` and assigns `evidence_doc_id`; the asynchronous Drive move can later fail or end in `verify_failed`.
- Failure scenario: Drive rejects the move, yet the case UI shows the step complete and points to evidence that is still in the Scans inbox.
- Why it matters: case progress and evidence can be falsely finalized, affecting adviser work and audit review.
- Required correction: keep the case step pending after confirmation; mark it done with `evidence_doc_id` only after the Drive operation's read-back is `verified`, in one local transaction. Define the failed-operation UI and retry path.
- Owner: builder
- Verification: a forced Drive permission error or read-back mismatch leaves the case step incomplete and visible for recovery; successful verification completes it once.
- Status: open

### [P1] The long-poll can miss a notification between lease and waiter registration
- Category: defect
- Rule: D26; M14 latency acceptance
- Evidence: spec line 77 orders the poll to query for a job, then register an `asyncio.Event`; lines 272 and 432 promise `NOTIFY` wakeup and delivery within one second p95.
- Failure scenario: a job commits after the empty lease query but before registration. The listener finds no waiter, so the poll sleeps until its 25-second timeout even though work is queued.
- Why it matters: the bridge recreates intermittent lag and can fail M14's own acceptance criterion.
- Required correction: register the waiter before the final empty-queue check (or use an equivalent sequence/condition protocol), and remove it in `finally`. Add a deterministic race test that inserts a job at this boundary.
- Owner: builder
- Verification: a job committed at every boundary between check, registration and wait wakes or is seen immediately; no waiter leaks after timeout/cancellation.
- Status: open

### [P1] The AI spend ledger cannot settle as currently specified
- Category: guardrail mismatch
- Rule: T9; TEN-03; MON-01/05
- Evidence: spec lines 63, 133, 183 and 280. `ai_usage_ledger` is append-only with INSERT/SELECT only, yet the call flow reserves cost and later settles the same request; the row has `reserved_minor` and `settled_minor` but no event type, release link or definition of an open reservation.
- Failure scenario: updating a reservation to its actual settled cost is denied; inserting another positive row double-counts spend, while a failed call cannot release its reservation in the stated model. The hard monthly cap becomes inaccurate.
- Why it matters: the budget gate is a money-control path and must remain correct under failures and parallel calls.
- Required correction: specify an append-only reservation/settlement/release event model keyed by `request_id`, including signed deltas, currency and an atomic cap calculation, or separate a mutable reservation table from the append-only usage ledger. Define expiration of abandoned reservations.
- Owner: builder
- Verification: concurrent reserve/settle/release and worker-crash tests prove the cap cannot be exceeded or permanently consumed by an abandoned call.
- Status: open

### [P1] The Drive folder operation is recorded before its client exists
- Category: spec mismatch
- Rule: D25; Flow 5.6; EVT-01
- Evidence: spec lines 123 and 276. Step 1 inserts `drive_operation(create_folder)` in the person's Closed-won transaction; step 2's later job creates the `client` that the operation must reference and whose display code names the folder.
- Failure scenario: a required client FK cannot be populated when the operation is inserted, or the Drive worker starts before client creation and has no client identity/folder name to use.
- Why it matters: this path cannot reliably meet the same-transaction journal and idempotent folder creation promises as written.
- Required correction: create the local client and folder-operation row in the same transaction as the Closed-won event, or add an explicit source reference and dependency state so the operation becomes executable only after client creation. Define the `client_id` nullability and uniqueness accordingly.
- Owner: builder
- Verification: a concurrent-worker test shows Closed-won creates exactly one client and one executable folder operation, with a valid same-agency FK and no early Drive call.
- Status: open

### [P2] The schema checker needs explicit exceptions for the tenant root and key-only tables
- Category: spec mismatch
- Rule: TEN-04/08; §4.2
- Evidence: spec lines 90, 103, 126, 134 and 184. The schema check says every non-global table has `agency_id` and `unique(agency_id, id)`, but `agency` has no `agency_id` and is not in the complete global list; `bridge_nonce` and `setting` are described without an `id` even though the check requires one.
- Failure scenario: M4's specified schema gate fails on compliant intended tables or a builder silently weakens the gate.
- Why it matters: the gate should make tenant omissions visible without false failures.
- Required correction: give `agency` a named root-table exception with an `id`-based RLS check, and either explicitly give key-only tables an `id` plus the required unique constraint or specify their composite primary-key equivalent in the schema checker.
- Owner: builder
- Verification: M4 schema-check fixtures pass for these declared cases and fail for an undeclared table missing a tenant key.
- Disposition: before merge
- Status: open

### [P2] Gate the unapproved Drive filing policy before M16
- Category: material risk
- Rule: D25; M16
- Evidence: spec lines 76, 434 and 479. D25 selects no step-up for Drive mutations but says the owner must confirm Q24; M16 can meet its listed acceptance criteria without that answer.
- Failure scenario: document filing ships under a permission policy the owner declined or never decided.
- Why it matters: the spec correctly treats the AI transfer choice as a release gate; the Drive approval choice also changes live authorization behavior.
- Required correction: require a recorded Q24 decision before enabling Drive writes, or specify a conservative default that meets either answer.
- Owner: owner for the policy decision; builder for the milestone gate
- Verification: the M16 enablement gate fails with Q24 undecided and passes only with the selected policy configured and tested.
- Disposition: before merge
- Status: open

### Round 1 resolution audit

| Round 1 finding | Round 2 result | Evidence |
|---|---|---|
| Tenant columns and tenant-consistent FKs | Resolved in design; new schema-check inconsistency above | §4.1–4.2, lines 90–190 |
| Approval and execution evidence | Resolved in design; implementation unverified | D11 and §4.3, lines 62 and 192–245 |
| Drive write policy | Resolved in design; Q24 release gate above | D25 and §5.10, lines 76 and 284–298 |
| CRM crash/idempotency behavior | Resolved in design | §4.3 and Flow 5.5, lines 247–262 and 274 |
| Procrastinate transaction handoff | Resolved with explicit M0 verification and fallback | D5 and M0, lines 56 and 418 |
| Async long-poll boundary | Resolved in design; new notification race above | D26 and M14, lines 77 and 432 |
| Outbox milestone order | Resolved | M9 before M10/M11, lines 427–429 |
| Haiku 4.5 transfer gate | Resolved | D12, M11 and Q13, lines 63, 429 and 468 |

### Self-check audit

`PROJECT.md` is still unfilled. I derived applicability from the spec: universal, tenancy/RLS, auth, events/jobs, files/templates, money, frontend and finalized records. Public-links and payments remain outside the stated scope. A builder PR self-check does not yet exist for this pre-setup spec. The newly identified defects are listed above; no implementation-level rule can be verified without source.

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `0ebdd25eff3803609b059034ec56bdb55646ec0b`. |
| Read spec v1.1, previous review, decisions log, reviewer instructions and applicable guardrails | Eight round-one changes re-inspected; eight new findings recorded. |
| [PostgreSQL custom settings](https://www.postgresql.org/docs/17/runtime-config-custom.html) and [SECURITY DEFINER guidance](https://www.postgresql.org/docs/current/sql-createfunction.html) | Confirmed the GUC and definer-function risks described above. |
| [Google Drive file creation guidance](https://developers.google.com/workspace/drive/api/guides/create-file) | Pre-generated IDs support ordinary files and folders; no finding on that revised choice. |

### Residual risks and test gaps
- No source, CI, staging or Git repository is present here; architecture and acceptance tests remain unexecuted.
- `PROJECT.md` is not reconciled; its identity, pack selection and project-specific rules remain unavailable.
- Owner answers on CRM terms, Google Workspace, Drive filing approval and AI cross-border use remain outstanding and need the release gates stated in the spec or above.

### Required before merge
- Resolve the P0, all five P1 findings, and both P2 findings marked `before merge`; bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.

## Round 1 — 2026-10-05 · scope: feature-complete spec
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.0 · hash (`git hash-object`) `5338c32b679a75de4a1b5a6ff9d3f9c4a28a3a2c`
- **Code review:** n/a; this folder has no application source and is not a Git repository.

**Verdict:** Revision required
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can address the concrete spec gaps.

### Findings

### [P1] Specify tenant columns and tenant-consistent foreign keys for every business table
- Category: guardrail mismatch
- Rule: TEN-04–08; D18
- Evidence: spec lines 63, 73 and 82–114. D18 says every business table has `agency_id`, but the listed columns for `goal`, `fund_holding`, `review`, `case`, `form_instance`, `bridge_result`, `ai_message` and others omit it. Relationships use single-column IDs without tenant-consistent foreign keys.
- Failure scenario: a migration follows the table definitions literally, leaving tables that cannot have the specified `agency_id` RLS policy. Even with an agency column, a row for agency A can reference a client or user from B unless the relationship is constrained.
- Why it matters: the promised database tenant boundary would be incomplete or permit cross-tenant references.
- Required correction: list `agency_id` explicitly for every tenant-owned table, identify genuinely global tables, and require composite tenant-consistent foreign keys or an equivalent DB constraint for cross-table references. Specify RLS `USING` and `WITH CHECK` plus isolation and cross-tenant-FK tests for each table.
- Owner: builder
- Verification: schema checklist covers every table; migrations fail on an agency-A row pointing at an agency-B parent; read and write RLS tests pass under `skiw_app`.
- Status: open

### [P1] Make approval and execution state enforce the stated human gate
- Category: defect
- Rule: D11; T10; AUTH-09
- Evidence: spec lines 56, 106, 126, 174 and 261. The stated DB `CHECK` tests only `approved_by` for `executing` and `succeeded`; it does not require `approved_at` or `stepup_at`, prevent a payload edit after approval, or define what happens when execution starts more than five minutes after step-up.
- Failure scenario: an approved job waits for CRM reconnect, then executes against a changed payload or with a stale step-up. The advertised DB invariant does not reject the row.
- Why it matters: the central “a person submits” control would depend on unrecorded state transitions and can no longer prove what the person approved.
- Required correction: freeze/version the approved payload and diff, constrain required approval fields for every post-approval state, define who may transition each state, and define expiry/reapproval behavior for delayed jobs. Test mutation and delayed execution through the executor and DB constraints.
- Owner: builder
- Verification: tampering with an approved payload or moving to execution without all approval evidence fails; expired approval requires a new step-up or a documented approval snapshot policy.
- Status: open

### [P1] Reconcile the “every outside write” rule with Drive writes
- Category: spec mismatch
- Rule: D11; T10
- Evidence: spec lines 56 and 106 restrict `external_action` to CRM operations, while lines 128 and 130 create a Google Drive folder and move a file through background jobs. Line 58 also adds Drive filing.
- Failure scenario: an automatic job creates or moves a client document without the approval, audit and retry controls that D11 says cover every outside write.
- Why it matters: builders can implement two conflicting interpretations of the product’s main human approval invariant.
- Required correction: either include Drive/Calendar external mutations in the outbox with explicit approval policy, or narrow D11 to regulated portal/CRM writes and define a separate, testable authorization and audit policy for document filing.
- Owner: builder
- Verification: an inventory of all external mutation endpoints maps each to its authorization, approval, audit, idempotency and verification path; tests exercise the Drive paths.
- Status: open

### [P1] Treat CRM write outcomes as unknown after an interrupted POST
- Category: defect
- Rule: D11; EVT-05
- Evidence: spec lines 106, 126 and 263 say a local `idempotency_key` prevents double posting and that replay sends once, but no CRM-side idempotency capability is identified.
- Failure scenario: CRM commits a create-task POST, then the worker dies before recording success. Retrying the same local row sends another POST and can create a duplicate; a read-back after the first POST never ran.
- Why it matters: retries can corrupt the CRM despite the promised once-only behavior.
- Required correction: define an `outcome_unknown` state and per-operation recovery: use CRM-side idempotency if supported, otherwise reconcile by stable external reference/fingerprint before retry and require manual resolution where a unique match is impossible. Remove the unqualified “sends once” claim.
- Owner: builder
- Verification: fault-injection test kills the executor after remote success and before local commit; recovery does not issue a second unsafe write.
- Status: open

### [P1] Specify how Procrastinate shares the Django transaction
- Category: material risk
- Rule: EVT-01; D5
- Evidence: spec lines 50, 124 and 128 promise atomic data and job insertion but do not name the connector/connection handoff. [Procrastinate’s documentation](https://procrastinate.readthedocs.io/en/main/howto/production/external_connection.html) says same-transaction deferral requires passing the externally managed connection; a normal defer can use another connection.
- Failure scenario: a database write rolls back while its job commits independently, or the write commits while job enqueue fails.
- Why it matters: the design’s reason for choosing a Postgres queue, and several flows, depend on atomic enqueue.
- Required correction: name the transaction integration with Django’s connection, the exact defer API, and a rollback/commit test. Keep job arguments to IDs as specified.
- Owner: builder
- Verification: integration tests prove both data and job disappear on rollback, and both appear on commit, using the production connector configuration.
- Status: open

### [P1] Resolve the async long-poll and transaction boundary
- Category: material risk
- Rule: D1; D10; TEN-09
- Evidence: spec lines 46, 55, 63, 124 and 264 promise that 50 long polls use fewer than one worker thread while every request runs through a transaction helper. [Django 5.2’s async documentation](https://docs.djangoproject.com/en/5.2/topics/async/) says synchronous middleware keeps a thread open during long requests and ORM transactions are not supported in async mode.
- Failure scenario: a synchronous tenant/session middleware or a transaction held across the 25-second wait consumes one thread and DB connection per bridge poll, reproducing the current latency problem.
- Why it matters: the chosen ASGI deployment alone does not deliver the stated concurrency target.
- Required correction: specify an async-safe long-poll stack, short tenant-scoped DB transactions around authorization/lease work, and how notifications are received without one dedicated DB connection per device. State how TEN-09 is met across those short operations.
- Owner: builder
- Verification: load test with production middleware and 50 polls measures thread and DB connection counts, cancellation cleanup, and tenant isolation.
- Status: open

### [P1] Move the outbox milestone before features that require it
- Category: spec mismatch
- Rule: §9 milestone “done when”
- Evidence: spec lines 259–261. M9 requires drafts to appear in the outbox and M10 allows `draft_crm_task`, but M11 first builds the outbox/executor framework.
- Failure scenario: M9 and M10 cannot meet their stated acceptance criteria in milestone order; a builder may invent a temporary draft path and later migrate it.
- Why it matters: the delivery sequence encourages duplicate, unreviewed write paths.
- Required correction: move the minimal draft/outbox model and API before M9, or move M9/M10 after M11; keep the executor disabled until its safety controls pass.
- Owner: builder
- Verification: each milestone can pass its “done when” using only earlier milestones and its own scope.
- Status: open

### [P2] Make the Haiku 4.5 cross-border choice a release gate
- Category: material risk
- Rule: D12; D19; M10
- Evidence: spec lines 57, 64, 260 and 300. The spec prefers an APAC profile if available, but [AWS’s Haiku 4.5 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html) currently lists `ap-southeast-5` as Global only, with neither In-Region nor Geo availability.
- Failure scenario: M10 ships via Global inference while Q13 remains unanswered, or cannot ship after Global processing is declined.
- Why it matters: AI chat is an existing feature and Global inference can process prompts outside Malaysia.
- Required correction: name Global as the current Haiku 4.5 route; make the owner’s transfer decision and TIA/exception a pre-M10 gate, with an explicit approved fallback or a blocked milestone if declined.
- Owner: owner for transfer decision; builder for gate and fallback design
- Verification: M10 acceptance requires a recorded transfer decision and a test/config check that rejects unapproved inference profiles.
- Disposition: before merge
- Status: open

### Self-check audit

`PROJECT.md` is unfilled, so guardrail applicability was derived from the spec. No builder self-check table exists for this pre-setup spec; the PR self-check gate cannot yet be applied. Applicable packs: universal (all), tenancy/RLS, auth, events/jobs, files/templates, money, frontend, and finalized records for generated forms. Public-links and payments have no in-scope flow. The findings above address failed or ambiguous rules; code-level compliance cannot be checked without source.

### Verification performed

| Command / check | Result |
|---|---|
| `nl -ba docs/specs/2026-10-05-skiw-platform-stack-design.md` | Reviewed version 1.0 and cited lines. |
| `git hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `5338c32b679a75de4a1b5a6ff9d3f9c4a28a3a2c`. |
| `cat agents/START.md agents/PROJECT.md agents/roles/reviewer.md` and relevant guardrails | Reviewed workflow and requirements; project setup is incomplete. |
| `cat docs/DECISIONS.md` | Header only; no prior approved choices recorded. |
| Official Procrastinate, Django and AWS documentation | Checked atomic enqueue, ASGI thread behavior, and Haiku 4.5 regional availability. |

### Residual risks and test gaps
- No application source, CI, staging, preview, or Git repository is available here; all implementation claims remain unverified.
- The owner’s budget, CRM terms/session lifetime, Google Workspace status, data transfer decision and role definitions remain open as documented in §10. They do not prevent this spec review, but dependent milestones need explicit gates.
- `PROJECT.md` has unresolved setup fields; its identity, source-of-truth paths, guardrail ticks and project-specific constraints could not be used.

### Required before merge
- Resolve all seven P1 findings and the P2 marked `before merge`; bump the spec version and request another spec review.

### Deferred conditions
- None.

### Optional improvements
- None required for this round.
