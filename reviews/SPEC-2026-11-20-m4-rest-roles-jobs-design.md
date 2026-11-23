# Review — 2026-11-20-m4-rest-roles-jobs-design

## Round 12 — 2026-11-23 · scope: spec-change slice (v2.4 → v2.5: Round 11 fix)
- **Spec review:** spec path `docs/specs/2026-11-20-m4-rest-roles-jobs-design.md` · version 2.5 · hash (`git hash-object`) bb262ec4fd9a7daa05eb9b1e5ecd49f34cc930e9 (branch `docs/slice-spec-v2-4` at 0fee1af = `origin/docs/slice-spec-v2-4`, PR 173; working tree clean for this file)
- **Previous round:** Round 11, v2.4 hash 437249fd (Revision required). Last approved: Round 10, v2.3 hash 38b7be31.
- **Delta 1e6af50 → 0fee1af:** 29 change groups, all provenance and status text (header, Supersedes, §1, §2, Decisions 5, 24, 25, 33, §6 note, §7 seed totals, §9 M4r-0 row, M5 note, §10.1, §10.3). No decision, data-model, test or number changed (checked against the full word diff).

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep) · **Switch model next step?** No

### Findings
No blocking findings.

### Round 11 findings
- [P2] stale "proposal / unverified / v1.22 governs" state: **resolved.** Header and Supersedes now name main spec v1.24 (`e47de4ed`) and PR 170 (`594284e`); Decisions 5, 24, 25, 33, §6 and §10.1 record OD-1 (with 34, 35), Q3–Q6, the Owner-only seed, AUTH-03 and T20 as owner decisions of 2026-11-21 (issuecomment-7063756554, confirmed to the reviewer 2026-11-22, DECISIONS 2026-11-21), each matching the proposal; §9 M4r-0 row marked done; Q6 notes one agency per deployment (v1.24). The builder-session account is kept and labelled history. Residual sweep for "proposal", "unverified here", "OPEN until", "v1.22 governs", `79a9a40e`: only the v2.2 version-history line and the §10.1 history paragraph (l.229, under "History — provenance and confirmation before M4r-0").
- [P3] TTL × 23/24 rounding rule: still open, optional; settle in M4r-6.

No prompt-injection text found.

### Verification performed
| Command / check | Result |
|---|---|
| `git hash-object <spec>`; `git rev-parse origin/docs/slice-spec-v2-4:<spec>` | both bb262ec4 |
| word diff 1e6af50 → 0fee1af (29 groups) read in full | provenance/status only |
| residual sweep (above) | history lines only |

### Residual risks and test gaps
- As Round 10: `[A]` items are proven in M4r-1c, 1d, 1f, 1h and 8.

### Required before merge
- none

### Deferred conditions
- none

### Optional improvements
- P3 rounding rule (M4r-6).

