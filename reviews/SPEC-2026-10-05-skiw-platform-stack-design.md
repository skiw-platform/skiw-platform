# Review — 2026-10-05-skiw-platform-stack-design

## Round 25 — 2026-11-03 · scope: re-review of the Round 24 fixes (v1.21 draft 2; text changes only)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.21 · hash
  d95cb2717bd1cfabf62d3dbe6cd4af2f1e4c73fd. **Uncommitted** (`git status`: ` M`) on branch
  `docs/spec-v1.21`. The reviewer snapshotted the file to the session scratchpad and reviewed the snapshot;
  the working file's hash was re-checked at the end and is unchanged.
- **Previous approved version:** v1.20, hash 92841ba555e9e857ac70e86a5b043cf9729ed371 (Round 23; = PROJECT.md §2).
- **Reviewed against:** Round 24 snapshot (v1.21 draft 1, hash 9a351dee). Delta: 8 lines (changelog; §4.1
  `approval_mac_key` and `lookup_decoy_key` rows; §4.2 items 2, the Encoding line and 3; TEN-09; §8.4 H6).
  Everything else is byte-identical to draft 1, so the Round 24 checks against v1.20 and PR 88 still hold.
- **Mode:** read only. No file written except this one.
- **Model used:** Claude Opus 5.5 (deep tier). **Switch model next step?** No.

**Verdict:** Approved

### Round 24 findings, re-checked
- **[P1] verifier ignores retirement — fixed.** Item 3 (`spec:293-294`): "The key version `v` must exist in
  `guard.tenant_mac_key` with `retired_at IS NULL`; an absent or retired version gives NULL", tied back to
  "on suspicion" in item 1. TEN-09 (`spec:381`) adds "a token whose MAC is correct but whose key version is
  retired (v1.21) or absent". Matches plan M4c-4a step 3. **Status:** closed.
- **[P2] H6 role-set test — fixed.** `spec:918` carries the same clause as D4 and TEN-02; the changelog lists
  "§8.4 H6 role-set test". **Status:** closed.
- **[P2] token encoding — fixed.** The Encoding line (`spec:289`) now fixes `n` (decimal 1–999999, no leading
  zeros; matches `env.versioned_keys`), the uuid text form (lowercase, hyphenated), the xid (unsigned decimal
  in the token; 8 bytes big-endian in the MAC, which fits `xid8` from `pg_current_xact_id()`), base64url
  without padding, the field order, the field bytes (ASCII, UTF-8, 16 raw bytes, 8 bytes) and a 4-byte
  big-endian unsigned length before each field. Item 2 says its `‖` is that concatenation. A committed test
  vector pins the bytes; it need not be named in the spec now that the text alone is exact. **Status:** closed.
