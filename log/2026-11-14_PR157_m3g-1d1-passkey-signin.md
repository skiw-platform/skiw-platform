# PR 157 — feat(accounts): M3g-1d-1 sign in with a passkey

- **Merged:** 2026-11-14 (06:55:43 UTC) · **Merge commit:** 95185a824f431567f9fb8221c27eba41f61cfad3 · **Branch:** feat/m3g-1d-signin (final head 046fe6cf87b84e319b649e30adf435a1794de7ad)
- **Gate breaches:** none. The final round (R2) head SHA equals the PR's final head; the receipt (2026-11-14T06:51:54Z, review-file hash 7392224d, log-branch commit 0d0e46d) precedes the merge by 3 minutes 49 seconds.
- **Approval receipt:** `reviews/PR-157.receipt` on agent-logs (review at commit 0d0e46d).
- **Merge evidence:** `gh pr view 157` (skiw-platform/skiw-platform) state MERGED, mergedAt 2026-11-14T06:55:43Z, merge commit 95185a8; reachable from fetched origin/main.
- **Drafted by:** a deep-tier (Opus) sub-agent for the design and code, Sonnet 5.5 for the gates, mutant re-runs and PR body; the Round 1 fix commit (046fe6c) was made outside the session that wrote this log · **Reviewed by:** Codex (GPT-5), deep review (two rounds) · **Final verdict:** Approved with conditions (round 2)
- **Spec:** v1.22 (unchanged) · **Plan:** M3 §1 M3g row, amended 2026-11-13 · **Milestone:** M3, package M3g (fifth server PR, 1d-1)
- **Repository:** now `skiw-platform/skiw-platform` (moved back from skiw-dev1 on 2026-11-13); owner rule: public while a PR is open, private once merged. Made public at PR open, private again at this merge.

## What changed
`POST /api/auth/second-factor/passkey` begin and confirm: a passkey as the second factor. Begin answers 409 `no-passkey` for a user without one (owner choice). Confirm takes the single-use `login` challenge, checks the id bound, discovers the credential owner through `guard.auth_lookup_credential` and compares user and agency with the pending session, verifies against the stored key, then makes one conditional update of `sign_count` and `last_challenge_at` (strict `<`). Wrong assertions share the TOTP budget and the 30-minute lock. R1 fix: discovery runs after the reservation, in autocommit, outside the tenant transaction (`assertion.discover`, then `match` inside `with_agency`), so the lookup event survives a tenant rollback. +768/−9 over 10 files (over the 600 rule; the owner chose the split and knew sign-in alone would still exceed 600).

## Why
Plan M3g and owner Q8: optional passkeys on top of TOTP. Closes PR 154 R1 P2 #2 (stale-save replay) for sign-in with a live test.

## Review rounds
- R1 (Revision required): [P1] credential discovery inside the tenant transaction → `counted` reserves first, `assertion.discover` runs in autocommit, then `with_agency`; a live fault test shows the lookup event survives tenant rollback. [P1] incomplete self-check → PR body enumerates UNI, AUTH, TEN and project rows. [P1] exact-head CI did not run → run 43466791644 green on the fix head. [P2] stale repository remote → `PROJECT.md`, origin, PR and repo name `skiw-platform/skiw-platform`. [P3] reviewer-directed PR prose removed; [P3] the PR body's begin route name corrected.
- R2: Approved with conditions; one deferred P2.

## Deferred conditions
- P2 (assertion reuse contract) → **M3g-1d-2**: remove the stale "`match` is the whole check" wording (module header, DECISIONS) and make discovery-plus-verification the reusable API (a helper or typed discovery result). Step-up tests must prove reservation/lock → autocommit discovery and owner comparison → tenant verification, no lookup past the budget, and event durability on a later tenant fault. Direct reuse of `match` without discovery must not be the supported path.

## Decisions worth keeping
- Pre-tenant discovery and tenant verification are separate steps; the lookup event commits whatever happens next (supersedes the builder's [A] that the lookup ran inside `counted`).
- 409 `no-passkey` is a distinct answer; a passkey satisfies every step-up purpose (owner, 2026-11-13).
- Issue-time comparison fails closed across sessions.

## Follow-ups
- M3g-1d-2 (step-up with a passkey, deep tier): the saved patch (`.agent/stash/stepup-part.patch`, +358/−48) predates the R1 fix and must be reworked against `assertion.discover` and `match`; carries the deferred P2.
- Then M3g-2 (screens, e2e, one challenge per session, passkey label or created time), the M3 gate review, and an image-path PR moving `ghcr.io/skiw-dev1` back to `skiw-platform`.
- Carried: owner checks (`ghcr_read_token`; fix the G9 hostname before the first passkey; main checkout `.env`); PR 152 conditions; older P3s; 13 open Dependabot PRs in the repo.

## Appendix — final review round
## Round 2 — 2026-11-14 · scope: slice
- **Code review:** base (merge base) `ea9313052b157398199a0591424e28881f0270d5` · head `046fe6cf87b84e319b649e30adf435a1794de7ad` · head re-checked at end: yes
- **Spec review:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.22 · hash (`git hash-object`) `79a9a40ee1a686ae1082e8d11a73b299deb66d38`

**Verdict:** Approved with conditions
**Model used:** Codex (GPT-5), deep review · **Switch model next step?** Yes — M3g-1d-2 adds passkey step-up on this split security API and should use the project's deep tier.

### Findings

### [P2] The reusable assertion contract still describes `match` as the whole security check
- Category: material risk
- Rule: UNI-05; plan M3g assertion contract
- Evidence: the R1 fix correctly split pre-tenant owner discovery from tenant verification, but the module header still says “`match` is the whole check of an assertion” and that step-up can reuse it (`app/accounts/auth/assertion.py:1-3`). The durable split decision likewise says M3g-1d-2 is built on `assertion.match` (`docs/DECISIONS.md:1463`). In reality, the owner comparison and committed `passkey.lookup` event now live in `assertion.discover` and the `counted(..., precheck=...)` orchestration (`app/accounts/auth/assertion.py:79-105`); `match` alone only performs tenant-row/key verification (`:108-130`). Its function docstring correctly says discovery must already have passed, so the module exposes contradictory contracts.
- Failure scenario: M3g-1d-2 follows the module header or split decision and calls `match` through `counted` without the discovery precheck. Step-up assertions then omit the required definer lookup, both-owner comparison, and durable lookup event even though sign-in is correct.
- Why it matters: this is a security-sensitive reuse seam for the immediately following PR. It does not break the current sign-in route, which pairs discovery and match correctly.
- Required correction: in M3g-1d-2, remove the stale “whole check”/“built on match” wording and make the safe discovery-plus-verification pairing the reusable API contract (for example, an assertion-specific orchestration helper or a typed discovery result consumed by verification). Its step-up tests must prove reservation/lock → autocommit discovery/owner comparison → tenant verification, no lookup past the budget, and event durability on a later tenant fault.
- Owner: builder
- Verification: review M3g-1d-2's API, decisions entry, and live step-up tests; direct reuse of `match` without successful discovery must not be the supported path.
- Disposition (P2 only): deferred to M3g-1d-2
- Status: open

#