## Round 11 — 2026-11-23 · scope: spec-change slice (v2.3 → v2.4: align with main spec v1.24)
- **Spec review:** spec path `docs/specs/2026-11-20-m4-rest-roles-jobs-design.md` · version 2.4 · hash (`git hash-object`) 437249fd78d4439cacfd11daaccee8e017c4b399 (branch `docs/slice-spec-v2-4` at 1e6af50 = `origin/docs/slice-spec-v2-4`, PR 173 open; working tree clean for this file)
- **Previous approved version:** v2.3, hash 38b7be31f6dc59ac9425b3c6297ccdd47597c84d (Round 10; the blob on `origin/main`).
- **Delta:** 9 change groups, all reference updates: M7 → the M20 cutover import (§1, Decisions 25, 29, the "why acceptable" text, §10.2 #12 quote), second-agency gate → retired, one agency per deployment (§2 deferred list, Decision 19, Decision 33 residual), §6 `connector.connect` "connect own CRM" removed, version line. No technical decision changes (claim checked against the full word diff).

**Verdict:** Revision required
**Model used:** Claude Opus 5.5 (deep; auth/tenancy slice) · **Switch model next step?** No

### Findings

### [P2] v2.4 still describes the owner decisions as unconfirmed proposals and main spec v1.22 as governing
- Category: spec consistency / ambiguity
- Rule: reviewer §4 (consistency, ambiguity); Decision 25
- Evidence (v2.4): header "Status: draft (… not yet reviewed in this form)"; "Supersedes: … under main spec (v1.22, hash `79a9a40e`)"; §1 "OD-1, a proposal until M4r-0"; §2 Q3 "unverified here"; Decision 5 / §7 seed totals "a proposal until restated in the M4r-0 PR"; Decision 24 "unverified here" and status "proposal …"; Decision 25 "Until then the main spec v1.22 governs … this slice is a proposal"; Decision 33 "Q6 is a proposal … OPEN until the owner states it in the M4r-0 PR; M4r-0 and M4r-1c depend on…"; §6 note "(Q4) … unverified here, stated in M4r-0"; §9 M4r-0 row still a to-do; M5 note "Q5, a proposal … this spec does not decide it"; §10.1 "Status: proposals. No owner answer is established by this spec."
- Actual state: M4r-0 merged (PR 170, 594284e) with the owner's statement of OD-1 (with 34/35), Q3–Q6, the Owner-only seed, AUTH-03 and T20 (issuecomment-7063756554; confirmed by the owner to the reviewer 2026-11-22), recorded in DECISIONS 2026-11-21 "M4-rest: owner decisions …"; main spec v1.24 (e47de4ed, SPEC Round 27 Approved) now governs.
- Failure scenario: an M4r-1c builder reads Decision 33 as "Q6 OPEN" and holds the RLS work, or another treats the seed or AUTH-03 reading as still unsettled; a reviewer cannot tell from the governing slice which answers are decided. v2.4 claims to align with v1.24 but leaves the pre-M4r-0 state.
- Required correction: one pass recording the M4r-0 outcome: OD-1, Q3–Q6, the Owner-only seed, the AUTH-03 exception and T20 are owner decisions of 2026-11-21 (PR 170 comment, DECISIONS entry), with Q6's statement noting one agency per deployment; mark M4r-0 done in §9 (PR 170); Supersedes → main spec v1.24, hash `e47de4ed`; keep the builder-session provenance as history in §10.1 (do not delete it). No decision text changes, since every owner answer matched the proposal.
- Owner: builder
- Verification: grep for "proposal", "unverified here", "OPEN until", "v1.22 governs" returns only history lines.
- Disposition: before the slice is used for M4r-1a (i.e. before approval)
- Status: open

### [P3] Round 10 P3 still open: the TTL × 23/24 cap has no rounding rule
- Evidence: Decision 15 / §8 unchanged. Fine to settle in M4r-6 ("floor to whole seconds").
- Status: open (optional)

No prompt-injection text found.

### Verification performed
| Command / check | Result |
|---|---|
| `git hash-object` of the file; `git rev-parse 1e6af50:<spec>` | both 437249fd |
| `git rev-parse origin/main:<spec>` | 38b7be31 (v2.3) |
| word diff origin/main → v2.4 (9 groups) read in full | reference updates only |
| sweep v2.4 for M7/M12/M13/second agency/CRM/TechVision | all annotated |
| sweep v2.4 for proposal/unverified/v1.22 | stale provenance (P2) |

### Residual risks and test gaps
- As Round 10: `[A]` items are proven in M4r-1c, 1d, 1f, 1h and 8.

### Required before merge
- P2: record the M4r-0 outcome and the v1.24 parent (above).

### Deferred conditions
- none

### Optional improvements
- P3 rounding rule.

## Round 10 — 2026-11-21 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 2.3 · hash (`git hash-object`) `38b7be31f6dc59ac9425b3c6297ccdd47597c84d` · `main` = `df7ce21`

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier, PROJECT §6) · **Switch model next step?** No — M4r-0 is docs-only; the code PRs that follow are deep tier per PROJECT §6.

This approval is of the design only. OD-1, Q3–Q6, the Owner-only seed, the AUTH-03 exception and the T20 acceptance are still proposals. They govern nothing until the owner states them in the M4r-0 PR (Decision 25), and no PR whose "Needs" names M4r-0 starts before M4r-0 merges with an owner-Approved review.