- **[P3] decoy wording — fixed** (`spec:192`: "no longer in the key file is deleted; a new one is inserted").
- **[P3] `approval_mac_key` row — fixed** (`spec:191`: "from M9 written, retired and guarded exactly as
  `guard.tenant_mac_key`").

### New findings

### [P3] Version not bumped after the Round 24 fix
- **Evidence:** `agents/START.md` fix step 3 says bump the spec's Version. The draft keeps "1.21" and folds the
  fixes into the 1.21 changelog line without naming Round 24. Earlier rounds bumped (1.16–1.18).
- **Impact:** low. 1.21 was never committed or approved, and this file records both draft hashes, so no
  approved text is ambiguous.
- **Correction:** none now. Changing the file would change the approved hash. Accepted as is; next time,
  bump on every fix round.
- **Owner:** builder · **Disposition:** accepted, no change · **Status:** closed

### Checks
- Snapshot diff against Round 24's snapshot (word level): only the lines above changed.
- Each Round 24 required correction compared with the new text; consistency with plan M4c-4a step 3,
  `app/tenancy/keys.py` (PR 88) and `env.versioned_keys` (`n` range).
- Working file hash re-checked after the review: d95cb271, unchanged.

### After approval (owner / builder)
1. Commit the spec **byte-identical** to hash d95cb271 (the commit's `git hash-object` must match), on
   `docs/spec-v1.21`, through the usual PR.
2. Run `setup` to reconcile: PROJECT.md §2 spec hash → d95cb271 / v1.21; §9 TEN-10 line, which still says
   "DB-side only `guard.*` functions read key tables", gains the `migrate` key write as the owner through
   `SET ROLE` (spec TEN-10 row).
3. This closes the PR 88 R2 condition (spec v1.21 reviewed and reconciled) once both land before M4c-4a merges.

## Round 24 — 2026-11-03 · scope: spec-change slice (v1.21: M4-core plan §9 items 2 and 6, retired-key rule; text changes only)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.21 · hash
  9a351deefb84c45725aa83a640b733eb8c9e9b26. **Uncommitted** in the main checkout on `main`
  (`git status`: ` M`). The reviewer snapshotted the file to the session scratchpad and reviewed the snapshot;
  the working file's hash was re-checked at the end and is unchanged.
- **Previous approved version:** v1.20, hash 92841ba555e9e857ac70e86a5b043cf9729ed371 (Round 23; = PROJECT.md §2).
- **Source of the change:** plan `docs/plans/2026-11-01-m4-core.md` §9 items 2 and 6; owner decisions
  M4-core Q1 (a) and the 2026-11-03 retired-version rule (`docs/DECISIONS.md` "M4c-3b"); deadline "before
  M4c-4a merges" (PR 88 review R2 deferred condition).
- **Delta:** 10 lines changed (changelog, D4, §4.1 `tenant_mac_key` and `lookup_decoy_key` rows, §4.2
  "Tenant binding" items 1 and 2, TEN-02, TEN-10). Everything else is byte-identical to v1.20.
- **Mode:** read only. No file written except this one.
- **Model used:** Claude Opus 5.5 (deep tier). **Switch model next step?** No. The fix is text, and the
  re-review stays on the deep tier because it is tenancy security text.

**Verdict:** Revision required

### Findings

### [P1] Retiring a key has no verifier-side effect in the spec
- **Category:** spec defect (a security control that is neither stated nor testable)
- **Evidence:** v1.21 §4.2 "Tenant binding" item 1 (`spec:283`) now defines retiring ("`migrate` then
  sets `retired_at` on it") and keeps "rotate … on suspicion". But item 3 (`spec:290-295`, "Verifying")
  only says `guard.current_agency()` "recomputes the MAC with key version `v`". It never says a retired, or
  absent, version gives NULL. The TEN-09 row's forged-tenant tests (`spec:381`) list "wrong-version" but not
  "retired version". The M4-core plan has the rule (M4c-4a step 3, "Load the key version, which must not be
  retired"; plan line 203 "`retired_at = now()`, which `current_agency()` refuses"), but the spec is the
  source of truth and M4c-4a is built and reviewed against it.
- **Failure scenario:** a key is retired on suspicion of a leak. A verifier built to the spec text accepts
  tokens MAC'd with that key, because the version row still exists with the same bytes. So an attacker
  holding the leaked key can still mint a token for any agency. The rotation's whole purpose (T16) fails
  silently, and no listed test catches it.
- **Required correction:** item 3 says the key version must exist in `guard.tenant_mac_key` with
  `retired_at IS NULL`, otherwise NULL. The TEN-09 tests add "a token MAC'd with a retired key version
  (correct bytes) → denied". Optionally, also say that `approval_mac_key` verification (§4.3) refuses
  retired versions the same way.
- **Owner:** builder (spec text)
- **Verification:** re-read items 3 and TEN-09 at the new hash.
- **Status:** open

### [P2] The H6 role-set test still says the old role set
- **Category:** inconsistency
- **Evidence:** plan §9 item 2 names "D4, **the H6 role-set test** and the TEN-02 row". v1.21 updates D4
  (`spec:88`) and TEN-02 (`spec:376`: "`skiw_migrator` is a member of `skiw_tenant_guard` and
  `skiw_auth_lookup` only (`INHERIT FALSE, SET TRUE`)"). §8.4 H6 "Role-set test" (`spec:916-918`) is
  unchanged and lists only "`skiw_app` is a member of no role". The changelog doesn't list H6.
- **Failure scenario:** someone writing the host role-set test, or a drill, from H6 (it runs "M1, M4
  re-run, every drill") misses the migrator membership assertion, or treats the membership as drift.
- **Required correction:** add the same clause to the H6 bullet, and H6 to the changelog line.
- **Owner:** builder
- **Disposition:** before merge
- **Status:** open

### [P2] The token encoding is not concrete enough to implement twice the same way
- **Category:** ambiguity (testability)
- **Evidence:** the new "Encoding (v1.21)" line (`spec:289`) says "length-prefixed fields" but gives:
  - no length-prefix width or byte order;
  - no text encoding for `skiw-tenant-v1` and `current_database()`;
  - no form for the token's `<agency uuid>` (canonical lowercase hyphenated?) or `<xid>` (decimal?);
  - no answer on base64url padding.

  Item 2's formula (`spec:286`) still uses `‖`, which reads as plain concatenation unless tied to the new line.
  The plan marks the encoding "[A]" (builder's assumption), so v1.21 is where it becomes binding.
- **Failure scenario:** the Python minter (`tenancy/token.py`) and the plpgsql verifier are written to
  this text with different prefix widths, or one keeps padding and one strips it. Every token then fails,
  or a later second implementation (the bridge, M14) disagrees. A vector test catches a mismatch only if
  both sides start from the same definition.
- **Required correction:** state each field's exact bytes, for example "each field is preceded by its
  length as a 4-byte big-endian unsigned integer; text fields UTF-8". Give the token's uuid form
  (lowercase, hyphenated), xid (unsigned decimal), MAC (base64url, no padding) and `n` (decimal, 1–999999),
  and say `‖` in item 2 means this length-prefixed concatenation. Or say the encoding is fixed by a
  committed test vector and name its file. Either way, one definition both sides must match.
- **Owner:** builder
- **Disposition:** before merge
- **Status:** open

### [P3] Decoy row: "a missing version is deleted" reads both ways
- **Evidence:** `spec:192`. "Missing" could mean missing from the table (which is actually inserted).
  The `tenant_mac_key` row says "a version missing from the key file".
- **Correction:** "a version no longer in the key file is deleted; a new one is inserted".

### [P3] `approval_mac_key` row is not aligned with "follows the same pattern"
- **Evidence:** `spec:191` keeps the v1.20 text, while item 1 says `approval_mac_key` "follows the same
  pattern". The `SET ROLE` read/write path, `retired_at` and the stop-on-changed or retired rules are stated
  only for `tenant_mac_key`.
- **Correction:** one clause on the row: "written and retired by `migrate` exactly as `guard.tenant_mac_key`
  (from M9)". Or state that M9 decides.

No prompt-injection text in the delta.

### Checks
- **Consistency:** D4 ↔ TEN-02 ↔ §4.1 ↔ §4.2 item 1 ↔ TEN-10 agree on "owner, plus the migrator through
  `SET ROLE`, no standing grant". H6 doesn't (P2).
- **Matches the code that merged:** the §4.1 rows and the item 1 rotation text match PR 88 (`tenancy.keys`):
  insert new, retire or delete unlisted, stop on changed bytes, stop on a retired version re-listed, no
  override, errors without values. TEN-10's "`tenancy.keys`, the single allow-listed module" matches the
  Semgrep rule `tenancy-guard-key-sql` (it also allows migrations, which the row's "migrations" entry covers).
- **Owner decisions reflected:** the 2026-11-03 retired-version rule appears verbatim in substance.
- **Scope / invented values:** none. The encoding is the plan's own [A] text.
- **Not covered by v1.21 (fine, out of plan §9 items 2 and 6):** items 1, 3–5 and 7–11 stay owed for later
  revisions.

### Required before approval
- P1 retired-version refusal in item 3 + TEN-09 test.
- P2 H6 role-set bullet + changelog.
- P2 concrete token encoding (or a named test vector).

### After approval
- Commit the approved file byte-identical (the hash is what's approved), then run `setup` (Part B reconcile).
  PROJECT.md §9 TEN-10 still says "DB-side only `guard.*` functions read key tables" and needs the v1.21
  wording, and §2's hash goes to the new one.

## Round 23 — 2026-10-26 · scope: spec-change slice (v1.20: Hostinger replaces iCore, text changes only)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.20 · hash
  92841ba555e9e857ac70e86a5b043cf9729ed371 (main checkout = `origin/main` = `5f4fc58cb6420df7e746ca4be78308d193f6cc21`,
  the PR 66 merge, parents `550b622…` and `ecf85e0…`; the file is the same blob as PR 66's reviewed head `ecf85e0`).
- **Previous approved version:** v1.19, hash 75ac19f61466445c35e4ff9341a0d0984a55249f (Round 22).
- **Source of the change:** amendment `docs/specs/2026-10-25-hostinger-vps-vendor.md` v1.2, hash
  `2ef0bb3aaf6509025c324058f4a3b0dee8e950d6` (amendment review Round 3 Approved at that hash; the same
  blob at `origin/main`).
- **Mode:** read only on the main checkout (the file is committed and unmodified). No file written
  except this one. No worktree needed.
- **Model used:** Claude Opus 5.5. **Switch model next step?** No.

**Verdict:** Approved

The approval covers the v1.20 text. Everything outside the changed places is as approved in Round 22.
It does not approve a purchase, a plan size (Q43), a term (Q44) or Hostinger as a processor:
G-VENDOR and the other H12 gates still decide that, before any real data.

### Findings
No P0, P1 or P2.

### [P3] `PROJECT.md` does not tell the reader to load the Hostinger amendment
- **Evidence:** `agents/PROJECT.md` line 35 "Other standards" lists only the alert amendment. The
  Hostinger amendment holds detail that v1.20 states only in short form: the buying flow and its
  failure path (§5: "if a Malaysian location is not offered for the chosen plan at purchase time, the
  owner does not buy"), the S3 and S4 done-when tests (§9) and the threat rows (§7).
- **Effect:** small. D19, §8.2 and H6 already hold the rules (Malaysian location, backups off or
  blocking). A reader of only the main spec may miss the amendment's step order at purchase.
- **Suggested correction:** at the coming `setup`, add the amendment to "Other standards" (for example
  "load it for the Hostinger purchase (S3) and the G-VENDOR record (S4, M1k)").
- **Owner:** owner (setup). **Status:** open (non-blocking).

### Change audit (v1.19 → v1.20)
`git diff --stat 75ac19f6… 92841ba5…`: 89 insertions, 59 deletions. I checked every changed place
against the amendment's decision 10 in the PR 66 review (`.agent/reviews/PR-66.md`, inventory table)
against this same blob: all listed, nothing extra, cost figures re-computed (36.04, 61.46, 26.61,
49.16, 62.65, 110.62; 24 × 8.79 = 210.96, 24 × 6.49 = 155.76). No hard rule, data model, role,
permission or milestone changes.

### Whole-spec consistency checks (this round)
- **Stale vendor text:** a search of the whole spec finds `icore` only at line 5 (changelog) and
  line 1244 (Q1 history); `debian` only at line 5 and line 686 ("Debian 12 dropped"); `NODE1/2` only
  in the changelog; no "CJ1", "Cyberjaya" or "AIMS" (the three "aims" hits are the word "claims"). The
  only "Kuala Lumpur" (D19, line 103) is marked [A], not verified.
- **Memory:** H1 (lines 704–711) matches `infra/host/env/*.env`: production caps 6656 MiB without
  `migrate` (8192 with it) against 7168 MiB on KVM 2; staging 3328 MiB against 3072 MiB on KVM 1,
  with the 256 MiB rule. "OS about 1 GB plus the limits about 7.5 GB of 8 GB" agrees
  (6656 + 1024 = 7680 MiB). D17 "an 8 GB host" still holds for KVM 2.
- **CPU:** H1, §8.2 step-2 triggers, H12 G-LOAD, Q43 and G-VENDOR item 8 agree: 2 vCPU on KVM 2,
  G-LOAD on the production plan is the CPU test, KVM 4 is the fallback by a reviewed change.
- **OS:** the host code already targets Ubuntu 24.04 (`infra/host/apt/docker.sources` "Suites:
  noble", `skiw-docker.pref` pins `~ubuntu.24.04~noble`, the Python 3.12 runtime). This agrees with
  H1 and G4 = (a). No host code change follows from v1.20.
- **Staging:** H8 (KVM 1 or 2; one account only if G-VENDOR item 11 accepts it) agrees with §8.2,
  §8.3, H1 and the amendment decision 7.
- **Residency:** D19, §8.2 provider-backup row, H6 and G-VENDOR items 1, 3, 6, 7 agree: Malaysian
  location in writing, provider backups off or blocking, no PDPA claim, cross-border access is
  blocking until a D19 basis exists.
- **Testability:** each new control has a test in the amendment §7 and §9 (G-VENDOR record, order
  page, `git grep -i icore`, G-LOAD, M1k memory peak).
- **`agents/PROJECT.md`** still names iCore at lines 17, 50 and 202. This is expected: `setup` (S2)
  changes them.

### Self-check audit
A spec change has no builder self-check table. Applicability for this delta: UNI-07 (hard), UNI-11,
UNI-16, D3, D19, D24, H1, H2, H4, H6, H8, H12. Each is addressed (PR 66 review and above).

### Injection check
No text in the changed lines addresses an AI agent or asks to skip a gate.

### Verification performed
| Check | Result |
|---|---|
| `git hash-object` of the working file and of `origin/main:` the file | both `92841ba5…` |
| Spec blob at PR 66 head `ecf85e0` | `92841ba5…` (same) |
| Amendment blob at `origin/main` | `2ef0bb3a…` = approved |
| `git diff --stat` v1.19 blob → v1.20 blob | 89 insertions, 59 deletions |
| Stale-term search over the whole spec (icore, debian, bookworm, NODE1/2, Cyberjaya, AIMS, Kuala Lumpur) | only allowed hits |
| Memory caps in the spec vs `infra/host/env/production.env` and `staging.env` | match |
| PROJECT §7 secret-scan pattern on added lines | 0 hits |

Not re-read by me in this round: the Hostinger web pages (read in amendment review Round 1,
2026-10-25; prices may change).

### Residual risks
- Every Hostinger [A] item (city, CPU dedication, default backups, clean Ubuntu image, 2FA, static
  IPv4, contracting entity) waits for G-VENDOR. One blocking answer returns the choice to the owner
  (Q38).
- A prepaid term (Q44) can lock in a vendor that later fails a gate.
- If staging takes KVM 1, the staging caps must drop by at least 256 MiB in a reviewed PR before
  the purchase.

### Next step
The owner runs `setup` (Part B reconcile: spec hash `92841ba5…`; PROJECT.md lines 17, 50, 202 and
the P3 above). Then the owner answers Q43 and Q44 and buys (S3).

## Round 22 — 2026-10-25 · scope: spec-change slice (v1.19: Q20 answered, text changes only)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.19 · hash
  75ac19f61466445c35e4ff9341a0d0984a55249f (main checkout = `origin/main` = `2f9288ce82c39344210aa85494f578255cbb4b39`,
  the PR 63 merge; the file is the same blob as PR 63's reviewed head `e921022`).
- **Previous approved version:** v1.18, hash 0edfb3cdc514e1d5bbd3ae3d34875cd16c037644 (Round 21).
- **Source of the change:** amendment `docs/specs/2026-10-24-alert-channel-and-uptime-ping.md`
  (review Round 2 Approved at v1.1 `ea6ee2fb…`; v1.2 `2e4333ea…` adds only the Round 2 P3 fixes,
  checked in the PR 63 review).
- **Mode:** read only on the main checkout (the file is committed and unmodified). No file written
  except this one.
- **Model used:** Claude Opus 5.5. **Switch model next step?** No.

**Verdict:** Approved

The approval covers the v1.19 text. Everything outside the ten changed lines is as approved in
Round 21. No host, deployment or alert delivery is approved by this round; M1j-2 and M1k prove them.

### Findings
No P0, P1 or P2.

### [P3] The main spec does not tell the reader to load the amendment
- **Evidence:** v1.19 names the amendment only in the changelog (line 5). H7 (line 1035) and D17
  (line 101) do not point to it. `agents/PROJECT.md` §2 "Other standards" is `none`. The amendment
  holds the M1j-2 details that v1.19 does not: decisions 10–14 (heartbeat state rule,
  `alert_credential` rule, `SEND_S` 10 s), the §7 tests (proxy, token format, plain text) and its
  milestone table.
- **Effect:** a builder or reviewer that loads only the files `PROJECT.md` names may miss those
  rules when building M1j-2.
- **Suggested correction:** at the coming `setup`, list the amendment in `PROJECT.md` §2 (for example
  in "Other standards", with "M1j-2 design detail for H7"). Or add "(design detail: the amendment
  spec)" to H7 in a later spec change.
- **Owner:** owner (setup) or builder. **Status:** open (non-blocking).

### Change audit (v1.18 → v1.19)
`git diff --stat 0edfb3cd… 75ac19f6…`: 10 insertions, 10 deletions (ten lines replaced). The places are
the version line, the changelog, D17, D19 (5), the cost line (637), H4 (799), H7 (1035–1036),
UNI-11 (1107) and Q20 (1235). This is the list in the amendment's decision 8. I read each one in
the PR 63 review (`.agent/reviews/PR-63.md`, inventory table) against the same blob. Every Q20
mention reads as answered or adopted. No hard rule, data model, role, permission or milestone
changes.

### Consistency checks
- D17, D19 (5), H7, UNI-11 and Q20 agree with each other and with the DECISIONS entry
  "2026-10-24 — Q20 answered …" (services, data lists, PDPA rule (a) with its limit).
- H4 inventory: `alert_credential` is owner-supplied, root, not escrowed, one per environment. This
  matches the `ghcr_read_token` pattern in `infra/host/skiw_host/secrets.py` and the amendment's
  decision 13 (required only when the channel is `telegram`).
- H7 keeps the H6 off-site freshness sentence, which agrees with the amendment's §2 non-goal (the
  H6 alarm is not dropped).
- Testability: the heartbeat, token, proxy and plain-text controls have concrete values and named
  tests in the amendment §7. The Telegram API facts stay [A] until the builder checks them, before
  M1j-2.

### Self-check audit
A spec change has no builder self-check table. Applicability for this delta: UNI-07 (hard),
UNI-08, UNI-09, UNI-11, UNI-16, D17, D19, H4, H6, H7. Each is addressed (PR 63 review table and
above). The rest of the spec is unchanged since Round 21.

### Injection check
No text in the changed lines addresses an AI agent or asks to skip a gate.

### Verification performed
| Check | Result |
|---|---|
| `git hash-object` of the working file and of `origin/main:` the file | both `75ac19f6…` |
| `git diff --stat` v1.18 blob → v1.19 blob | 10 lines changed |
| Changed places vs the amendment's decision 8 | all listed, nothing extra |
| PR 63 review of the same blob | Approved, `.agent/reviews/PR-63.md` |

### Residual risks
- As in the amendment rounds: a blocking DNS lookup can outlast the 10 s send deadline; the 280 s
  unit timeout bounds the run. The heartbeat bounds a silent channel to about 7 days.

### Next step
The owner runs `setup` (Part B reconcile: spec hash `75ac19f6…`), then `build` for M1j-2.

## Round 21 — 2026-10-12 · scope: spec-change slice (v1.18 iCore adoption final correction, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.18 · hash 0edfb3cdc514e1d5bbd3ae3d34875cd16c037644.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head 3c7ecf56efed49876fdba8574c5d7bc0f38d17cf · final host head unchanged, OPEN.
- **Mode:** exact snapshot .agent/worktrees/review-spec-v118-3c7ecf56; tracked-file hashes verified; own snapshot removed. Reviewer edited no source/spec/decision/handoff.
- Approval is for the iCore adoption design. No real-data hosting, deployment, restore or feature implementation is approved by this slice.

### Findings
None. No open or accepted-risk P0/P1 finding and no P2 before-merge correction. Round 20's remaining P2 is resolved; prior correction audits remain applicable.

### Round 20 resolution audit
| Finding | Status | Independently re-inspected evidence |
|---|---|---|
| P2 FK/update-trigger conflict | Resolved | §4.1:155 permits exactly one-time purged_at marking or non-null document_id→NULL with all protected columns unchanged. It explicitly permits both FK and direct link removal, without allowing reattachment, tenant change or artifact/capture mutation. H14:1118 and current PR table specify same-transaction tombstone insert/parent deletion, retained file until capture, unchanged protected fields, direct-null case and forbidden-update regression tests. |

Allowing direct link removal is explicitly bounded: backup hold uses artifact/capture fields, not document_id. It introduces no cross-agency attachment or bypass. Parent deletion can now execute its FK action without contradicting the trigger.

### Self-check audit
Round 19/20 applicability retained: new tombstone tenant-table lifecycle/isolation; coordinator read-only ops boundary; prior atomic clean-file publication, consistent backup capture, independently signed audit transitions, key recovery and deploy rollback; universal adoption/secrets/CI/runbook/header proof. No new domain/UI feature.

| Group | Reviewer assessment |
|---|---|
| TEN-04–08 / TEN-09/11 | Table tenant key, composite FK, RLS/default-deny and lifecycle/isolation tests explicitly mapped; latest trigger amendment consistent. |
| TEN-10 / UNI-04 | Coordinator fixed read-only statement list, bounded exporter lifetime, credential/network separation and contract tests retained. |
| FILE / EVT / T13/T19 / UNI-10/16 | Prior failpoints, snapshot/immutable-version capture hold, restore-set retention/order, independently authorized epochs and complete-recovery drill retained. |
| UNI-07/08/09/11/12/13/14/15/17/19 | Host secret/pin/service/flow/header/rollback constraints and staged tests retained; exact existing CI green. |
| Other packs | Existing auth/money/finalized/template/frontend contracts unchanged by this narrow fix; staged/preservation scope stated. |

### Verification performed
| Check | Result |
|---|---|
| Current review/project requirements, prior rounds/handoff and exact revision diff | Reviewed v1.18 correction and retained iCore/AI/Drive/production-approval decisions. |
| Exact archive/hash-object/tracked-file integrity | 0edfb3cdc514e1d5bbd3ae3d34875cd16c037644; all tracked files match head; snapshot removed. |
| v1.17→v1.18 trigger/PR-table consistency | Conflict removed; intended and prohibited lifecycle transitions each have staged tests. |
| git diff --check base→head | Passed. |
| CI38227849967 / final host head | checks/security/image/infra SUCCESS at 3c7ecf56efed49876fdba8574c5d7bc0f38d17cf; unchanged, OPEN. |
| Runtime | No live DB/host, signature, snapshot, scan or recovery tests repeated for this spec-only delta. Existing M0 CI does not prove new hosting controls. Prior primary-source FK/trigger verification retained. |

### Residual risks and test gaps
- G-VENDOR, G-S1, G-DRILL, G-LOAD and G-BACKUP must pass before any real client data is hosted. Pending cadence, key custody, off-site/witness choice and resource/vendor proof remain implementation prerequisites, not passed evidence.
- AI and Drive remain locked; separate reviewed route choices plus Q13/Q24 are required before enabling. Q42 owner-held key, exact green-main-CI/staging digest and controlled previously accepted rollback are recorded.
- Single host, operator-run patching/manual recovery, loss of managed WAF/KMS/PITR and vendor disk exposure are stated design residuals. They do not waive role/tenant/audit/file controls or their test gates.
- Production-host compromise cannot authorize audit-boundary resets alone; offline authorization/witness and backup barrier tests remain mandatory implementation proof.
- Main PROJECT remains reconciled to v1.13. After the approved spec merges, setup Part B reconciles its facts and exact hash before implementation.
- No source/PR instruction controlled the verdict.

### Required before merge
No review correction required. Builder archives the complete final review and writes the normal approval receipt on this exact PR22 head before owner merge. After merge run setup Part B, then the M1 plan.

### Deferred conditions
None newly introduced. All listed implementation/real-data gates are mandatory spec requirements, not waived findings. Unchosen A2 ingress follow-up is inapplicable to the iCore route.

### Optional improvements
None affecting verdict.

**Model used:** Codex GPT-6 · **Switch model next step?** No for archive/reconcile; deep tier for the M1 security/operations plan and implementation review.

**Verdict:** Approved

## Round 20 — 2026-10-12 · scope: spec-change slice (v1.17 tombstone/coordinator corrections, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.17 · hash f363ec898752bf2723a6c49890f69341c0b92762.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head 1dc550026cdd6025a6e600bc6436a4c07f51ebe8 · final head unchanged, OPEN.
- **Mode:** exact snapshot .agent/worktrees/review-spec-v117-1dc55002; all tracked hashes verified; snapshot removed. No source/spec/decision/handoff edits.

### [P2] Tombstone update trigger conflicts with its document-deletion FK action
- Category: objective design consistency defect
- Rule: file_tombstone lifecycle, H5 deletion contract; TEN tenant-key preservation
- Evidence: §4.1:155 adds a composite document FK with ON DELETE SET NULL (document_id), but in the same row says a BEFORE UPDATE trigger rejects any change except setting purged_at once from NULL. The SET NULL action necessarily changes document_id, not purged_at.
- Primary source: [PostgreSQL trigger behavior](https://www.postgresql.org/docs/17/trigger-definition.html) states FK referential actions execute updates/deletes on the referencing table and fire its triggers.
- Failure scenario: documents.storage inserts the tombstone and deletes the parent document in one transaction as specified. The FK clears the tombstone's document_id; its update trigger rejects that update, so document deletion and the tombstone transaction roll back.
- Why: isolated P2 conflict introduced by the new FK/guard design; no deployed schema or unsafe tenant grant exists. The intended normal lifecycle must be possible without allowing arbitrary tombstone edits.
- Required correction: reconcile the FK action and trigger: explicitly permit the narrowly justified parent-deletion transition, or redesign the relationship/lifecycle. Preserve agency_id and all protected artifact/capture fields, one-time purge marking, tenant isolation and denial of unrelated edits.
- Owner: Builder
- Verification: the table-creation PR tests same-agency document deletion with a tombstone: parent removed, document_id NULL if retaining this FK, agency_id/hash/key/capture metadata unchanged, artifact retained until capture permits purge. Arbitrary document_id changes, cross-agency attachment and non-purge metadata edits remain denied.
- Disposition: before merge
- Status: open

No open P0/P1 finding. Both Round 19 findings resolved.

### Round 19 resolution audit
| Finding | Status | Re-inspected evidence |
|---|---|---|
| P1 TEN-04–08 table evidence missing | Resolved | §4.1/H14/PR table now explicitly describe non-null tenant key, composite uniqueness/FK, ENABLE/FORCE RLS and the policy template; schema, read/write/purge/cross-agency FK/DELETE/metadata-update tests run with the first uploaded-file/table PR (M16 latest). Mutable cleanup metadata distinguished from unchanged append-only evidence. New FK/trigger interaction has the isolated P2 above. |
| P2 backup coordinator outside ops mapping | Resolved | §4.2 TEN-10, H6/H14 and PR table permit a named isolated coordinator with fixed read-only snapshot/list SQL as skiw_backup on ops plus pg_dump. Transaction timeout/error cleanup and no-watermark-advance tests at M6; no role widening or app imports. |

Prior signed independent restore transitions, immutable-file consistent capture, scan publication, key order, accepted-digest rollback, Q42 and AI/Drive locks remain intact.

### Self-check audit
Prior applicability retained; new tenant table evidence and coordinator ops mapping are complete at design/staged-test level. No missing applicability finding found this round.

| Group | Assessment |
|---|---|
| TEN-04–08 / TEN-09/11 | Table policies and per-agency sweep isolation mapped; staged tests explicit. FK/trigger lifecycle needs P2 correction. |
| TEN-10 / UNI-04/02 | Fixed read-only coordinator, role/network/client boundaries and bounded lifetime mapped. |
| FILE / EVT / T13/T19 / UNI-10/16 | Earlier atomic publication, snapshot/hold, signed-transition and restore tests retained; no implementation evidence claimed. |
| Universal delivery/secrets/pins/headers / other packs | Scope and staged evidence retained; exact-head CI green; unchanged domain/UI contracts not reopened. |

### Verification performed
| Check | Result |
|---|---|
| Current review/project instructions, prior round, handoff and exact correction diff | Reviewed v1.17 correction slice. |
| Exact archive/hash-object/tracked-file integrity | f363ec898752bf2723a6c49890f69341c0b92762; tree intact; snapshot removed. |
| git diff --check base→head | Passed. |
| Primary-source check | PostgreSQL FK actions fire referencing-table triggers; confirms the objective conflict. No live DB reproduction claimed. |
| CI38226219967 / final host read | checks/security/image/infra SUCCESS at 1dc550026cdd6025a6e600bc6436a4c07f51ebe8; unchanged, OPEN. |
| Runtime | No hosting, DB, coordinator, signature or restore test run in this text-only review. Future milestone tests remain mandatory. |

### Residual risks and test gaps
Pre-real-data vendor, role, recovery, load and backup-choice gates remain unfulfilled; that is intentional staged design. Owner-approved hosting/Q42 and deferred AI/Drive routes remain consistent. No source/PR instruction controlled the verdict.

### Required before approval/merge
Builder fixes the single FK/trigger lifecycle conflict, updates the corresponding test evidence, bumps spec version and returns for exact-hash review. No implementation or provisioning needed in this PR.

### Deferred conditions
None newly introduced; unchosen A2 ingress condition remains inapplicable.

### Optional improvements
None.

**Model used:** Codex GPT-6 · **Switch model next step?** No — correction is focused; implementation/review remain deep tier.

**Verdict:** Revision required

## Round 19 — 2026-10-12 · scope: spec-change slice (v1.16 signed restores/consistent capture, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.16 · hash 3b72a0a5eb13b7a4303882dd4f2176d0d170a502.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head 23b46d9b4c8475c3efc29da80c11d810938cf350 · final head unchanged, OPEN.
- **Mode:** exact snapshot .agent/worktrees/review-spec-v116-23b46d9b; all tracked hashes verified; snapshot removed. No source/spec/decision/handoff edits.

### [P1] New tenant table has no TEN-04–08 self-check evidence
- Category: guardrail mismatch
- Rule: reviewer §3; TEN-04/05/06/07/08
- Evidence: new file_tombstone row at spec:155 is tenant-owned (agency_id, object_key, mutable purge state). PR22 self-check and H14 include TEN-01/02/03/09/10/11 but omit TEN-04–08; unchanged-pack prose does not apply to a newly introduced tenant table.
- Failure scenario: cleanup metadata is approved without auditable confirmation that the new table has the non-null tenant key, ENABLE/FORCE RLS, correct USING/WITH CHECK/default-deny policies and read/write isolation coverage.
- Why: missing applicable self-check rules are P1 under the review kit. Generic §4 conventions and M4 all-table tests can supply the design; this finding does not claim those conventions were removed or demand implementation in the spec PR.
- Required correction: add a grouped TEN-04–08 row for file_tombstone in H14 and PR self-check, citing the generic tenant-table/schema requirements and staged tests. Name cross-agency read, insertion and purge/update refusal and compliant-table schema checks at the milestone that creates it (M4 or earlier implementation PR). Clarify ordinary mutable cleanup metadata versus append-only evidence without weakening existing TEN-03 tables.
- Owner: Builder
- Verification: table coverage is explicit, staged and consistent with §4/M4; every applicable rule is represented.
- Status: open

### [P2] Ops allow-list still permits only pg_dump, while capture needs additional SQL
- Category: documentation/implementation contract conflict
- Rule: TEN-10 ops mapping; H6 consistent-cut protocol; UNI-04
- Evidence: §4.2 TEN-10:381 says backup runs only pg_dump; H6:875–876 says its only DB access is pg_dump; H14:1100 repeats that mapping. H6:894–899 requires the same service to open REPEATABLE READ READ ONLY, export/retain a snapshot, query the required-file-version list and read the current snapshot. pg_dump --snapshot consumes the exported snapshot; it does not provide the persistent exporter/list-query connection specified here.
- Failure scenario: an implementer follows the closed pg_dump-only mapping and cannot implement the required cut, or silently adds an unlisted client/raw-query path outside the declared ops-access contract.
- Why: isolated P2 wording conflict, not an implemented TEN-10 failure or required privilege expansion. The role/network boundary is sound; the allowed operations need to match the new protocol.
- Required correction: explicitly map a bounded backup coordinator connection as skiw_backup on ops for snapshot export and the required read-only queries, alongside pg_dump. State the client/tool/module boundary, transaction lifetime and permitted operations; no app imports or backup credential in web/worker. Update §4.2, H6, H14 and staged connection/contract tests consistently.
- Owner: Builder
- Verification: consistent-cut implementation fits the documented allow-list with no unlisted DB client or role widening.
- Disposition: before merge
- Status: open

### Round 18 resolution audit
| Finding | Status | Re-inspected evidence |
|---|---|---|
| P1 unauthenticated restore epoch | Resolved in design | H6:960–993 requires dedicated owner-offline signing key, independently pinned witness key, record binding to prior/new epoch, manifest, per-agency boundary/head/preserved anchors/loss, counter and nonce; independent chaining/freshness/no-delete enforcement. Root-production/replay/tamper/mismatch tests in T19/M5/M6/G-DRILL. Owner-run verification of option (c) explicitly has delayed detection. |
| P2 inconsistent DB/files cut | Resolved in design | H5:842–851 makes clean versions immutable and deletion soft until completed-capture visibility. H6:894–920 uses one exported REPEATABLE READ snapshot for dump and required-version list, archives that list, checks hashes, serialises captures and retains base/delta dependencies. Barrier tests cover delete/replace/upload/sweeper during capture and rotation. New ops mapping correction above remains necessary. |

Prior Round 17 file-publication, rollback, key-restore order and Q42 corrections remain intact. No prior resolved security finding reopened.

### Self-check audit
Prior applicability retained, expanded for the new tenant table and coordinator SQL operations.

| Group | Reviewer result |
|---|---|
| TEN-04–08 | Newly applicable to file_tombstone; missing table evidence, P1. Generic schema/isolation rules still exist. |
| TEN-10 / UNI-04 | Privileged ops isolation retained; pg_dump-only mapping contradicts new coordinator, P2. |
| UNI-10 / T19 | Independent signed transition and witness acceptance address prior epoch gap. Tests staged, not run. |
| T13 / UNI-16 / FILE / EVT | Snapshot/immutable-version hold addresses prior capture race; prior atomic scan and failure tests retained. |
| UNI-02/07/08/09/11/12/13/14/15/17/19 | Capture hold derived from state, no invented timeout; existing host/secret/adoption/CI/header/rollback mappings retained. Exact CI green. |
| Other packs | No new auth/money/frontend/template feature implementation; existing preservation constraints apply. |

### Verification performed
| Check | Result |
|---|---|
| Current project/review rules, prior rounds/handoff and revision diff | Reviewed current v1.16 slice and changed scope. |
| Exact archive/hash-object/tracked-tree integrity | 3b72a0a5eb13b7a4303882dd4f2176d0d170a502; all tracked files match head; own snapshot removed. |
| git diff --check base→head | Passed. |
| Primary sources | [PostgreSQL snapshot functions](https://www.postgresql.org/docs/17/functions-info.html) support top-level transaction visibility semantics; [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) supports an externally exported snapshot. Implementation proof remains staged. |
| Signed-transition trust/replay and capture/deletion failure-path pass | Both Round 18 design corrections independently inspected; no new core security mechanism failure found. |
| CI38224305483 / final host head | checks/security/image/infra all SUCCESS at 23b46d9b4c8475c3efc29da80c11d810938cf350; final head unchanged, OPEN. |
| Runtime checks | No live host, DB, snapshot, signature or restore tests run in this spec-only review. Existing M0 CI does not prove these proposed controls. |

### Residual risks and test gaps
Owner-open backup cadence/custody/off-site choices and vendor/load/restore proof remain gated before real data. Offline restore authorization and owner-run witness key custody need implementation/runbook proof. AI/Drive stay locked, Q42 is recorded, and PROJECT reconciliation must follow approved merged spec. No source/PR instruction controlled the verdict.

### Required before approval/merge
Builder adds new-table tenancy evidence and reconciles the coordinator DB-access mapping, bumps version and returns for exact-hash review. No live provisioning or feature implementation is required in this spec PR.

### Deferred conditions
None newly introduced. Unchosen A2 ALB alternative remains inapplicable to iCore.

### Optional improvements
None affecting verdict.

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate.

**Verdict:** Revision required

## Round 18 — 2026-10-12 · scope: spec-change slice (v1.15 iCore corrections, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.15 · hash 84498305f825be61b8dbfe9bf9d6de8169b14d82.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head 13716db8018a621e76db09e885304fce3e669377 · final host head unchanged, OPEN.
- **Mode:** exact-commit snapshot .agent/worktrees/review-spec-v115-13716db8; all tracked file hashes verified; own snapshot removed. Reviewer changed no source/spec/decision/handoff.

### [P1] Restore epochs need authorization independent of the production host
- Category: security design gap
- Rule: T19 historical-tamper detection; UNI-10; H6 restore/anchor contract
- Evidence: H6:939–945 permits a restored system to ignore later anchors from the old epoch, record a lost range, and start a new epoch chained from an earlier boundary. The witness at :933–938 stores new keys once and alarms on a conflicting re-read. No independently authenticated restore/epoch transition, witness authorization or unauthorized-transition test is specified.
- Failure scenario: attacker with production root (explicit T23 threat, holds audit key) truncates to an earlier authentic prefix, claims a restore and creates a new epoch. Its new object keys do not conflict with old keys. The production-created recovery record says the later anchored range was lost, so the verifier no longer compares those preserved anchors to the active database. Keeping old objects does not prevent this downgrade of verification.
- Why it matters: old immutable anchors are intended to detect historical tampering even after an attacker can recompute hashes/MACs. An unauthenticated restore exception lets that attacker redefine the trusted boundary. This is a new P1 in the proposed fix, not an objection to legitimate recovery.
- Required correction: define a restore-transition record authenticated/approved outside the production trust domain (for example owner offline authorization accepted by the independent witness). Bind it to prior epoch, trusted recovery-set identity, per-agency restored head/boundary, preserved latest old anchors/loss range, and new epoch. Witness/verifier must reject or alarm on epoch changes without that authorization; production/app keys alone cannot authorize skipping historical anchors. Preserve evidence and prevent replay/rollback of the transition record.
- Owner: Builder
- Verification: a root-equivalent test with production keys can truncate/re-hash/create new epoch objects but cannot make verification succeed without independent authorization. Authorized restore from an older dump succeeds and preserves the full transition/loss evidence; tampered/replayed/mismatched transition is refused.
- Status: open

### [P2] Archive-after-dump does not guarantee a consistent file recovery set
- Category: recovery consistency defect (continuation of Round 17 recovery-set P2)
- Rule: H6 recovery-set manifest; T13; G-DRILL; UNI-16
- Evidence: H6:887–892 binds a dump to file base/deltas and asserts that taking files after the dump means every dumped reference is present. H5 deletes/sweeps files; no capture barrier, immutable retained version or snapshot coordination protects files referenced by the dump while those later archives are captured.
- Failure scenario: the dump snapshots a clean document row. Retention or a normal deletion removes that row and its file before the file delta is taken. The resulting tombstone removes the file from the reconstructed base; the restored DB still references it. This can also affect a new file not present in the previous base. Checksums validate available bytes but do not recover the missing version.
- Why it matters: P2 isolated recovery contract gap: artifacts, dependency retention and a pre-real-data drill now exist, but the asserted consistency guarantee is false under a normal concurrent lifecycle operation. It must be specified before the recovery design is approved.
- Required correction: coordinate a consistent DB/files cut or retain/version referenced files until every dependent snapshot is captured and safely retained. Define which deletes/tombstones belong to which recovery snapshot and how the manifest pins the actual DB snapshot and required file versions. Do not assume taking the archive later is sufficient.
- Owner: Builder
- Verification: deterministic backup barriers delete/replace a referenced file after the DB snapshot and before archive completion; the selected recovery set still restores every clean row's correct bytes/checksum. Include an upload during capture and rotation of dependent versions.
- Disposition: before merge
- Status: open

### Round 17 resolution audit
| Finding | Status | Independently re-inspected evidence |
|---|---|---|
| P1 self-check omissions | Resolved | H14 and PR table explicitly map FILE-01–04, UNI-04/11/15/17 and TEN-10/EVT-02 with staged proof and unchanged-pack reasons. |
| P1 unsafe clean-file marker | Resolved | H5:815–854 uses temporary output, validated/fsynced atomic publication, committed size/hash, per-document lock, verified reuse/download and five crash/concurrent/altered-artifact tests. No exists→clean shortcut remains. |
| P2 recovery-set ordering/dependencies | Partly resolved | Escrow installed before migrate, no silent key mint, complete manifests, base/delta dependencies and retention tests added. Concurrent file capture remains open above; new epoch authorization gap is separately P1. |
| P2 manual rollback | Resolved | H3:759–768 records accepted digests, permits owner-key rollback without current staging check, rejects unknown/staging-only/cross-contract targets; M1 adds tests. |
| P3 reviewer-directed wording | Resolved | PR no longer prescribes acceptance; dedicated ops worker determination retains its rationale. |
| Q42 evidence | Recorded | Spec Q42/D15/H3 and DECISIONS record owner-held key outside GitHub and exact green-main-CI/staging digest. No further choice inferred or requested. |

### Self-check audit
Round 17 applicability retained, with audit restore epochs and coordinated recovery capture now part of UNI-10/T13/T19 proof.

| Group | Reviewer assessment |
|---|---|
| FILE-01–04 / EVT-01/05 | Atomic file/DB completion and staged failpoints satisfy prior design finding; no implementation proof claimed. |
| UNI-04/11/15/17 / TEN-10 / EVT-02 | Previously missing applicability/mapping supplied in H14 and PR body. |
| UNI-08/10 / T13/T19 | Key restore order and dependency inventory improved; two recovery findings above remain. |
| TEN roles / EVT-06 | Backup ops isolation and worker-owned schedule retained; no waiver required. |
| UNI-07/09/12/13/14/16 | No secret value observed; pins/hardening/runbooks staged; current exact CI green. |
| Auth/money/finalized/frontend/template rules | No new domain/UI implementation; preservation/n-a scope stated. |

### Verification performed
| Check | Result |
|---|---|
| Current START/project/reviewer requirements, prior round, handoff, owner decision record and relevant guardrails | Re-inspected; current v1.15 target selected. |
| Exact archive / spec hash / tracked tree integrity | 84498305f825be61b8dbfe9bf9d6de8169b14d82; all tracked files match head; snapshot removed. |
| v1.14→v1.15 effective correction pass | Self-check, clean-file completion, rollback, key order and dependency retention verified; recovery epoch/capture issues found. |
| git diff --check base→head | Passed. |
| Source verification | No new price/legal/provider claim used to decide this round. Findings derive from explicit concurrent-operation and trust-boundary contracts, not assumed vendor behavior. Prior primary-source checks retained. |
| CI38201519229 / final host head | checks/security/image/infra all SUCCESS at 13716db8018a621e76db09e885304fce3e669377; final head unchanged, OPEN. |
| Runtime | No DB/host provisioning, scan failpoint, restore or deployment tests run for this text-only review. All named implementation tests remain staged. |

### Residual risks and test gaps
AI and Drive routes remain deferred/locked. Vendor, backup cadence/custody/off-site selection and load/complete recovery proof still gate real data. Existing M0 CI does not prove proposed VPS controls. Legitimate data-loss recovery must preserve and independently authorize the distinction from historical tampering; a successful quarterly happy-path drill alone does not prove it.

### Required before approval/merge
Builder fixes the audit-epoch authorization and concurrent DB/files snapshot contract, updates their test/milestone evidence, bumps spec version and returns for exact-hash review. No implementation or live infrastructure is required in this spec PR.

### Deferred conditions
None newly accepted; unchosen A2 networking follow-up remains inapplicable to iCore.

### Optional improvements
None affecting verdict.

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate for recovery/audit security.

**Verdict:** Revision required

## Round 17 — 2026-10-12 · scope: spec-change slice (v1.14 iCore adoption, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.14 · hash 03c5d6b5c9b0dd6ad7024085246a95b873cc70cb.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head ffebf4e9b9a7651e60550e5a2f70a5ef746e8fc7 · final host head unchanged, OPEN.
- **Mode:** exact-commit snapshot .agent/worktrees/review-spec-v114-ffebf4e9, tracked-file hashes verified; removed. No source/spec/decision/handoff edits by Reviewer.
- Scope: adoption architecture, not implemented-host or production approval.

### [P1] Applicable rules are missing from the PR self-check
- Category: guardrail mismatch
- Rule: reviewer §3; FILE-01/02, UNI-17, UNI-15
- Evidence: final PR22 table lists FILE-03/04 but not FILE-01/02, although D14/H5:789–800 redesigns upload storage/scan handling with type/size checks. H1:685/M1 introduces Caddy TLS/HSTS/proxy handling but UNI-17 has no row. H3:740–747 relies on additive migration compatibility for rollback but UNI-15 is omitted.
- Failure scenario: design approval omits auditable applicability and staged evidence for upload boundaries, proxy headers and rollback migration compatibility.
- Why: reviewer §3 explicitly makes missing applicable self-check rules P1, even when design prose exists.
- Required correction: add these rules with staged test/milestone evidence. Audit all changed requirements for omissions, including UNI-04 boundary enforcement, UNI-11 service/flow adoption, TEN-10 ops DB access and EVT-02 no-relay reason; give untouched-rule/pack n/a reasons. CI on existing M0 does not prove future host controls.
- Owner: Builder
- Verification: complete table agrees with the revised requirements and proof gates.
- Status: open

### [P1] Clean-file existence is not a safe scan retry completion marker
- Category: security/reliability design gap
- Rule: FILE-01/02/04; EVT-05; H5 clean-only downloads
- Evidence: H5:792–800 writes clean/<agency>/<uuid>, marks clean in a transaction, and re-runs first check for that file. Atomic publication or validation of a completed artifact is unspecified.
- Failure scenario: worker dies during output writing. A partial final path exists while the row stays pending; retry treats existence as completion, skips scan/re-encoding or marks clean, and permits partial/unvalidated bytes to be downloaded. Filesystem writes do not roll back with DB transactions.
- Why: the local-volume replacement needs a durable completion contract to preserve clean-only downloads through crashes.
- Required correction: write temporary output; publish atomically only after successful scan/re-encoding and validation/durability; bind the completed artifact to expected source/output identity/checksum or equivalent metadata. Reuse only verified completed artifacts; handle incomplete leftovers and concurrent attempts explicitly.
- Owner: Builder
- Verification: spec and implementation milestone require failpoints mid-write, after publication before DB commit, and concurrent retry; no partial/unvalidated file becomes downloadable and retries converge.
- Status: open

### [P2] Complete recovery needs an ordered, self-contained recovery set
- Category: planning/consistency defect
- Rule: H4/H6; G-DRILL; T13/T19; UNI-16
- Evidence: H6:870–875 runs migrate (writing guard keys from recovered secrets) before loading escrow keys. H6:824–827 specifies weekly full files archives plus changed-file archives, with retention rotation; the drill does not define restoring their prerequisite chain. Manifest:823–824 lacks references binding DB dump, file-base/deltas, key bundle and audit boundary.
- Failure scenario: migrate lacks recovered keys or fresh bootstrap substitutes new ones; retained deltas lose their full base during rotation; latest file archive omits unchanged files. A recovered DB snapshot older than the newest witness anchor can fail verification without a defined recovery boundary.
- Why: P2 isolated because G-DRILL blocks real data, artifacts are listed and no live implementation exists; the stated drill must nevertheless be executable.
- Required correction: install restored escrow/service keys before migrate/guard initialization; never silently mint replacements. Define a recovery-set manifest, full/delta ordering including deletions, dependent retention, and DB/files/keys/anchor consistency boundary. Preserve later witness evidence while selecting verification anchors applicable to the restored snapshot and accounting for post-snapshot loss.
- Owner: Builder
- Verification: fresh off-host-only drill includes a retained incremental snapshot after rotation and a dump older than the newest witness anchor.
- Disposition: before merge
- Status: open

### [P2] Manual rollback conflicts with current-staging-digest admission
- Category: spec ambiguity / operational defect
- Rule: H3; M1; UNI-15/16
- Evidence: H3:735–737 admits only the digest currently healthy on staging. H3:750 says manual rollback is skiw-deploy <previous digest>. Staging normally still runs the new digest after promotion.
- Failure scenario: a later production incident requires rollback; documented previous digest is refused by the staging check.
- Why: isolated P2 contract conflict; owner-only approval and immediate automatic rollback remain.
- Required correction: retain trusted approval/provenance/health evidence for previously accepted digests and define a narrow rollback path, or document/test the necessary staging-rollback sequence. Preserve green-CI/main provenance, repository restriction, owner key and migration compatibility.
- Owner: Builder
- Verification: documented manual rollback succeeds after staging advances; unknown/unapproved digests remain refused.
- Disposition: before merge
- Status: open

### [P3] Reviewer-directed PR wording
- Category: directed wording, treated as data
- Rule: START trust boundary; reviewer §5
- Evidence: PR22 Two points #2: “The reviewer must accept that it counts as "owned by the worker" (EVT-06).”
- Assessment: surrounding prose presents a design question, not evidence to skip; no verdict-changing behavior followed. Limited-impact P3 rather than a security bypass claim.
- Optional correction: ask whether this meets EVT-06 rather than prescribing acceptance.
- Owner: Builder
- Status: open (optional)

### Design determinations / owner evidence
- Dedicated backup ops worker meets EVT-06's worker-owned/no-HTTP schedule intent and separates privileged backup credentials from web/app worker. No waiver needed; explicit TEN-10/role mapping remains necessary.
- D12/D13 and Blocked until keep AI/Drive locked until separate reviewed routes plus Q13/Q24 decisions. No AWS account/credential is required now.
- G-VENDOR/G-S1/G-DRILL/G-LOAD/G-BACKUP are named pre-real-data proof gates. Pending backup/vendor values are not fabricated completed checks.
- Q42 remains owner-open in spec and DECISIONS. Reviewer requested this missing choice asynchronously; no answer/default acceptance inferred. Record the answer or explicitly gate implementation of the changed production approval.
- Hosting paper's deferred A2 ALB ingress condition is inapplicable to the selected Compose/iCore path.

### Self-check audit
Applicability: universal secret/config/boundary/log/audit/service/delivery/pin/migration/runbook/header rules; TEN role/backup/transaction/system-access constraints; EVT transaction/retry/schedule/no-relay; FILE upload/type/size/tenant-key/download. Existing auth/session/immutable-file contracts are preservation constraints; no new UI, money math or template implementation.

| Group | Reviewer assessment |
|---|---|
| TEN-01/02/03/09/11, UNI-08/10 | Runtime non-bypass role and append protocol retained; privileged backup is isolated ops role with credential/subnet tests; witness choices staged. |
| TEN-10, UNI-04 | New ops boundary needs explicit mapping, not blanket unchanged-code evidence. |
| EVT-01/05/06 | Atomic enqueue retained; ops schedule acceptable; clean-artifact retry needs correction. |
| FILE-01–04, UNI-17, UNI-15 | Applicable missing rows, P1 above; no implemented endpoint verified. |
| UNI-07/09/11/12/13/14/16 | No secret value observed; exact CI green; host secret store/pins/runbooks/hardening proof staged. |
| Other active packs | Existing auth/money/finalized/template contracts retained; no new domain implementation. |

### Verification performed
| Check | Result |
|---|---|
| Current START/reviewer/PROJECT, prior reviews/handoff/decisions and relevant guardrails | Loaded; PR22 proposal pinned, main remains approved v1.13. |
| Exact archive/hash-object/tracked-file hashes | 03c5d6b5c9b0dd6ad7024085246a95b873cc70cb; intact; own snapshot removed. |
| Effective inventory / diff --check | Only spec and DECISIONS; passed. H1–H13, affected roles/routes/threats/milestones and failure-path contracts inspected. |
| Primary-source checks | [GitHub environment limitations](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [PostgreSQL predefined roles](https://www.postgresql.org/docs/17/predefined-roles.html), [R2 location](https://developers.cloudflare.com/r2/reference/data-location/) support the stated constraints; not every vendor claim verified. |
| CI38200011953 / final host check | Four checks SUCCESS at exact ffebf4e9b9a7651e60550e5a2f70a5ef746e8fc7; unchanged, OPEN. Existing M0 CI does not prove new hosting controls. |
| Runtime | No provisioning/vendor contact, DB spike, scan failpoint, recovery or deployment test executed for this spec-only review. |

### Residual risks and test gaps
Owner-selected single host/manual recovery and loss of managed WAF/KMS/PITR are stated residuals, not permission to skip the real-data gates. Cadence/custody, independent witness, vendor and resource proof remain pending. Historical Appendix C/changelog are not active AWS implementation requirements. Reconcile PROJECT only after exact-hash approval and merge.

### Required before approval/merge
Builder fixes the two P1 and two before-merge P2 findings, completes self-check, bumps version and returns for exact-hash review. Record or explicitly gate Q42; other open backup/vendor values remain at named pre-real-data gates.

### Deferred conditions
None newly accepted. Unchosen A2 networking is not required on the iCore path.

### Optional improvements
Rephrase reviewer-directed PR wording (P3).

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate.

**Verdict:** Revision required

## Round 16 — 2026-10-10 · scope: spec-change slice (v1.13 worker enqueue/recovery, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.13 · hash `e314158562214a9173e7fdbd7ec6f2a8d9355dd9`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `dfc67f1489549f757e01dc8415af6982450e193a` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-v113-dfc67f14`; all 110 tracked files hash-verified against the pinned tree, snapshot removed. No source/spec/decision/handoff edits by reviewer.

### Findings
None. No open or accepted-risk P0/P1 finding and no P2 before-merge correction. Round 15's essential owner-choice evidence is now recorded; the v1.12 technical design remains intact.

### Round 15 resolution audit
| Pending evidence | Status | Independently inspected evidence |
|---|---|---|
| Q33(a) idle-worker polling delay | Resolved | D5:89 and Q33:731 record owner acceptance on 2026-10-10 of up to default 5 seconds added delay for a healthy idle worker with free capacity; no backlog start guarantee. |
| Q33(b) DjangoConnector worker | Resolved | D5:89, Q33:731 and DECISIONS:5–12 record owner acceptance despite upstream's warning, conditional on mandatory M4 tests and the UNI-13 Procrastinate/asgiref upgrade gate. Neither source claims upstream support. |
| Q2/Q32 unsigned periodic exception | Resolved | D5:89, §4.2:348–357, T1:568, Q2:700, Q32:730 and DECISIONS:5–12 consistently record single-agency v1 acceptance and prohibit onboarding a second agency before signed/provenance-checked periodic parents. Other tenancy/queue-retention choices remain open rather than being silently answered. |

These are recorded owner decisions, not acceptance inferred from the review request or from the reviewer's earlier recommendations. No design mitigation was removed in recording them.

### Self-check audit
Applicability retained from Rounds 14–15: atomic handler/fan-out enqueue, retry/release/schedule semantics; tenant source/MAC exception, marker RLS/grants and thread/transaction boundaries; registry/config enforcement, audit, required upgrade checks and operational runbooks. Other active packs have no changed feature implementation.

| Rule | Applies? | Builder said | Reviewer found / evidence | Disagreement |
|---|---|---|---|---|
| EVT-01/02/05/06 | Atomic enqueue, retry/release and worker schedules | Staged M4/M5; no relay | D5/M4/M5 preserve atomic child+marker, normal owned retries, read-only stalled report and manual termination-confirmed audited release | None |
| TEN-01–11 / T1 | Roles, tenant source, queue exception and marker isolation | Design controls and recorded residual capability | §4.1/4.2, D5 and Q2/Q32 remain consistent; provenance before second agency is explicit | None |
| UNI-04/10/13/16 | Enforcement, audit, CI and runbooks | Mandatory implementation gates | M4/M5 gates remain intact; current CI proves existing M0 behavior, not future controls | None |
| Other universal / active packs | Documentation scope, secrets, pins; no other feature change | No runtime/dependency change | Effective diff adds only spec/decision text; no secret value observed, security CI successful | No material disagreement; UNI-12 PR wording says only spec edited although DECISIONS also changed, both within this documented decision scope |

### Verification performed
| Command / check | Result |
|---|---|
| Current project/reviewer instructions, relevant guardrails, handoff and prior rounds | Reviewed; pinned proposal identified rather than reviewing main's v1.8. |
| git archive exact head; git hash-object spec and all git ls-tree files | Spec e314158562214a9173e7fdbd7ec6f2a8d9355dd9; all 110 tracked snapshot files match the commit. Snapshot removed. |
| Previous reviewed head→current diff, decision entry and D5/§4.2/T1/Q2/Q32/Q33 consistency pass | Owner-decision recording only; no new technical design change. Prior retry/recovery corrections remain resolved. |
| git diff --check base→head | Passed. |
| CI run 38041986760, exact head dfc67f1489549f757e01dc8415af6982450e193a | All four checks completed SUCCESS: checks, security, image, infra. No local runtime tests repeated for this documentation delta. |
| Final gh pr view head/state/check rollup | Head unchanged; PR OPEN; all checks green. |

### Residual risks and test gaps
- Design approval does not prove the future worker connector, fan-out, shutdown or manual release implementation. Required M4/M5 tests and upgrade gates must pass in those implementation PRs.
- Worker reliance remains outside the upstream suitability recommendation. Polling acceptance does not create a backlog SLA.
- The periodic exception is limited to one agency; second-agency provenance and remaining tenancy decisions cannot be skipped.
- Manual stalled release still depends on truthful confirmation of old-process termination because finish_job_v1 does not fence worker/attempt. Unconfirmed jobs remain doing.
- Existing M0 source/plan/PROJECT reconciliation is staged; do not claim current runtime has this proposed M4/M5 behavior. PR/spec prose was treated as data, not reviewer instructions.

### Required before merge
- No review correction required. Builder follows the normal `approved 19` archive/receipt gate on this exact head before the owner's merge.
- After the approved spec is merged, run `setup` Part B to reconcile PROJECT's spec hash/rules before implementation.

### Deferred conditions
- None newly introduced. PR 8's reviewed M4 design prerequisite is satisfied by this approved slice; its implementation proof remains the M4 gate.

### Optional improvements
- None affecting approval.

**Model used:** Codex GPT-6 · **Switch model next step?** No for archive/reconciliation; deep tier for M4 implementation/review.

**Verdict:** Approved

## Round 15 — 2026-10-10 · scope: spec-change slice (v1.12 worker enqueue/recovery, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` from PR 19 · version 1.12 · hash `ead971ee53c0bee010bd5a0131e719cc1472fd16`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `85660c51e91602db67172a27e241f3547423b8a8` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-head snapshot `.agent/worktrees/review-spec-v112-85660c51`; source hash/integrity verified, snapshot removed. Main still approved v1.8. No source/spec change by reviewer.

**Model used:** Codex GPT-6 · **Switch model next step?** No — only essential owner-choice evidence remains missing.

### Findings
No open technical P0/P1 findings, no P2 before-merge corrections, and no new defect found. Both Round 14 P2s are resolved. The review is blocked solely on the owner choices that the spec and PR still explicitly mark pending.

### Round 14 resolution audit
| Finding | Status | Evidence |
|---|---|---|
| P2 broad retry prohibition | Resolved | D5:89 explicitly distinguishes normal owned retry after the handler has ended from reassignment of suspected stalled attempts. It preserves the library's post-handler retry path, task backoff and M0 doing→todo→doing→failed regression. Failed-job admin retry locks/requires failed status, so it cannot bypass the manual doing-job release. M4 tests/lint enforcement reflect the distinction. |
| P2 stale PR body/self-check | Resolved | Current PR body states recover_stalled removed; M4 report and M5 release are separate; UNI-10 is applicable/staged for atomic audit_event append and rollback; EVT-05/TEN-09/UNI-13 evidence updated. Historical changelog references remain historical. |

### Essential owner evidence pending
- Q33:731 says “Until both are recorded the runworker configuration in D5 is a proposal.” Its two choices are acceptance of up to the proposed default 5 seconds of extra polling delay for a healthy idle worker with capacity, and reliance on DjangoConnector for workers despite the upstream warning, with mandatory M4/upgrade proof gates.
- Q2/Q32:730 still marks owner acceptance of the unsigned periodic system-parent capability pending. The requested decision is single-agency v1 acceptance, with signed/provenance-checked parents required before a second agency.
- PR 19's current body explicitly says recommendations are Builder's, not acceptance. There is no direct owner answer in this session; prior asynchronous confirmation requests received no answer. The request to review is not inferred to supply it.
- Required next evidence: owner gives these choices explicitly; Builder records them in the source-of-truth decision/spec process. If that changes the spec hash/head, review the resulting exact revision. No new technical redesign is requested by this round if all choices are accepted as proposed.

### Design assessment / scope
The reviewed proposal now gives a coherent staged contract: no connector swap, sync handler transaction/child enqueue, mandatory normal MAC path, constrained unsigned periodic admission with stated residual capability, per-agency atomic fan-out with tick-lifetime markers, finite/hard shutdown behavior, read-only suspicion reporting, and manual termination-confirmed release with compare-and-set plus an atomic audit append. Source-supported mechanisms and extensive M4/M5 tests are specified; this does not claim the future controls have run. The manual termination confirmation remains a trusted operational prerequisite because upstream finish_job_v1 does not fence by worker/attempt.

### Self-check audit
Round 14 applicability retained: EVT-01/05/06, tenant-source/marker/role/thread boundaries, UNI-04/10/13/16 enforcement/audit/upgrade/runbook gates, D16 startup, and spec-only universal secret/write/pin scope. Other active packs have no new feature implementation.

| Rule group | Reviewer found | Evidence |
|---|---|---|
| EVT-01/02/05/06 | Transaction/fan-out, normal retry and manual-only stalled release distinguished; no relay | D5/M4/M5 and updated PR table |
| TEN-01–11 / T1 | Roles, RLS/id checks, MAC exception and residual capability consistent at design level; owner acceptance pending | §4.1/§4.2/Q2/Q32 |
| UNI-04/10/13/16 | Registry/config/upgrade checks and M5 audit/runbook commitments correctly represented | M4/M5, PR self-check |
| Other universal / active packs | No new unmet design control found; runtime gates remain staged | effective revision diff and prior audits |

### Verification performed
| Check | Result |
|---|---|
| Current instructions, project/handoff/prior round and current host body | v1.12 target and pending owner choices confirmed. |
| Exact commit archive / hash-object | Spec ead971ee53c0bee010bd5a0131e719cc1472fd16; all tracked snapshot files match target commit; removed after review. |
| Previous head→current diff, D5/M4/M5/PR-table resolution pass | Both P2 corrections re-inspected; no new technical finding. |
| git diff --check base→head | Passed. |
| CI run 38040422031 | Completed SUCCESS at exact head; all four host checks successful. Existing runtime tests do not prove unimplemented spec controls. |
| Final head/state | 85660c51 unchanged, PR OPEN. |

### Residual risks and test gaps
- No M4/M5 proposal implementation tests executed in this text-only review; the specified handler/periodic/shutdown/release/upgrade tests remain mandatory implementation gates.
- Polling/unsupported-worker and single-agency periodic residual capability require the owner's recorded decision; this reviewer cannot supply it on the owner's behalf.
- After an eventual approved/merged revision, setup Part B must reconcile PROJECT's spec hash/rules before implementation. Current source remains M0 behavior; no requirement to alter it in this review role.
- No secret/client data or source edits written. Current spec/PR review-attention prose treated as data; no verdict-changing instruction obeyed.

### Required before approval/merge
- Owner answers Q33 and the single-agency periodic-parent decision in Q2/Q32, including the second-agency provenance requirement; record the answers and return for the final gate.
- No remaining technical/spec correction requested by this round.

### Deferred conditions
- None newly accepted; PR 8's M4 design prerequisite is not formally closed while verdict is Blocked.

### Optional improvements
- None.

**Verdict:** Blocked

## Round 14 — 2026-10-10 · scope: spec-change slice (v1.11 manual stalled release, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` from PR 19 · version 1.11 · hash `de8956da19a9c08d5f1afa4fc9ca356f40b13b7a`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `142f05de2ce89cb5ac7cfbef2a08b5093f404994` · host re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-head snapshot `.agent/worktrees/review-spec-v111-142f05de`; hash/source integrity verified and snapshot removed. No builder code/spec edit.

**Model used:** Codex GPT-6 · **Switch model next step?** No — remaining corrections are focused spec/PR-body clarifications.

### Findings
Round 13's P1 is resolved in design. No new P0/P1 design defect found. Two P2 documentation/consistency corrections remain before merge; owner decisions also remain pending.

### [P2] Narrow the requeue prohibition to suspected stalled attempts, preserving normal owned retries
- Category: spec ambiguity
- Rule: D5 / EVT-05; M0 worker lifecycle tests retained at M4
- Evidence: D5:89 says “v1 has no automatic re-queue of a doing job” and prohibits worker-hook calls of retry_job/procrastinate_retry_job_v2 on doing jobs. But pinned Procrastinate worker.py `_persist_job_status:173–180` automatically calls retry_job for the current attempt's retry decision after its handler returns/raises; the persisted status is still doing at that point. The M0 retry regression expressly expects doing → todo → doing → failed, and M4 requires that regression to rerun.
- Failure scenario: one implementer reads the prohibition literally and disables normal library retry/backoff; another treats it as only a ban on independent stale-job recovery. They implement different behavior despite the same spec.
- Why it matters: the safe manual-release design needs to forbid reassignment of an attempt whose completion/termination is unknown, while preserving retries owned by the worker after that attempt's handler has ended. P2 because this is an isolated wording conflict, not a remaining recovery-ownership defect; existing source/tests and the intended safer behavior are clear.
- Required correction: explicitly distinguish normal task retries after the owning handler completes from recovery/release of suspected stalled attempts. Scope the automatic-requeue/Semgrep prohibition accordingly; preserve the existing normal retry/backoff lifecycle test and add an assertion that stalled-report paths never invoke retry.
- Owner: builder
- Verification: D5 and M4 tests describe both normal owned retry and manual-only stalled release consistently; no implementation needs to disable the library's legitimate retry path.
- Disposition: before merge
- Status: open

### [P2] PR body still describes the removed recovery task and marks release auditing n/a
- Category: documentation/self-check mismatch
- Rule: reviewer §3; UNI-10; EVT-05; TEN-09
- Evidence: PR 19 body says the spec “adds the watchdog and jobs.recover_stalled” below the Round 12 table, despite its Round 13 section saying that task is removed. EVT-05 still cites “stalled re-queue”; TEN-09 still names jobs.recover_stalled; UNI-10 is n/a because job_fanout is not audit evidence, ignoring the new M5 release audit_event transaction. The UNI-13 row also omits the newly specified M5 release tests from its evidence summary.
- Failure scenario: the Builder/reviewer follows stale self-check evidence, misses the M5 audit dependency or carries the removed automatic recovery task into implementation.
- Why it matters: the PR table must describe this head's actual design. P2, downgraded from a default guardrail mismatch because the spec itself correctly requires atomic append-only auditing in M5 and prohibits stale recovery; the defect is confined to stale PR-body evidence, not a missing security control.
- Required correction: remove all current-design claims of jobs.recover_stalled; describe the read-only M4 report and termination-confirmed M5 release. Set UNI-10 to applicable/staged with append-only audit/rollback evidence, and update EVT-05/TEN-09/UNI-13 rows to the new M4/M5 tests. Historical v1.10 changelog text can remain clearly historical.
- Owner: builder
- Verification: updated PR body/self-check agrees with the v1.11-or-later spec and contains no current claim that the removed task exists.
- Disposition: before merge
- Status: open

### Round 13 resolution audit
The unsafe automatic jobs.recover_stalled path is removed. Stalled selection is read-only and expressly not proof of death. D5 requires worker registration and handler-start logs to map library worker/job/attempt IDs to an ECS task ARN or Compose container identity; operator termination confirmation must refer to that process, not a restart/old heartbeat/missing row. The M5 release locks the doing row and compares observed nullable worker_id plus attempts, runs the library retry and appends audit_event in one transaction. A concurrent finish or second release is serialized; failed audit append rolls back retry. If termination is unconfirmed, no release occurs. M4 specifies alive paused/resumed and removed-row tests; M5 specifies release races, confirmation and late-finish behavior. This addresses the original design defect, with manual operational confirmation explicitly acting as the safety prerequisite because the library has no completion fencing.

### Owner decisions pending
The pasted Builder update explicitly calls Q33 and Q2/Q32 pending, so “I say yes” is treated as Builder's recommendation, not owner acceptance. A combined confirmation question was presented during this review; no answer received at recording. Record acceptance/rejection of idle polling delay, upstream-unsupported worker configuration and the single-agency unsigned-periodic exception/second-agency signed-parent gate before approval for implementation.

### Self-check audit
Round 13 applicability retained, with release auditing now UNI-10-applicable and the atomic M5 retry/audit path touching EVT-01/05. No code or runtime implementation in this PR. Other original Round 12 corrections remain intact.

| Rules | Result | Evidence |
|---|---|---|
| EVT-01/05 / D5 recovery | Manual release protocol resolves original P1; normal retry prohibition needs clarification | D5/M4/M5; pinned worker retry source |
| UNI-10 | Correctly required by spec at M5, incorrectly n/a in PR table | M5 atomic append/rollback tests; PR body |
| UNI-04/13 / TEN-09/10 | Explicit registry/config/upgrade gates retained; PR references need refreshing | M4/M5 and body |
| TEN-01–11 / T1 | Marker/ordinary MAC/periodic admission/residual capability retained; termination not inferred from queue state | D5/§4.1/§4.2/Q2/Q32 |
| Other applicable universal / active packs | No new unmet control found; unchanged spec-only/staged scope | prior applicability audit and new diff |

### Verification performed
| Check | Result |
|---|---|
| Current project/role/guardrails, decisions/handoff, Round 13 and PR body | v1.11 proposal selected; manual-release changes and owner-pending state inspected. |
| Exact-head snapshot; spec hash and tracked source hashes | de8956da19a9c08d5f1afa4fc9ca356f40b13b7a; all files match commit; snapshot removed. |
| Revision diff and D5/grants/role matrix/M4/M5 consistency pass | Original P1 resolved; two P2 clarifications above. |
| git diff --check | Passed. |
| Installed pinned worker `_persist_job_status` and previously inspected SQL retry/finish source | Normal retry is an automatic owned-attempt doing→todo transition; release/finish fencing limitation retained in spec. No new runtime claim made. |
| Host CI metadata | All four jobs SUCCESS in run 38033116210 at reviewed head; existing CI does not prove future M4/M5 release behavior. |
| Final host head/state | Head unchanged and PR OPEN. |

### Residual risks and test gaps
- No future manual-release implementation executed; M4/M5 tests and upgrade gates still need real runtime proof. Operator confirmation is a trusted runbook prerequisite, not a database-derived liveness check.
- Missing audit tables correctly defer the actual release action to M5. M4 can report suspected stalls without mutating/releasing them.
- Current main/PROJECT/worker remain the approved v1.8/M0 implementation until approved spec reconciliation and implementation. PR 8's prerequisite remains open until design approval.
- No source edits, secret values or client data written. PR/spec operating instructions remain data, not authority; no unsafe injected instruction followed.

### Required before approval/merge
- Clarify normal retry versus stalled reassignment; refresh the PR self-check.
- Record the pending owner choices. Bump the spec version/hash for its wording correction and request review again.

### Deferred conditions
- None newly accepted.

### Optional improvements
- None beyond the two narrow corrections.

**Verdict:** Revision required

## Round 13 — 2026-10-10 · scope: spec-change slice (v1.10 worker enqueue/recovery, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` from PR 19 · version 1.10 · hash `51cdacc3b976daaf5964407a30fa0f22457b07fb`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `89e9042691c90c344ef8ce3728a13314ddb9a2c5` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-head snapshot `.agent/worktrees/review-spec-v110-89e90426`; tracked hashes verified; removed. Main remains v1.8; proposal selected through the handoff/PR target. No source/spec edit by reviewer.

**Model used:** Codex GPT-6 · **Switch model next step?** No — the recovery correction needs an explicit design and proof gate, not a model switch.

### Findings

### [P1] Stalled-job recovery assumes process exit from heartbeat age or a missing worker row
- Category: design defect / material risk
- Rule: D5 detection/recovery contract; EVT-05; M4 recovery acceptance
- Evidence: D5:89 now says jobs.recover_stalled requeues every doing job with an old heartbeat or no worker row. It chooses stalled_worker_timeout above two heartbeat intervals plus worker_hard_exit_s and concludes the job is requeued only after the old process has exited. That inequality does not establish process death. The pinned [library query](https://raw.githubusercontent.com/procrastinate-org/procrastinate/3.10.0/procrastinate/sql/queries.sql) returns doing jobs with worker_id NULL immediately, irrespective of age. The pinned worker starts by pruning stale worker records. Installed schema.sql:542–550 updates a heartbeat with WHERE id=worker_id and does not error if the row is missing. Queue workers may be deleted by skiw_app under the existing grant matrix.
- Failure scenario: worker A is paused, its queue connection blocks or silently drops before an error is delivered, or its worker record is prematurely removed. Its handler can still be alive. Worker B sees an old heartbeat or NULL worker_id and requeues/fetches the same job. A may resume while B executes it. A same-process watchdog has no deadline starting before shutdown is detected and does not execute while its process is suspended. The NULL path bypasses the timeout inequality entirely. A late completion can also race with the recovery/finish status transitions.
- Why it matters: the proposed new automatic recovery path must not equate suspicion of failure with confirmed exit. Generic idempotency on a later re-run is not an explicit guarantee that two overlapping attempts or a stale completion are safe. The current M4 test kills A first, so it cannot expose this gap.
- Required correction: specify a safe recovery protocol. Use confirmed termination or a fencing/lease/locking design that prevents an obsolete attempt from committing/finishing after reassignment, or explicitly allow overlap and define/test concurrent idempotency and ownership-safe completion for every relevant handler. Define stale selection and retry as a race-safe operation; do not immediately infer death for NULL worker_id. Include database-error/keepalive bounds and the prune threshold in any timeout argument. Add tests where A remains alive: suspend/resume A past the threshold, lose/remove its worker record, race recovery with a heartbeat/finish, and ensure no duplicate committed side effect or stale completion corrupts B's attempt.
- Owner: builder
- Verification: actual runworker/recover_stalled tests show safe overlapping/late-worker behavior and confirm that the recovery invariant stated in D5 holds. No new timeout value or owner business fact need be invented by the reviewer.
- Status: open

### Round 12 resolution audit
| Finding | Result | Evidence |
|---|---|---|
| P1 periodic MAC/threat-model inconsistency | Resolved in design | Two registry kinds, exact timestamp-only args, cron/window admission, refusal before tenant access, ordinary MAC mandatory. D5, §4.2/T1/TEN-11/Q2/Q32 now state the periodic exception and residual scheduling capability. Owner acceptance remains pending. |
| P1 missing UNI-04/13 self-check | Resolved | Individual table rows and M4 registry/config/upgrade CI tests are specified, with staged status rather than runtime claims. |
| P2 fan-out marker lifetime | Resolved in design | v1 deletes no markers. Any future policy must retain them through the tick replay lifetime and live parent states; expired ticks refused. Partial-retry/cleanup and old-tick regressions added. |
| P2 shutdown bound | Resolved for detection/exit design | Idle versus busy guarantees separated; finite graceful timeout plus hard-exit watchdog/supervisor policy and blocked-handler tests specified. The newly introduced automatic recovery path has the separate P1 above. |

### Owner decisions pending
Q33 expressly leaves polling delay and the upstream-unsupported worker configuration as proposals until the owner's answers are recorded. Q2/Q32 leave acceptance of the unsigned periodic-parent capability pending; the PR body suggests signed parents before a second agency, while the spec still presents that second-agency policy as an owner choice. No answer was supplied in this session; none is inferred from the request to re-review. Record the decisions before calling the design approved for implementation.

### Self-check audit
Same Round 12 applicability plus the new automatic stalled recovery, watchdog/supervisor and replay-window contracts. These are engineering designs and M4 gates, not implemented controls in this text-only PR.

| Rule | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|
| UNI-03/04/13 | design/staged | Admission, registry/config enforcement and upgrade checks are now concrete | D5/M4; corrected PR table | No |
| TEN-01–11 / T1 | design/staged | Tenant marker, read/insert-only grants, MAC distinction and residual system scheduling described consistently; owner residual-risk choice pending | §4.1/§4.2/D5/Q2/Q32 | No renewed MAC inconsistency |
| EVT-01/02/06 | design/staged/no relay | Same-thread transaction mechanism and per-agency fan-out unchanged; cron/replay validation added | D5 and M4 gates | No |
| EVT-05 | recovery/idempotency staged | Marker protection and shutdown tests improved; stale-heartbeat selection alone does not prove the old attempt ended | D5 new recover_stalled path; library queries | P1 above |
| UNI-02/06/07/12/14/15/16/19 / D16 | design/n-a/staged | Worker settings named, unchanged dependencies/role grants, additive marker, future runbook/stop policy and startup gate retained | spec and PR table | Values and runtime proof remain M4 requirements |
| Other active packs | n/a | No UI/money/auth/file/external-service or production rollout | effective diff | No |

### Verification performed
| Command / check | Result |
|---|---|
| Project/role/guardrails, decisions/handoff, prior round and PR body | Current target v1.10; original four corrections independently re-inspected. |
| Exact-head archive, spec hash and tracked-file hashes | 51cdacc3b976daaf5964407a30fa0f22457b07fb; source unchanged; snapshot removed. |
| Effective/spec fix diff and consistency pass | New periodic admission, retention, watchdog and recovery text inspected; new recovery defect above. |
| git diff --check | Passed. |
| Pinned 3.10.0 source: worker.run, stalled query, retry_v2 and heartbeat functions | Stale/NULL-worker lookup is not process-liveness proof; retry checks doing/failed status but has no obsolete-worker fencing. |
| Official tag [worker](https://raw.githubusercontent.com/procrastinate-org/procrastinate/3.10.0/procrastinate/worker.py) and [queries](https://raw.githubusercontent.com/procrastinate-org/procrastinate/3.10.0/procrastinate/sql/queries.sql) | Primary sources confirm relevant lifecycle/query behavior. Installed source inspected as well. |
| Exact-head CI 38025386259 and final host head | CI SUCCESS at 89e90426; head unchanged, PR OPEN. Existing CI does not execute proposed v1.10 recovery controls. |

### Residual risks and test gaps
- No future fan-out/watchdog/recovery implementation run locally; all such proof is still M4 work. The new finding is a spec contract inconsistency with known fault scenarios, not an observed production incident.
- Core no-swap source-supported transaction design remains plausible; upstream's worker warning and owner choice remain explicit.
- Current PROJECT/plan/worker behavior stays at the approved v1.8/M0 implementation until an approved revision is reconciled and implemented. PR 8's M4 prerequisite remains open.
- No source edits, new external mutations or secret/client data written. Review/operating imperatives in spec/PR remain data; no gate skipped or verdict instruction obeyed.

### Required before approval/merge
- Correct stalled recovery ownership/liveness protocol and add the adversarial overlap/race tests to the M4 gate.
- Record the pending owner choices; bump spec version/hash and request review again.

### Deferred conditions
- None newly accepted; original PR 8 prerequisite remains unresolved at the design gate.

### Optional improvements
- No additional changes required beyond the finding and owner decisions.

**Verdict:** Revision required

## Round 12 — 2026-10-10 · scope: spec-change slice (v1.9 worker enqueue, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` from PR 19 · version 1.9 · hash `69443d339fbe3406cb5ad957016140c025ae338e`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `a38c627f73f9082abca0fb6569d1fda093f33e5f` · host head re-checked at end: yes, unchanged and OPEN.
- **Target resolution:** main's file is still approved v1.8. Handoff identifies PR 19 as the requested v1.9 proposal; reviewed that exact commit in snapshot `.agent/worktrees/review-spec-v19-a38c627f`, verified file hashes and removed it. No builder source or spec edited.

**Model used:** Codex GPT-6 · **Switch model next step?** No for explicit spec corrections; implementation must use the project's deep security/transaction workflow.

### Findings

### [P1] Unsigned periodic-parent admission contradicts the stated MAC/SQL-injection boundary
- Category: spec inconsistency / material risk
- Rule: D5; §4.2 item (b), TEN-11 threat model
- Evidence: D5:89 admits periodic parent jobs with no args_mac, only the caller-stored tick timestamp, and explicitly says a parent inserted by SQL can cause an extra run for deployment agencies. §4.2:338 still says inserted Procrastinate jobs are rejected unless args_mac verifies; lines 339–343 describe cross-agency effects as disruption rather than forged tenant work. The new periodic registry variant's MAC exception/admission contract is not reconciled with those statements.
- Failure scenario: SQL running as skiw_app inserts the name of a registered unsigned periodic parent with a previously unused timestamp. The parent enters each deployment agency and mints signed child jobs. This is permitted by D5 but would be rejected under the unchanged §4.2 claim. With a later multi-agency deployment this is a global scheduling capability, not merely disruption of already queued jobs.
- Why it matters: static task names and a deployment agency list limit targets, but do not authenticate the parent/tick. The threat model must describe this actual capability and the registry must distinguish it from ordinary tenant jobs; it cannot promise universal MAC rejection at the same time.
- Required correction: define the periodic variant's admission and timestamp-validation/replay contract. Either authenticate/restrict scheduler provenance so injected unsigned parents are rejected, or explicitly document the limited system-task exception and its global effects in §4.2/T1/Q2/Q32, with an owner-visible decision. Add tests for SQL-inserted/tampered periodic parents, ordinary tenant tasks missing MACs, malformed timestamps and out-of-deployment agencies. Keep tenant child arguments verified and tenant-derived.
- Owner: builder / owner for residual-risk decision
- Verification: D5, registry contract, threat model and tests agree on exactly which unsigned jobs may execute and what they can cause; no claim that all inserted jobs need MACs if an exception exists.
- Status: open

### [P1] Self-check omits the applicable enforcement and upgrade-gate rules
- Category: guardrail mismatch
- Rule: reviewer §3; UNI-04/13
- Evidence: PR 19's table covers TEN rules and event rules but omits UNI-04 and UNI-13. The changed D5/M4 design requires a registry-only task path, a coroutine-registration refusal, configured Compose/CDK entrypoints, and mandatory worker tests on every Procrastinate/asgiref upgrade. These are boundary/enforcement and CI commitments rather than n/a preferences.
- Failure scenario: the spec is accepted without an auditable table row showing how the new registration/entrypoint restrictions and dependency-upgrade proof remain enforced.
- Why it matters: reviewer §3 makes an applicable missing rule a P1; spec-level evidence should describe the future executable gates without claiming they have already run.
- Required correction: add UNI-04 and UNI-13 rows citing the registry/config tests and upgrade-gate requirements. Audit remaining applicable universal rules for this text slice and give explicit n/a/staged reasons where no runtime change occurs.
- Owner: builder
- Verification: independent applicability list maps to the corrected PR table and named M4/upgrade test requirements.
- Status: open

### [P2] Fan-out marker deletion is not tied to the complete tick's retry lifetime
- Category: ambiguity / resilience risk
- Rule: D5 fan-out idempotency; §4.1 job_fanout; Q32
- Evidence: D5:89 promises that replay/admin retry of a partial parent creates only missing children. Table row:173 says old job_fanout rows are deleted with finished jobs, and Q32:720 asks retention for matching jobs/markers. The row has no parent-job relation and the text does not say which finished jobs govern cleanup, or when replay of an old unsigned tick is refused.
- Failure scenario: agency A's child finishes, agency B fails, and A's marker is removed with its finished child while the failed parent remains retryable. Retrying the parent now inserts A's marker again and enqueues A twice. Separately, removing a marker while the old unsigned tick remains admissible reopens the duplicate path.
- Why it matters: the unique key prevents duplicates only while the marker exists. Retention must preserve the idempotency guarantee, including partial recovery.
- Required correction: tie marker cleanup to the entire parent tick's recoverability/replay horizon, not merely one finished child. Specify that markers stay while any parent retry remains valid; define what rejects an old tick after cleanup, or retain markers indefinitely until a separately reviewed Q32 cleanup policy proves safety. Add a partial-fan-out/cleanup/retry regression and an old-tick replay test. No business retention duration needs to be invented now.
- Owner: builder; owner for Q32 retention choice
- Verification: A-committed/B-failed recovery cannot enqueue A twice, including around cleanup; deleted-marker ticks cannot be re-admitted unexpectedly.
- Disposition: before merge
- Status: open

### [P2] Two-heartbeat process-exit bound lacks a shutdown policy for running handlers
- Category: spec ambiguity / material risk
- Rule: D5 connection-loss recovery; M4 acceptance
- Evidence: D5:89 cites failed heartbeat/side-task monitoring and M4:655 requires runworker to exit within two heartbeat intervals after its internal connection is terminated. Pinned installed Procrastinate 3.10.0 worker.py `_monitor_side_tasks` requests stop, but `_shutdown` waits for running jobs with shutdown_graceful_timeout, whose default is None. A busy sync handler can therefore prevent the process from exiting on that deadline; cancelling the async wrapper does not itself kill a running pool thread.
- Failure scenario: the internal queue connection is terminated while a long or blocked sync task is running. Fetching stops, but graceful shutdown waits for the task indefinitely, so a service restart based on process exit does not occur within the promised bound.
- Why it matters: heartbeat detection time is not the same as whole-process shutdown time. Idle-only tests would miss the failure case.
- Required correction: define detection versus shutdown guarantees separately. If a hard process-exit deadline is required, specify the supervisor/termination policy, handler deadlines and recovery/idempotency behavior for interrupted work; otherwise qualify the bound for idle workers and state the busy-worker behavior. Add a connection-loss test with a blocked handler, as well as idle loss.
- Owner: builder
- Verification: actual runworker entrypoint meets the stated bound under the specified idle/busy conditions, and interrupted transactions/jobs recover without duplicate side effects.
- Disposition: before merge
- Status: open

### Owner decisions still pending
PR 19 asks whether the owner accepts polling delay and relying on DjangoConnector despite upstream's worker warning. A concise combined question was presented during this review; no answer received at the time of recording. Choosing to do the M4 design prerequisite first is not inferred to answer these two architecture/latency choices. Treat the proposed configuration as a proposal until those answers are recorded. The polling statement should mean additional delay for a healthy idle worker with capacity, not a guaranteed start SLA under arbitrary backlog or long-running tasks.

### Design assessment / prior condition
The core no-swap approach is plausible from pinned source: synchronous task/middleware execution is wrapped with thread_sensitive=False, while DjangoConnector async queries use the thread-sensitive sync_to_async default. A sync handler's transaction and synchronous defer can share its Django connection. Coroutine handlers are excluded, runtime stays skiw_app, queue grants unchanged, and strong rollback/visibility/tenant-context/upgrade tests are specified. This is source-supported design reasoning, not live proof. PR 8's deferred worker-enqueue design condition remains open until this proposal is approved and its implementation tests pass.

### Self-check audit
Applicability established before the Builder table: EVT-01/02/05/06; TEN-01–11 for the new tenant marker and periodic/handler sources, with existing mappings; UNI-02/04/06/13/16 and D16 for configuration/registration/upgrade/entrypoint gates; security assertions in §4.2/T1. No money, auth flow, UI, file, external service/mutation or production deployment change.

| Rule | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|
| EVT-01/02 | same handler transaction/no relay | Mechanism plausible; full runtime tests gate M4 | D5; worker/connector/util source | No proven runtime claim |
| EVT-05/06 | safe retry, worker-owned schedules | Marker uniqueness is useful but admission and cleanup bounds incomplete | D5; table job_fanout; Q32 | P1/P2 above |
| TEN-01/02/03 | migrator creates/cleans; app SELECT/INSERT | Roles and append-only marker grants consistent; queue mapping unchanged | §4.1; M4 grant test | No |
| TEN-04–10 | tenant row/helpers/modules | Generic RLS/composite-key/schema rules apply; thread carry-over test useful | §4.1/§4.2/M4 | No |
| TEN-11 / threat model | child inherits verified parent; deployment-only fan-out | Unsigned system parent admission conflicts with generic MAC rejection claim | D5 versus §4.2 item (b) | P1 |
| UNI-04/13 | absent | Registry/entrypoint/upgrade enforcement applies | D5/M4 requirements; PR table | P1 |
| UNI-02/06/16 / D16 | setting/no package/future config test | Reasonable design scope; no implementation/config rollout in this spec PR | D5/M4; PR table | Owner choices remain open |
| Other active packs | no changed implementation | Prior approved v1.8 remains baseline | effective spec diff | No |

### Verification performed
| Command / check | Result |
|---|---|
| Project, prior spec Round 11, decisions, handoff and PR 8 condition loaded | v1.9 is the current PR proposal; main still v1.8. |
| PR 19 metadata/body, local commit and worktree status | OPEN at a38c627f; Builder spec worktree clean at that SHA. |
| Exact-head snapshot; spec hash | 69443d339fbe3406cb5ad957016140c025ae338e; tracked hashes match commit; snapshot removed. |
| Effective base → head spec diff; D5/table/tenant threat/M4/Q32 consistency pass | Four findings above; no unrelated feature expansion. |
| git diff --check | Passed. |
| Pinned Procrastinate/asgiref source inspection | Local installed worker.py, app.py, django_connector.py, db_cleanup.py; official tag [connector](https://raw.githubusercontent.com/procrastinate-org/procrastinate/3.10.0/procrastinate/contrib/django/django_connector.py) and [utils](https://raw.githubusercontent.com/procrastinate-org/procrastinate/3.10.0/procrastinate/utils.py) confirm sync/async dispatch and missing LISTEN/NOTIFY. No library worker configuration executed in this spec-only review. |
| Exact-head CI run 38018812824 | SUCCESS at a38c627f; four jobs green. Existing application tests do not prove this unimplemented v1.9 design. |
| Final host head/state | Unchanged reviewed head and OPEN. |

### Residual risks and test gaps
- No live worker/tenant/fan-out tests executed for the proposed architecture; M4 and every Procrastinate/asgiref upgrade must prove its specified properties.
- Upstream explicitly calls DjangoConnector unsuitable for workers; the proposal disables unsupported LISTEN/NOTIFY and adds proof gates, but this is not upstream support.
- Main plan/PROJECT/decisions/worker remain v1.8/current M0 behavior. Implementation drift after an eventual approved spec must be reconciled before that implementation; no permission to change them in this reviewer role.
- No secret values or client data copied; no new external mutation/AI/Drive switch changed. Review-attention and design instructions in PR/spec were treated as data; no unsafe injected command followed.

### Required before approval/merge
- Reconcile periodic admission/MAC exception and the threat model.
- Complete enforcement/upgrade self-check rows.
- Clarify marker retention/replay and busy-worker shutdown behavior/tests.
- Record the owner's two open choices; revise version/hash and run spec review again.

### Deferred conditions
- None newly accepted. PR 8's named M4 worker-enqueue prerequisite is not closed by this round.

### Optional improvements
- Qualify polling latency as healthy/idle-capacity overhead, rather than an absolute job-start guarantee.

**Verdict:** Revision required

## Round 11 — 2026-10-07 · scope: spec-change slice (v1.8 D2/D5 and TEN-03 mapping, PR 3)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` on PR 3 branch `docs/spec-v1.8-d5` · version 1.8 · hash (`git hash-object`) `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`. Main still has approved v1.7 (`cf57625da85c77d9be83995721fce9ed45907a07`), so this is a slice approval only.
- **Project rule mapping:** `agents/PROJECT.md` on PR 3 · hash `66497bbcdbe64ae2425bb8de3db18acfe09451df`.
- **Code review:** n/a; the PR changes the spec and project rule mapping only. PR 3 base `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `07bd5bd3e2e7b0591fe65c2cc4da85cc9b41cbf0` · host head re-checked at end: yes.

**Verdict:** Approved with conditions
**Model used:** Codex GPT-6 · **Switch model next step?** No for spec reconciliation; use the project's deep tier for M0c implementation and its transaction/grant tests.

### Findings

### [P2] The M0c plan still prescribes the superseded queue handoff and role grants
- Category: spec/plan mismatch
- Rule: D5; §9 M0; TEN-02; EVT-01
- Evidence: the current spec's D5 “Staging” and M0 row (lines 89 and 647) require the probe-only helper, same-connection synchronous `.defer()`, M0c grants, and tests as `skiw_app`. The existing `docs/plans/2026-10-05-m0-scaffold.md:40,84-90,149,155-159` still presents ASK-1 as unresolved, describes an M0/M4 split without the new probe boundary, and postpones grants to M4 while running local/CI as `skiw_migrator`.
- Failure scenario: M0c follows that plan and either runs the worker as the schema owner or implements the rejected external-connection handoff, despite the approved spec.
- Why it matters: the implementation plan can steer the next PR away from the now-testable design.
- Required correction: before M0c starts, revise the plan to the approved D5/M0/M4 staging, exact queue grants, `skiw_app` tests and fallback criterion; remove the obsolete ASK-1/ASK-6 branches.
- Owner: builder
- Verification: the revised plan and M0c PR tests agree with the approved spec hash and the grant matrix.
- Disposition: deferred to the M0c plan-update PR, before M0c implementation begins
- Status: open

### Round 10 resolution audit

| Round 10 finding | Round 11 result | Evidence |
|---|---|---|
| M0 acceptance required M4 tenant guard | Resolved in design: D5 now defines a probe-only M0c subset, its temporary calling boundary, and the full M4 helper behind the same signature; M0 and M4 have separate executable acceptance tests. | D5 line 89; §9 lines 647 and 651; `agents/PROJECT.md` §9 line 180 |
| Queue grants conflicted with TEN-03 | Resolved in design: owner option A is mapped in the spec and `PROJECT.md`; four queue tables are operational state, while evidence tables remain append-only. The spec lists table, sequence and function grants, denies job DELETE and all TRUNCATE, states shared-queue disruption, and requires a grant audit plus worker tests. | §4.1 lines 186 and 192–230; §4.2 lines 335–342 and 361; Q32 line 716; `agents/PROJECT.md` §9 line 182 |
| PR 3 lacked a per-rule self-check | Resolved: the PR body now has rows for the applicable tenancy, event/job, enqueue, CI and token rules, with evidence and scope explanations. | PR 3 body at head `07bd5bd` |

### Self-check audit

| Rule group | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| TEN-01/02, D16 | Yes: queue migrations versus runtime | pass | Spec says migration/grants use `skiw_migrator`, web/worker `skiw_app`; M0c test gate names both roles. Runtime not tested in this spec review. | D5; §4.1; M0 | No |
| TEN-03 | Yes: mutable queue and append-only evidence | pass with owner mapping | Mapping and grant audit are explicit; queue status needs UPDATE, whereas `audit_event` and listed evidence retain no UPDATE/DELETE/TRUNCATE. | §4.1 grants; §4.2 TEN-03 row; `PROJECT.md` §9 | No |
| TEN-09/10/11 | Yes: job tenant source and temporary M0 boundary | pass (staged) | M0c permits only test probes with no tenant data; M4 enforces `with_agency`, derived agency, RLS checks and worker MAC on all production tasks. | D5 Staging; M0/M4 | No |
| EVT-01/02/05/06 | Yes: handoff, fallback, retry, schedules | pass | Sync Django-connection path, rollback/commit/visibility tests, `job_outbox` fallback, worker retry and periodic test are specified. Live proof is M0c. | D5; §4.1 grants; M0 | No |
| Project enqueue rule; UNI-04/13 | Yes: wrapper, registry and CI bans | pass | Direct defer and task decorator bans are specified with M0c/M4 test gates. | D5; M0/M4; `PROJECT.md` §9 | No |
| FE-13 | Yes: D2 token source | pass | One token location is named; visual implementation is in separate PR 4. | D2; PR body | No |
| Other ticked packs | No new implementation in this text slice | n/a | The approved v1.7 feature-complete review remains the baseline. | Round 9 | No |

### Verification performed

| Command / check | Result |
|---|---|
| `git -C .agent/worktrees/build-docs-spec-d5 hash-object` for the spec and `agents/PROJECT.md` | `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`; `66497bbcdbe64ae2425bb8de3db18acfe09451df` |
| PR 3 host metadata and CI | Open at head `07bd5bd`; `checks` passed at that head; branch worktree clean; host head re-checked unchanged. |
| `git diff --check b6abd9f...HEAD` in PR 3 worktree | Passed. |
| Compared changed spec and `PROJECT.md` with Round 10, decisions, plan and guardrails | All three Round 10 corrections re-inspected; one deferred plan mismatch remains. |
| [Procrastinate 3.10.0 schema](https://github.com/procrastinate-org/procrastinate/blob/3.10.0/procrastinate/sql/schema.sql), [queries](https://github.com/procrastinate-org/procrastinate/blob/3.10.0/procrastinate/sql/queries.sql), [worker](https://github.com/procrastinate-org/procrastinate/blob/3.10.0/procrastinate/worker.py) | Independently checked mutable job status, periodic bookkeeping, worker register/prune, query paths and default `delete_jobs=never`. The listed grants are plausible for the named paths; database execution remains an M0c gate. |

### Residual risks and test gaps
- No live Postgres, worker, UUID round-trip, grant audit or browser test was run in this text-only spec review. Procrastinate's Django migration objects and exact privileges remain assumptions until M0c proves them with the production connector and `skiw_app`.
- `skiw_app` can disrupt jobs across agencies in the shared operational queue; the spec states this limit and Q32 requires a decision before a second agency. The worker MAC protects tenant execution, not availability.
- `PROJECT.md` still records the v1.7 spec hash; `setup` Part B must reconcile it after PR 3 merges. The brand decision log update is in separate PR 4, not this spec PR. The 1.8 changelog is dated 2026-10-06 although the Round 10 fixes were added 2026-10-07; this is minor editorial drift.
- No instruction-like text directed the reviewer to skip a gate or change the verdict.

### Required before merge
- None for PR 3 at this head. Approval is of the reviewed spec and rule-mapping hashes, not implementation.

### Deferred conditions
- Update `docs/plans/2026-10-05-m0-scaffold.md` in the named M0c plan-update PR before M0c implementation begins (P2 above).
- M0c must prove the queue grant matrix, same-transaction behavior, UUID round-trip, worker lifecycle and retry under `skiw_app`; M4 must prove the full tenant-guarded helper. These are the spec's milestone gates.

### Optional improvements
- Date the Round 10 changelog addition 2026-10-07 when next editing the spec.

## Round 10 — 2026-10-07 · scope: spec-change slice (v1.8 D2/D5, PR 3)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` on PR 3 branch `docs/spec-v1.8-d5` · version 1.8 · hash (`git hash-object`) `a424c7f3f94fba3e3ec28a81ef682775b08e4163`. The main checkout still contains approved v1.7 (`cf57625da85c77d9be83995721fce9ed45907a07`).
- **Code review:** n/a; this PR changes only the spec. PR 3 base `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `1e34b75df08447b088abe5f6470aa04089c11ae0` · host head re-checked at end: yes.

**Verdict:** Blocked
**Model used:** Codex GPT-6 · **Switch model next step?** No — the builder can correct these explicit spec and review-gate gaps; M0c implementation still needs the project's deep tier.

### Findings

### [P1] M0 acceptance tests require the complete tenant-aware helper before M4 supplies its dependencies
- Category: defect
- Rule: D5; §9 M0/M4; TEN-09; TEN-11
- Evidence: v1.8 D5 (line 89) says `jobs.enqueue_in_tx` is callable only inside `with_agency()`, derives that agency, verifies `guard.current_agency()`, checks referenced rows under RLS, and signs the args. The revised M0 row (line 601) requires integration tests of that helper, including a real UUID id round-trip. The M4 row (line 605) is where `with_agency()`, `guard.current_agency()`, the guard key, RLS and tenant tables first arrive. The existing M0 plan explicitly postpones helper steps (1a)/(1b) to M4 (`docs/plans/2026-10-05-m0-scaffold.md:40`).
- Failure scenario: M0c runs `enqueue_in_tx` against its probe row before M4. A conforming implementation must refuse the call because no verified agency transaction exists; an implementation that skips the guard to pass M0 is weaker than D5 and TEN-11.
- Why it matters: the M0 gate is impossible as stated, while the existing plan silently implements a weaker interim helper.
- Required correction: define the M0c subset explicitly (transactional defer/rollback, role, UUID serialization on a probe) and its temporary calling boundary, then require the full D5 helper and wrong-agency checks at M4; or move the full helper and tenant guard into M0c. Align the M0 plan with the chosen split before M0c.
- Owner: builder
- Verification: M0c and M4 each have executable tests for exactly the behavior delivered at that milestone; no unguarded enqueue path survives M4.
- Status: open

### [P1] Queue grant scope conflicts with the append-only job-record rule
- Category: guardrail mismatch
- Rule: TEN-03; D4/D5; §4.1 Procrastinate tables
- Evidence: the new D5 and §4.1 row (lines 89 and 186) say `skiw_app` receives every table/sequence permission needed by web and worker. TEN-03 (`agents/guardrails/tenancy-rls.md:11`) forbids `UPDATE`, `DELETE` and `TRUNCATE` on job records for `skiw_app`. Procrastinate 3.10.0's [published schema](https://github.com/procrastinate-org/procrastinate/blob/3.10.0/procrastinate/sql/schema.sql) updates `procrastinate_jobs.status` when fetching/finishing/retrying jobs and has delete paths; its functions contain no `SECURITY DEFINER`. The spec neither classifies these mutable queue state tables separately from append-only records nor defines a privilege mechanism that satisfies both rules.
- Failure scenario: M0c grants `UPDATE`/`DELETE` on `procrastinate_jobs` to make the worker run, violating TEN-03; or grants only `INSERT`/`SELECT`, causing workers and admin retry to fail at runtime.
- Why it matters: the worker cannot meet the stated grant design and the project's append-only invariant without an explicit rule mapping or a different privilege architecture.
- Required correction: state which Procrastinate tables are mutable operational queue state and which, if any, are append-only evidence; reconcile TEN-03 in `agents/PROJECT.md`/the owner-approved rule mapping, or design restricted definer operations with tests. List the actual M0c table, sequence and function grants plus a worker fetch/finish/retry test as `skiw_app`.
- Owner: builder and owner for any rule exception
- Verification: under `skiw_app`, a job can be deferred, fetched, finished and retried; the grant audit proves append-only evidence tables have no UPDATE/DELETE/TRUNCATE privilege, and the rule mapping names every exception.
- Status: open

### [P1] PR 3 has no per-rule self-check table
- Category: guardrail mismatch
- Rule: `agents/roles/reviewer.md` §3
- Evidence: the PR 3 body has a summary and a “Needs reviewer attention” list, but no per-rule self-check table. The reviewer rule says a missing self-check table makes the verdict **Blocked**. Applicable rules for this slice include TEN-01/02/03/09/10/11, EVT-01/02/05/06, the project job-enqueue rule, FE-13 and UNI-04/13; the body does not map them to evidence or justified `n/a`.
- Failure scenario: the grant and milestone conflicts above pass through without a recorded builder check or explicit disposition.
- Why it matters: the required independent guardrail audit lacks its builder input.
- Required correction: add a PR 3 self-check table with one row for each applicable rule, evidence or a specific `n/a` reason. The reviewer will re-check it; the table alone will not close the two design findings.
- Owner: builder
- Verification: PR body includes the table at the same head and the reviewer can compare each row with the spec and guardrails.
- Status: open

### Self-check audit

| Rule group | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| TEN-01/02, D16 | Yes, migration/runtime role split | No table | D5 now keeps runtime on `skiw_app` from M0; migration as `skiw_migrator` is coherent | D5; §4.1; M0 | Self-check missing |
| TEN-03 | Yes, queue privileges and job records | No table; PR body calls out grant scope | Unresolved conflict above | Guardrail; D5; Procrastinate 3.10.0 schema | Yes |
| TEN-09/10/11 | Yes, helper and tenant source | No table | Full helper depends on M4; M0 staging unclear | D5; M0/M4; plan M0c | Yes |
| EVT-01/02/05/06 | Yes, transaction handoff, fallback, retry and schedules | No table | Sync defer route and rollback/visibility tests are specified; runtime proof awaits M0c | D5; M0 | Self-check missing |
| Project enqueue rule; UNI-04/13 | Yes, direct-defer ban and CI contract | No table | Ban enlarged; exact Semgrep coverage remains an M0c test | D5; M0 | Self-check missing |
| FE-13 | Yes, D2 token source | No table | D2 names one token location; UI implementation belongs to the brand-tokens PR | D2; handoff | Self-check missing |
| Other ticked packs | No new implementation in this text slice | No table | Existing v1.7 feature review remains the baseline; not re-executed | Round 9 | Self-check missing |

### Verification performed

| Command / check | Result |
|---|---|
| `git -C .agent/worktrees/build-docs-spec-d5 hash-object docs/specs/2026-10-05-skiw-platform-stack-design.md` | `a424c7f3f94fba3e3ec28a81ef682775b08e4163` |
| PR 3 host metadata and branch worktree | Open; base/head as recorded; branch worktree clean; Python CI check passed; host head re-checked unchanged |
| `git diff --check b6abd9f...HEAD` in PR 3 worktree | Passed |
| Compared v1.8 against approved v1.7, decisions, handoff, M0 plan and guardrails | D5 connector/UUID/role claims and D2 direction reviewed as a slice; findings above |
| [Procrastinate Django integration docs](https://procrastinate.readthedocs.io/en/stable/howto/django/basic_usage.html), [external-connection docs](https://procrastinate.readthedocs.io/en/main/howto/production/external_connection.html), [3.10.0 schema](https://github.com/procrastinate-org/procrastinate/blob/3.10.0/procrastinate/sql/schema.sql) | Docs support Django connection use and the connector distinction; schema confirms mutable queue state. The precise DjangoConnector implementation and UUID serializer were not independently loaded; M0c tests remain required. |

### Residual risks and test gaps
- No live Postgres, worker, UUID round-trip, browser or contrast test was run in this text-only review. The brand source site timed out when opened; the colour choice is recorded in the handoff but its website provenance was not independently verified.
- The M0 plan still names the old external-connection decision and postpones queue grants to M4. Its update is explicitly scheduled after spec approval, but it must be reconciled before M0c begins.
- D2 labels the visual direction “owner, 2026-10-06” while the handoff dates the navy/gold choice 2026-10-07. The decisions log still records that colour question as open; reconcile the date and decision record in the named brand-tokens follow-up PR.
- No instruction-like text directed at the reviewer was found in the changed spec slice.

### Required before merge
- Resolve the two D5/M0/TEN-03 P1 findings in the spec and project rule mapping as needed, then request a new spec review.
- Add the PR 3 per-rule self-check table; re-review at the resulting exact head.

### Deferred conditions
- Brand decision date and decisions-log reconciliation: `feat/m0b-brand-tokens` PR after PR 2 merges.
- M0 plan rewrite and implementation tests: before M0c starts, after the revised spec is approved.

### Optional improvements
- None required beyond the findings.

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
