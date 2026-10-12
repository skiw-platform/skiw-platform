# PR 22 — docs(spec): v1.18 host on an iCore Malaysian VPS

- **Merged:** 2026-10-12T11:18:06Z (GitHub) · **Merge commit:** `720ed0bed8d20edd5a8fc1ccf701818c8c0273f2` · **Branch:** `docs/spec-v1.14-icore-hosting` (final head `3c7ecf56efed49876fdba8574c5d7bc0f38d17cf`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-22.receipt` on `agent-logs` (written 2026-10-12T09:21:45Z, before the merge); names head `3c7ecf5…` and review-file hash `28bd38ca0f7439d83d6105ae4221c8bec5dcec47`; records CI green on that exact head (run 38227849967). The archived review `reviews/SPEC-2026-10-05-skiw-platform-stack-design.md` has the same hash. PR 22 is a spec PR, so its reviewer record is the spec review file (as for PRs 3, 19 and 21).
- **Merge evidence:** `gh pr view 22` → state MERGED, mergedAt 2026-10-12T11:18:06Z, merge commit `720ed0b`, final head `3c7ecf5` (equals the reviewed head of Round 21); `git merge-base --is-ancestor 720ed0b origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder; spec text by an Opus subagent, deep tier) · **Final verdict:** Approved (spec review round 21; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` (was v1.13 `e3141585…`) · **Milestone:** hosting adoption (no feature milestone). `agents/PROJECT.md` is still reconciled to v1.13 until `setup` Part B runs.

## What changed
The platform spec now hosts SKIW on one Malaysian VPS from iCore Technology Sdn. Bhd. instead of AWS. New section 8.4 (H1 to H14): Docker Compose (Caddy, one web, worker, migrate, Postgres 17, ClamAV, a separate `backup` ops service); firewall and SSH hardening; pull-based deploy with a forced-command `skiw-deploy`, pre-migration dump, readiness check, automatic rollback and an accepted-digest record for manual rollback; host secret files with escrowed key versions; files on a VPS volume with atomic publication after scan; backups as encrypted dumps plus a files archive pulled off the host, taken as one consistent cut by a read-only backup coordinator; an independent anchor witness and owner-signed restore-transition records; a complete-recovery drill. New tables `file_tombstone` (mutable cleanup metadata) and document columns for sizes and hashes; new threats T23 to T25; five gates before real data (G-VENDOR, G-S1, G-DRILL, G-LOAD, G-BACKUP). The old AWS design is Appendix C and the documented upgrade path. `docs/DECISIONS.md` has the entry "2026-10-12 — Hosting: iCore Malaysian VPS".

## Why
Owner decision 2026-10-12 ("go with icore") after the reviewed hosting paper (PR 21): AWS Step 1 (about US$245 a month) was too costly. Owner answers: operator is the owner; one web instance; no database standby in v1; AI chat and Google Drive routes decided later (G-AI and G-DRIVE stay locked, no AWS account); Q42 owner-held production deploy key outside GitHub, on GitHub Free.

## Review rounds
- R17 (Revision required): [P1] self-check omitted FILE-01/02, UNI-17, UNI-15 and others → rule mapping H14. [P1] clean-file existence was not a safe completion marker → temp file, atomic rename, size and SHA-256 binding, advisory lock. [P2] recovery set ordering → keys before migrate, manifest, dependent retention. [P2] manual rollback vs staging digest → accepted-digest record. [P3] reviewer-directed wording removed.
- R18 (Revision required): [P1] restore epochs needed authorization independent of the production host → owner-signed restore-transition record checked by the witness. [P2] archive-after-dump was not a consistent cut → one snapshot, file list from it, soft-delete hold.
- R19 (Revision required): [P1] new tenant table `file_tombstone` lacked TEN-04 to 08 evidence → rule row and tests. [P2] ops allow-list said only `pg_dump` → bounded backup coordinator with a fixed statement list.
- R20 (Revision required): [P2] tombstone update trigger conflicted with its FK action → the trigger permits the one-time purge mark and `document_id` to NULL.
- R21: Approved.

## Deferred conditions
- none introduced. All real-data gates (G-VENDOR, G-S1, G-DRILL, G-LOAD, G-BACKUP) are mandatory spec requirements. The hosting paper's A2 ALB-ingress note is inapplicable to the iCore route.

## Decisions worth keeping
- All recorded in `docs/DECISIONS.md` (entry 2026-10-12). Still open (owner-open values): Q34 backup cadence and retention, Q35 key custody including the restore-authorization signing key, Q36 off-site copy location, Q37 R2 only after the PDPA adviser, Q38 iCore vendor gate results, Q39 AI route, Q40 Drive route, Q41 maintenance window and password rotation. Q42 is decided.
- Cloudflare R2 has no Malaysia guarantee (verified 2026-10-12): an R2 copy is cross-border and needs the PDPA process.
- The backup schedule runs in a dedicated `backup` ops service, not the app worker, so the app never holds the BYPASSRLS backup credential (TEN-02).
- GitHub Free has no required-reviewer approval for private repositories; the production deploy key stays with the owner outside GitHub.

## Follow-ups
- Builder: `setup` Part B reconcile of `agents/PROJECT.md` (sections 1, 3, 7, 8, 9, 10, 11 and the secret-scan pattern with `field_kek`, `blind_index_key`, `crm_jar_kek`), then the M1 plan (VPS infrastructure, deploy automation, host hardening and the vendor gate).
- Owner: answer Q34 to Q41 before the gates they feed; run the iCore vendor check (G-VENDOR); `brew install gitleaks` then `make hooks`; decide the kit change for the explicit green-CI check.
- Parked: UI kit decision, API Anything / FAME spike, `skiw-old` look reference. Local branch `docs/spec-v1.14-icore-hosting` and worktree `.agent/worktrees/spec-v1.14` remain until the owner says yes to delete.

## Appendix — final review round
## Round 21 — 2026-10-12 · scope: spec-change slice (v1.18 iCore adoption final correction, PR 22)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md · v1.18 · hash 0edfb3cdc514e1d5bbd3ae3d34875cd16c037644.
- **Pinned PR:** base 896eb4cf519a2fbdf573d349d0ce98a85b273521 · head 3c7ecf56efed49876fdba8574c5d7bc0f38d17cf · final host head unchanged, OPEN.
- **Mode:** exact snapshot .agent/worktrees/review-spec-v118-3c7ecf56; tracked-file hashes verified; own snapshot removed. Reviewer edited no source/spec/decision/handoff.
- Approval is for the iCore adoption design. No real-data hosting, deployment, restore or feature implementation is approved by this slice.

### Findings
None. No open or accepted-risk P0/P1 finding and no P2 before-merge correction. Round 20's remaining P2 is resolved; prior correction audits remain applicable.

#