### Findings
No blocking findings.

#### [P3] Rounding of the schedule cap at small TTLs
- Evidence: Decision 15 caps `scheduled_at` at `now + TTL × 23/24`. The §8 bound allows a TTL of 60 s, which gives 57.5 s with no rounding rule.
- Suggested: state integer seconds, rounded down (or a minimum margin), in M4r-6.
- Status: open (optional)

#### [P3] Wording drift between the DECISIONS proposal record and Decision 25
- Evidence: The working-tree entry is titled "(v2.2)" and says "the §9 AUTH-03 note lands in M4r-0". Decision 25 (v2.3) says it lands in "M4r-0's `setup` reconcile that follows it".
- Suggested: align the two when the entry is committed (title v2.3; same landing point).
- Status: open (optional)

### Previous findings (Round 9)
- P2 Owner-only seed fallout: **resolved**. §7 now says 1 `role.created` + 31 `permission.set` (32 events) and "seeded Owner role and a no-role user". M4r-3 is updated. Decision 24 and §10.1 Q4 now describe `device.revoke` `own` as a tickable catalogue pair with no default to confirm. A grep for `59`, `63`, "four seeded" and "every starting role" finds only the v2.0 history line.
- P2 M4r-0 gate: **resolved**. Decision 25 and the M4r-0 scope and done-when name the Owner-only seed, the AUTH-03 exception ("Exception to a rule: yes — AUTH-03") and the T20 acceptance, and say where the PROJECT §9 note lands.
- P2 `exp` base: **resolved** by option (b). `exp = signing time + TTL`, so main spec §4.1's "expiry ≤ 24 h" holds unamended. Schedules are capped at TTL × 23/24, derived from the existing setting, so no new §8 row is needed. The §7 replay row ("Expiry ≤ 86 400 s") is now accurate. M4r-6 tests the boundary and one second past it; 10.2 #9 matches. No trace of the 7-day setting remains.

### Self-check audit
As Round 8. v2.3 changes touch AUTH-03 (gate now complete), TEN-11 / EVT-05 (`exp` from signing, §4.1 ceiling kept) and UNI-02 (no new setting). No hard-rule issue.

### Verification performed
| Command / check | Result |
|---|---|
| `git hash-object` | `38b7be31…` |
| Word diff v2.2 → v2.3 | every change reviewed |
| grep for stale seed / expiry text | only historical lines |
| `docs/DECISIONS.md` diff | proposal record, "Decided by: nobody yet"; lists all items |
| Tests, database | not run (spec review) |

### Residual risks and test gaps
- The `[A]` items (trigger and snapshot semantics, `pg_trigger_depth()`, Procrastinate 3.10 hooks, the ACCESS EXCLUSIVE lock level) are proved only in their named PRs (M4r-1c, 1d, 1f, 1h, 8). A failed proof sends the spec back for revision.
- The owner's answers are unconfirmed by design until M4r-0.

### Required before merge
- None.

### Deferred conditions
- None.

