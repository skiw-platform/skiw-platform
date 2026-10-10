# PR 19 — docs(spec): v1.13 worker enqueue on DjangoConnector, per-agency fan-out (M4)

- **Merged:** 2026-10-10T09:43:34Z (GitHub) · **Merge commit:** `e84f929a8cac52437d63030ead02ca35b28cb63b` · **Branch:** `docs/spec-v1.9-worker-enqueue` (final head `dfc67f1489549f757e01dc8415af6982450e193a`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-19.receipt` on `agent-logs` (written 2026-10-10T09:42:02Z, 92 seconds before the merge); names head `dfc67f1…` and review-file hash `27b0e6f6cfe8b0d9496af8a77290f8e659cd979f`; records CI (checks, image, infra, security) green on that exact head (run 38041986760). The archived review `reviews/SPEC-2026-10-05-skiw-platform-stack-design.md` has the same hash. PR 19 is a spec PR, so its reviewer record is the spec review file (as for PR 3).
- **Merge evidence:** `gh pr view 19` → state MERGED, mergedAt 2026-10-10T09:43:34Z, merge commit `e84f929`, final head `dfc67f1` (equals the reviewed head of Round 16); `git merge-base --is-ancestor e84f929 origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder; spec text by Opus subagents, deep tier) · **Final verdict:** Approved (spec review round 16; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.13, hash `e314158562214a9173e7fdbd7ec6f2a8d9355dd9` (was v1.8 `67e36a52…`) · **Milestone:** M4 prerequisite (design only)

## What changed
Spec v1.8 to v1.13 and a `docs/DECISIONS.md` entry. `manage.py runworker` is the only worker entrypoint and keeps the `DjangoConnector` (no swap to `PsycopgConnector`), so a sync handler enqueues in its own `with_agency()` transaction. Periodic per-agency fan-out uses one `with_agency(a)` transaction per deployment agency and an insert-only `job_fanout` marker (kept for the tick lifetime; v1 deletes none). Periodic system tasks are the one unsigned job kind (allow-listed name, exact timestamp args, cron-aligned, replay window). No automatic stalled-job recovery: a read-only report (M4) and a manual, audited operator release after confirmed termination (M5). Normal owned retry stays.

## Why
Closes the M4 design prerequisite from PR 8 review R2 P2 (owner decision 2026-10-10, option A). Procrastinate 3.10.0 `procrastinate worker` swaps the app connector, which broke same-transaction handler-side enqueue and per-agency fan-out.

## Review rounds
- R12 (Revision required): [P1] unsigned periodic parent contradicted the MAC boundary → two task kinds, admission contract, residual capability documented. [P1] self-check omitted UNI-04/UNI-13 → gates named in M4, PR table extended. [P2] fan-out marker lifetime → kept for tick lifetime. [P2] shutdown bound → detection and exit separated, watchdog.
- R13 (Revision required): [P1] stalled recovery inferred process death from heartbeat age/NULL worker → automatic recovery removed; report plus manual release.
- R14 (Revision required): [P2] retry prohibition too broad → normal owned retry kept; [P2] PR body stale → rewritten.
- R15 (Blocked): no technical finding; blocked on the owner's recorded decisions only.
- R16: Approved (no findings) after the owner answered Q33a, Q33b and Q2/Q32 (yes to all).

## Deferred conditions
- none introduced. Standing: M4/M5 implementation proof (connector, fan-out, shutdown, report, release and upgrade-gate tests); second-agency provenance gate for periodic parents; Q2/Q32 remaining sub-questions (queue isolation, retention); M1 production secret manager and TLS flag validation; M2 CSP nonce.

## Decisions worth keeping
- All recorded in `docs/DECISIONS.md` entry 2026-10-10 "M4 worker enqueue": DjangoConnector worker accepted despite the upstream warning (mitigation: M4 tests and the UNI-13 Procrastinate/asgiref upgrade gate); up to 5 s polling delay for a healthy idle worker; single-agency unsigned periodic-parent exception with a second-agency gate; no automatic stalled-job recovery.
- Manual stalled release rests on a truthful operator confirmation of termination, because `finish_job_v1` does not fence by worker or attempt.

## Follow-ups
- Builder: `setup` Part B reconcile (`agents/PROJECT.md` spec hash to `e314158562214a9173e7fdbd7ec6f2a8d9355dd9`, section 9 `job_fanout`); the M4 implementation PR must also fix plan `docs/plans/2026-10-05-m0-scaffold.md` line 164, the `docs/DECISIONS.md` 2026-10-09 "unresolved" wording and `app/jobs/management/commands/runworker.py`.
- Owner: `brew install gitleaks` then `make hooks`; decide the kit change for the explicit green-CI check.
- Next: M1 infrastructure plan (needs AWS account and budget answers). Parked: UI kit decision, API Anything / FAME spike, `skiw-old` look reference.

## Appendix — final review round
## Round 16 — 2026-10-10 · scope: spec-change slice (v1.13 worker enqueue/recovery, PR 19)
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.13 · hash `e314158562214a9173e7fdbd7ec6f2a8d9355dd9`.
- **Pinned PR:** base `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · head `dfc67f1489549f757e01dc8415af6982450e193a` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-v113-dfc67f14`; all 110 tracked files hash-verified against the pinned tree, snapshot removed. No source/spec/decision/handoff edits by reviewer.

### Findings
None. No open or accepted-risk P0/P1 finding and no P2 before-merge correction. Round 15's essential owner-choice evidence is now recorded; the v1.12 technical design remains intact.

#
