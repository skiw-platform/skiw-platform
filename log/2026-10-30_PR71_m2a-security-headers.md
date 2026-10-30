# PR 71 — feat(security): CSP nonce, HSTS and frame headers (M2a)

- **Merged:** 2026-10-30T10:12:59Z (GitHub) · **Merge commit:** 2b24812ac82b7059d74efaf6e8e283d6ad51db9f · **Branch:** feat/m2a-security-headers
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-71.receipt` on agent-logs (receipt commit 22f508c7f807eda663f1f9c48b1d1856b6779f33); head 47901463 and review-file hash c25e7c03 match the final round; written 2026-10-30T10:11:34Z, before the merge
- **Merge evidence:** `gh pr view 71` state MERGED, merge commit above, merged 2026-10-30T10:12:59Z; commit is an ancestor of the fetched `origin/main`; final head SHA 47901463e54fab69a88a7d2b488db831c39b24a8 equals the reviewed SHA
- **Drafted by:** Opus sub-agent (code), Claude Sonnet 5.5 (review fixes); reviewer OpenAI Codex (GPT-5) · **Final verdict:** Approved (round 4)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 · **Plan:** docs/plans/2026-10-27-m2-headers-sessions-csrf.md · **Milestone:** M2 (M2a)

## What changed
Adds an own CSP nonce middleware (`app/shell/csp.py`) and fills `MIDDLEWARE` (Security, XFrameOptions, CSP). HSTS is one year only, with no includeSubDomains or preload (owner Q1 a). The shell is `no-store`, its script carries the nonce, and the favicon is built with a content hash. Adds the async-capable middleware test, a `check --deploy` test, the Caddy edge test (one CSP, one HSTS) and an e2e CSP listener.

## Why
Spec v1.20 section 9 M2 "Header assertion tests (UNI-17) pass", T6 policy, D26 (1).

## Review rounds
- R1: [P1] favicon bypassed the hashed-asset contract (D2) → icon bundled by Vite with a content hash, URL read from the manifest, 503 if missing, verifier and content-change test.
- R2: [P2] DECISIONS Scope line named the deleted icon path → corrected.
- R3: same P2 still open (no new commit yet).
- R4: Approved.

## Deferred conditions
none

## Decisions worth keeping
- Owner chose (c) for security.W009 on 2026-10-30: accepted, because `config.env` enforces 32 random bytes (`MIN_KEY_BYTES`); two tests pin the accepted warning and the byte check.
- `security.W003` is allowed in `test_deploy_checks.py` until M2d adds CSRF and removes it.
- All `/assets/` files stay hashed; the icon is `web/src/icon.svg`.
- Docker works on the owner's Mac, but a sub-agent's sandbox could not reach the socket; run `test-live`, `host-test-live` and `e2e` outside that sandbox (local worktree `.env` uses port 5434).

## Follow-ups
- Build M2b next (hashed session store, lifetime settings, M2b plan about 420 lines).
- Safari and Firefox are unverified; the real host is M1k.
- T6 "+ preload" wording fixed at the next spec change.

## Appendix — final review round

## Round 4 — 2026-10-30 · scope: slice
- **Code review:** base (merge base) `f4b9b6be6fde83754816c71ac22fd50334a8e707` · head `47901463e54fab69a88a7d2b488db831c39b24a8` · head re-checked at end: yes
- **Governing spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash `92841ba555e9e857ac70e86a5b043cf9729ed371`

**Verdict:** Approved
**Model used:** OpenAI Codex (GPT-5) · **Switch model next step?** No — the next step is the builder's mechanical approval/archive gate; no further security-review reasoning is required.

### Findings

No open findings.

### [P2] The durable decision record still names the deleted icon path — resolved
- Category: defect
- Rule: `PROJECT.md` §2 decisions-log source of truth
- Evidence: commit `47901463e54fab69a88a7d2b488db831c39b24a8` changes only `docs/DECISIONS.md`; the M2a Scope / affects line now names `web/src/icon.svg`, `web/src/icon-hash.test.tsx`, `app/shell/verify_dist.py`, and `app/shell/tests/test_verify_dist.py`, and no longer names deleted `web/public/assets/icon.svg`.
- Failure scenario: resolved; the durable record now points maintainers to the implemented icon contract and all enforcement files.
- Why it matters: the decisions log and effective code surface are consistent again.
- Required correction: completed.
- Owner: builder
- Verification: one-file fix diff inspected against the full `merge-base...head` file list; stale path absent.
- Disposition: before merge
- Status: resolved

### Self-check audit

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| Decisions log source-of-truth integrity | yes — Round 2 P2 correction | fixed in dedicated commit | pass | corrected Scope / affects line matches the implementation/test surface | no |
| Spec D2 / FE-34 | yes — hashed icon contract | pass | pass | Round 2 exact-head build/manifest/content-change verification; unchanged code | no |
| Spec T6 / M2 / D26(1), UNI-01/04-08/13/17, FE-50/61/70, PROJECT §9 | yes — M2a security slice | pass | pass | Round 2 local verification plus full green CI on the new head | no |
| UNI-02/03/09-12/14-16/18-19; other FE/A11Y rules; AUTH/TEN/MON/REC/FILE/EVT | n/a | n/a/grouped n/a | n/a | effective diff inspected | no |

### Verification performed

| Command / check | Result |
|---|---|
| `git fetch origin`; GitHub PR metadata | open/non-draft; base `f4b9b6b…`, head `4790146…`; merge base equals base |
| Round 3 → Round 4 diff | exactly one file and one line changed: `docs/DECISIONS.md`; correction matches the required outcome |
| Full three-dot file inventory | corrected Scope / affects line covers the M2a implementation, icon, verifier and test surface; deleted icon path is absent |
| `git diff --check` | pass |
| Exact-head snapshot | `git archive` file list matched `git ls-tree`; every original fingerprint unchanged at end |
| GitHub Actions run `41036182829` | success on `4790146…`; checks, security, image and host jobs all green; publish/deploy correctly skipped for a PR |
| Prompt-injection scan | no agent-addressed gate-skipping text in the correction |
| Final host re-check | PR head remains `4790146…`, open and non-draft; required jobs remain green |

### Residual risks and test gaps
- Browser behavior is verified in Chromium only; Safari and Firefox remain unverified.
- The real Hostinger staging/production host remains outside this slice and deferred to M1k.
- The owner-approved HSTS policy intentionally omits `includeSubDomains` and preload until the next spec revision fixes T6 wording.

### Required before merge
- No code or documentation corrections. The builder must run `approved 71` to archive this exact-head review before Ying merges.

### Deferred conditions
- None.

### Optional improvements
- None.

### Handoff block (only when handing off)
<!-- roles/reviewer.md §10 -->