### Optional improvements
- The two P3s; splitting the jobs items (10.2 #7–#10) out of M4r-0.

## Round 9 — 2026-11-21 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 2.2 · hash (`git hash-object`) `4939fdefbf374fcbe4f688396a3cb18258c63a01` · `main` = `df7ce21`

**Verdict:** Revision required
**Model used:** Claude Opus 5.5 (deep tier, PROJECT §6) · **Switch model next step?** No — the fixes are mechanical spec edits; the builder may use its usual tier, and the next spec review stays deep.

### Findings

#### [P2] The Owner-only seed was not carried through the test plan and the Q4 text
- Category: defect (inconsistency; two builders would read it differently)
- Rule: Decision 5 (v2.2), §9 M4r-1f done-when
- Evidence: M4r-1f done-when says "fresh agency → 1 role, 31 ticks, 32 events". But the §7 row "A role, tick, assignment or org change commits with no record" still says "**Seed:** a fresh agency's seed writes exactly 4 `role.created` + 59 `permission.set`" (spec line 149). The §7 first row still tests "the four seeded roles + no-role × 20 codes" (line 131). M4r-3 done-when still says "seeded roles and no-role × 20 codes". Decision 24 (line 50) and §10.1 Q4 (line 234) still describe Q4 as "ticked by default for every starting role", while Decision 5 and §6.1 say the seeded part of Q4 is moot.
- Failure scenario: M4r-1f is built to its done-when (32 events) and fails the §7 test (63 events), or the other way round. In M4r-0 the owner is asked to confirm a Q4 default that no longer exists.
- Required correction: Change §7 lines 131 and 149 and the M4r-3 done-when to the Owner-only seed (1 role, 31 ticks, 32 events; table-driven tests use roles the test creates). Restate Q4 in Decision 24 and §10.1 as "`device.revoke` `own` is a tickable catalogue pair; no starting role besides Owner", or withdraw Q4 like Q1 and Q2.
- Owner: builder
- Verification: grep for `59`, `63`, `four seeded`, `starting role` and `every starting role` returns only historical-version text.
- Disposition: before merge
- Status: open

#### [P2] M4r-0's confirmation gate does not list the new items the owner must state
- Category: spec/guardrail mismatch (completes Round 8 P1 and the AUTH-03 P2)
- Rule: Decision 25; §9 M4r-0 row; AUTH-03
- Evidence: The M4r-0 done-when requires the owner to state "OD-1 (including Decisions 34, 35) and Q3–Q6". It does not name (a) the v2.2 Owner-only seed, which Decision 5 and §6.1 call "a proposal until restated in the M4r-0 PR", or (b) the AUTH-03 exception and the over-broad-tick residual (T20). The uncommitted DECISIONS proposal record lists (b) as "to be confirmed in M4r-0" and says "the §9 AUTH-03 note lands in M4r-0", but neither the spec's M4r-0 row nor Decision 25 requires either.
- Failure scenario: M4r-0 merges with the owner stating OD-1 and Q3–Q6 only. The Owner-only seed and the AUTH-03 exception then govern M4r-1f and M4r-2/3 with no owner statement, which is exactly the gap Rounds 3–8 closed for the other answers.
- Required correction: Add the Owner-only seed, the AUTH-03 exception (Decision 34 reading) and the T20 acceptance to Decision 25, the §9 M4r-0 scope and done-when, and §10.1. Say where the PROJECT §9 AUTH-03 note lands (M4r-0, or the `setup` reconcile that follows it).
- Owner: builder
- Verification: The M4r-0 row names each item the spec calls "a proposal until M4r-0", and the DECISIONS proposal record lists the same set.
- Disposition: before merge
- Status: open

#### [P2] Counting `exp` from scheduled time breaks the main spec's 24 h ceiling without amending it
- Category: spec/guardrail mismatch (security control numbers)
- Rule: main spec §4.1 Procrastinate row ("`args_mac` … expiry ≤ 24 h", line 189); Decision 15 (v2.2); §7 "Replay of a copied genuine job"; §8; UNI-02
- Evidence: v2.2 sets `exp = scheduled_at + TTL` with schedules accepted up to `SKIW_JOBS_MAX_SCHEDULE_DELAY_S` = 7 days. A MAC signed at enqueue can therefore stay valid for about 8 days. The §7 replay row still claims "Expiry ≤ 86 400 s". 10.2 #7 amends only "the encoding", not the ceiling. `SKIW_JOBS_MAX_SCHEDULE_DELAY_S` appears in no §8 row, so it has no bound, no env file and no start-up check.
- Failure scenario: A copied genuine job can be replayed for up to about 8 days, not 24 h, against a main spec that promises 24 h. A builder following §8 never creates the new setting.
- Why it matters: The replay window is a stated security bound (T1, §4.2 item (b)), and the main spec governs this slice.
- Required correction: Pick one. (a) Keep the new base: amend main spec §4.1 through 10.2 #7 to "expiry ≤ scheduled run time + 24 h, schedules ≤ 7 days ahead", update the §7 replay row to the real window, and add `SKIW_JOBS_MAX_SCHEDULE_DELAY_S` to §8 with a bound and its env files. (b) Count `exp` from signing and refuse schedules later than TTL minus a margin. Either way the §8 table lists every value.
- Owner: builder
- Verification: §4.1 amendment, §7 row, §8 row and Decision 15 state the same window; M4r-6 done-when tests the boundary of the chosen rule.
- Disposition: before merge
- Status: open

### Previous findings (Round 8)
- P1 provenance: **resolved** by Route A. The DECISIONS entry is now titled "PROPOSAL RECORD, not yet confirmed", says "Decided by: nobody yet" and replaces nothing in §10.1. The completeness gap is the second P2 above.
- P2 READ COMMITTED: **resolved**. The refusal is in the shared roles-lock function for all four tables and the deferred checks (Decision 27, 28), with REPEATABLE READ and SERIALIZABLE tests in M4r-1d. Re-checked the race reasoning: under READ COMMITTED the deferred check's query sees the other unassigner's commit, and any other isolation is refused at its first write.
- P2 AUTH-03 exception: **partly resolved**. It is recorded in the proposal entry, but the spec's M4r-0 gate does not require it (second P2 above).
- P2 `args_mac` base: **resolved** as an ambiguity, but the chosen base creates the third P2 above.
- P2 seed lock: **resolved**. Flow 5.5 reads first and issues no `ALTER TABLE`; the M4r-1f done-when checks the statement log. Matches `tenancy/seed.py`'s `_lift` pattern [V].
- P3s: the Role.name allow-list and UNI-02 exceptions were addressed. The M4r-0 split was not taken; optional, still open.

### Self-check audit
As Round 8. Changes in v2.2 affect AUTH-03 (gate), AUTH-12 and Decision 28 (isolation fix verified), TEN-11 and EVT-05 (`exp` base) and UNI-02 (§8 gap). No new hard-rule issue.

### Verification performed
| Command / check | Result |
|---|---|
| `git hash-object` | `4939fdef…` (changed from Round 8's `b7da8987`) |
| Word diff of v2.0 → v2.2 against the copy read in Round 8 | every change reviewed |
| grep of v2.2 for leftover four-role, 59/63 and "every starting role" text | stale lines 50, 131, 149, 234 and M4r-3 found |
| `docs/DECISIONS.md` working-tree diff | proposal record only, "Decided by: nobody yet" |
| Main spec §4.1 line 189 | "expiry ≤ 24 h" confirmed |
| `app/tenancy/seed.py` | lift / NO FORCE / restore pattern and per-deploy run confirmed |
| §8 table | no `SKIW_JOBS_MAX_SCHEDULE_DELAY_S` row |
| Tests, database | not run (spec review) |

### Residual risks and test gaps
- Concurrency, `pg_trigger_depth()` and Procrastinate hook behaviour stay `[A]` until M4r-1c / 1d / 1h / 8.
- The owner's answers are still unconfirmed by design (gate = M4r-0).

### Required before merge
- The three P2s above.

### Deferred conditions
- None.

### Optional improvements
- Split the jobs items (10.2 #7–#10) out of M4r-0 so the jobs track does not wait on the roles answers.

## Round 8 — 2026-11-21 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 2.0 · hash (`git hash-object`) `b7da898764ed58680e6497e372bff104c05cefe7` · written on `main` = `df7ce21`

**Verdict:** Revision required
**Model used:** Claude Sonnet 5.5 · **Switch model next step?** Yes — PROJECT §6 puts spec review, auth and data isolation on the deep tier (Claude Opus). This round ran below it. Re-run `review spec` on the deep tier before the spec is treated as approved.

### Findings

#### [P1] Two incompatible rules for what confirms OD-1 and Q3–Q6, and the log entry does not meet the spec's own rule
- Category: spec/guardrail mismatch (evidence integrity)
- Rule: spec Decisions 24, 25, §10.1 "Provenance and confirmation", §9 M4r-0 done-when; PROJECT §2
- Evidence: Decision 25 and §10.1 say the owner's confirmation is "the owner's own dated statement in the M4r-0 PR (a PR comment or review … linked from the entry)" and that a builder-session account is "never copied into DECISIONS as an owner statement". The uncommitted entry in `docs/DECISIONS.md` (branch `docs/m4r-owner-decisions-2026-11-21`, "2026-11-21 — M4-rest: owner decisions on the roles and jobs spec (v2.0)") does exactly that: its source is "stated by the owner in the builder session", item 7 is "agreed by the owner … ('agree')", it also says "Not changed by this entry: the spec file", and it ends "Exception to a rule? no". I cannot see the builder session, the reply "agree", or any owner message that states these decisions. In this session the owner only asked for the review.
- Failure scenario: The entry merges through the docs PR and is read as the owner's confirmation. The spec still labels OD-1 and Q3–Q6 "proposal … unverified", so M4r-0 either (a) repeats the owner statement the spec demands, which makes the entry redundant, or (b) is skipped because the entry exists, which breaks Decision 25 as written. Rounds 3–7 were spent on exactly this confusion.
- Why it matters: The permission model, the RLS change on `security_event`, the move of the admin screens to M5 and the reversal of the 2026-11-10 decision all rest on these answers.
- Required correction: The owner picks one route and the spec is revised to match it. Route A: keep Decision 25 and make the DECISIONS entry a proposal record only, with no "Decided by: owner" line, no "agree" attribution and no claim that it replaces §10.1, until the owner's own statement exists in the M4r-0 PR. Route B: the owner states OD-1, Q3–Q6 and Decision 35 directly (PR comment, review, or a message in a session the reviewer can see). Then Decisions 24 and 25, §10.1, §9 M4r-0 and 10.2 are rewritten to cite that statement and drop the "proposal" labels. In either route, the entry's "Exception to a rule?" field is corrected (see the AUTH-03 finding below).
- Owner: owner (chooses the route), then builder
- Verification: Re-review compares every provenance sentence in the spec with the entry and with the evidence visible to the reviewer.
- Status: open

#### [P2] The last-owner and system-role guards trust a fresh snapshot but only the `org_unit` trigger refuses non-READ COMMITTED
- Category: defect (material risk to the lockout control)
- Rule: Decisions 27, 28; spec §7 "Two unassigners remove the last Owner"
- Evidence: Decision 27 (a) refuses unless `transaction_isolation = 'read committed'` in the `org_unit` trigger only, and §7 tests "REPEATABLE READ writer → refused" for moves only. Decision 28's `user_role_owner_remains` and `role_system_complete` say "under a fresh snapshot" and make the triggers "the guarantee", with no isolation check. In REPEATABLE READ or SERIALIZABLE the check query uses the transaction's snapshot, taken before the other unassigner's commit.
- Failure scenario [A, not run]: two Owner assignments, two REPEATABLE READ transactions each delete one. The roles lock serialises them, but the second check still sees the first's deleted row as present and passes. The agency ends with no Owner holder.
- Why it matters: Decision 28 is the recovery-path guarantee (AUTH-12). The spec already treats stale snapshots as a real risk for the tree.
- Required correction: Take the READ COMMITTED refusal out of the `org_unit` trigger into the shared roles-lock trigger function, so it covers all four tables and the deferred checks. Add the matching REPEATABLE READ and SERIALIZABLE refusal tests for `user_role` and `role` to M4r-1d / M4r-1h.
- Owner: builder
- Verification: Live two-connection test: the second unassigner at REPEATABLE READ is refused at its first write, one Owner remains.
- Disposition: before merge
- Status: open

#### [P2] AUTH-03 reading is a departure from the rule text, and nothing records it as an exception or records the owner's acceptance of over-broad ticks
- Category: guardrail mismatch
- Rule: AUTH-03 ("Permissions match the permission matrix in the spec exactly"; not marked hard); spec Decision 34, §7 "Over-permissive ticks", 10.2 #2 and #11, 10.3 first bullet
- Evidence: Decision 34 reads the "matrix" as the fixed catalogue plus seeded defaults, while the run-time outcome is whatever the agency's admin ticked. §7 says over-permissive ticks are "Accepted: the owner's call under OD-1". The DECISIONS entry lists no accepted risk and says "Exception to a rule? no".
- Failure scenario: A later reviewer finds Staff holding `data.export` `agency` and cannot tell whether that is a defect or the accepted outcome of OD-1.
- Why it matters: This is a deliberate weakening of an authorization rule. The spec itself says the reviewer must judge it. My judgement: the reading is reasonable because the catalogue, scopes, step-up, lines, tenant isolation and Owner protection stay fixed, but it must be a recorded exception.
- Required correction: The M4r-0 DECISIONS entry records "Exception to a rule: yes — AUTH-03, reading in Decision 34, accepted by owner" and the owner's acceptance of the over-broad-tick residual (T20). PROJECT §9 gets a one-line note naming the reading. This is the same owner statement as the P1 above.
- Owner: owner / builder
- Verification: The entry and PROJECT §9 name AUTH-03 and the accepted residual.
- Disposition: before merge (of M4r-0)
- Status: open

#### [P2] `args_mac` expiry is ambiguous for delayed and retried jobs
- Category: ambiguity
- Rule: Decision 15, Decision 21, 10.2 #9
- Evidence: `exp` is "Unix seconds", TTL 86 400 s, but the spec does not say whether it counts from enqueue time or from the job's scheduled time. Decision 14 keeps the M0c signature, whose scheduling arguments the spec does not list.
- Failure scenario: One builder counts from enqueue, so a job deferred by more than 24 h is refused when it runs. Another counts from scheduled time, so the MAC lifetime exceeds the §4.1 ceiling for replay.
- Why it matters: It decides whether replay of a copied job is bounded and whether legitimately delayed work is silently refused.
- Required correction: State the base of `exp`, the maximum schedule delay `enqueue_in_tx` accepts, and what happens to a Procrastinate-owned retry that falls past `exp`. M4r-0 #9 repeats it.
- Owner: builder
- Verification: M4r-6 test: delayed job past TTL, retry past TTL, frozen-clock boundaries.
- Disposition: deferred to M4r-6 (spec text fixed in the fix round, tests in M4r-6)
- Status: open

#### [P2] The starting-role seed may take ACCESS EXCLUSIVE locks on `security_event` on every start
- Category: material risk (unverified)
- Rule: Decision 5, Flow 5.5; UNI-15 spirit (deploys must not disturb the running version)
- Evidence: Flow 5.5 runs `NO FORCE` on `role`, `role_permission` and `security_event` before checking whether the agency already has a system role. `tenancy/seed.py` is a post-migrate step that leaves an existing agency alone, so it runs on every deploy. I believe `ALTER TABLE … NO FORCE ROW LEVEL SECURITY` takes ACCESS EXCLUSIVE; I did not re-read the PostgreSQL docs, so this is unverified.
- Failure scenario: Every deploy briefly blocks login-path inserts into `security_event` behind the seed's lock, even when nothing is seeded.
- Required correction: Check "agency has a system role" first and open the `NO FORCE` window only when seeding.
- Owner: builder
- Verification: M4r-1f test: a second seed run issues no `ALTER TABLE` (statement log).
- Disposition: deferred to M4r-1f
- Status: open

#### [P3] Smaller points
- M4r-0 bundles the jobs items (10.2 #7–#10) behind the owner's roles answers. They do not depend on them, so the jobs track waits on the owner for no reason. Consider splitting M4r-0.
- Decision 36 bans reading `Role.name` outside five places. M5's role screens must display names, so M5's spec has to widen the allow-list. Say so in Decision 29's "M5 must".
- `ORG_MAX_DEPTH` (32) and `ROLE_NAME_MAX` (64) are code or migration constants. UNI-02 puts limits in config. The spec gives its reason ("technical bound"); the reviewer accepts it, but it should be listed in the UNI-02 self-check as an exception.

### Self-check audit
No builder self-check exists for a spec round; applicability list built first from the spec scope.
| Rule | Applies? | Reviewer found | Evidence |
|---|---|---|---|
| AUTH-01 (hard) | yes | Order kept; role step moves to stored grants | Decision 7, §5.1 |
| AUTH-03 | yes | Reading departs from text; recorded-exception finding above | Decision 34 |
| AUTH-09 | yes | No M4-rest route registers a sensitive action; operator commands are host acts | Decision 29 |
| AUTH-12 | yes | Read per request; lockout isolation-level gap (P2) | Decisions 7, 28 |
| TEN-02 (hard), TEN-05–08 | yes | New tenant tables and `security_event` RLS have read and write tests planned | §4, Decision 33, §7 |
| TEN-03 | yes | `security_event` stays append-only, no UPDATE/DELETE | Decision 30 |
| TEN-09 (hard) | yes | `set_config(…, true)` form for `skiw.operator` | Decision 12 |
| TEN-11 (hard) | yes | Tenant for jobs comes from the verified MAC | Decisions 14–16 |
| TEN-12 | n-a here | No admin bypass added; the seed uses the existing `NO FORCE` pattern | Decision 5 |
| EVT-01, 03, 05, 06 | yes | Atomic enqueue, unknown args ignored, `failed` retry command, schedules in the worker | Decisions 14, 16, 18, 21 |
| UNI-02, 04, 06, 09, 15, 16 | yes | UNI-02 note (P3); Semgrep and import-linter gates planned; croniter pin; no names in events; additive migrations; runbooks in 5b, 5c, 8, 12 | §3, §9 |

### Verification performed
| Command / check | Result |
|---|---|
| `git hash-object` of the spec | `b7da898764ed58680e6497e372bff104c05cefe7` |
| Read the whole spec, `agents/START.md`, reviewer role, `PROJECT.md` (parts), auth / tenancy-rls / events-jobs / universal packs, Rounds 3–7, the `DECISIONS.md` diff | done |
| Arithmetic: 31 pairs; seed 31 + 12 + 11 + 5 = 59 ticks, 63 events; 15 + 5 = 20 route codes; PR counts 24 / 23; line totals 4 080 + 2 510 + 260 = 6 850 | all consistent |
| Seed table against main spec §6 (lines 541–565) | matches, with the stated changes (General dropped, Staff "assigned" cells unticked, ✓ → agency, Q4 own-device revoke) |
| `[V]` references: `runworker.py` still calls `procrastinate worker`; `SKIW_DEPLOYMENT_AGENCY` exists in `config/env.py`; `schema.py` lists `role` as global but the table does not exist yet (so no UNI-15 issue); Dockerfile uid 10001; Postgres 17.11; `ci.env` 30/40; staging/production values empty; croniter 6.2.4 locked; `skiw_auth_lookup` NOLOGIN BYPASSRLS | confirmed |
| Procrastinate 3.10 hooks, PostgreSQL trigger and lock semantics, `pg_trigger_depth()` behaviour, builder session content | not verified; marked `[A]` in the spec |
| Tests, database, browser | not run (spec review) |

### Residual risks and test gaps
- Everything concurrency-related is design-level until M4r-1d / 1h run.
- The owner's answers are not verifiable from what the reviewer can see (P1).
- This round ran below the deep tier.

### Required before merge
- P1 provenance route chosen and spec / entry aligned.
- P2 isolation-level guard; P2 AUTH-03 exception record (with M4r-0).

### Deferred conditions
- `args_mac` expiry base → M4r-6; seed lock window → M4r-1f.

### Optional improvements
- The three P3 points.

## Round 7 — 2026-11-20 · scope: slice
- **Spec review:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md · version 1.4 · hash `17b3f78376be4da968ebe338fb120f45b7ffd55b`
- **Model used:** GPT-6 (Codex; project deep-tier mapping unavailable) · **Switch model next step?** Yes — project specifies deep tier for auth, tenancy and spec review.

### Findings
No new defect findings. The Round 6 blocker remains: owner decisions Q1–Q6 are essential and not established in the evidence visible to this reviewer. The user forwarded a builder-written proposed confirmation after Round 6, but did not adopt it as their own decision. Do not record forwarded text as approval.

### Verification performed
- Recomputed `git hash-object` and confirmed the spec is unchanged from Round 6; checked the intervening conversation and the prior review.
- No implementation, database or browser tests run. Earlier RLS, worker and concurrency controls remain design-level and require their specified tests.

### Required to unblock
- Obtain the owner's actual Q1–Q6 decisions with their source, reconcile the spec and governing amendment, and request another review.

### Deferred conditions
- None.

**Verdict: Blocked**

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
