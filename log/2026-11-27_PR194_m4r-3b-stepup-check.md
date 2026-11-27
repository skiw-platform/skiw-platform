# PR 194 — feat(auth): M4r-3b wrapper step-up check with the catalogue's purposes

- **Merged:** 2026-11-27T00:43:49Z · **Merge commit:** b557f7d6ab3dfd6c91ef3ffdbb9acc8d9f89e177 · **Branch:** feat/m4r-3b-stepup-check
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-194.receipt (commit 5356d74, 2026-11-27T00:43:16Z, before the merge; head 09566c328b0d62f4125cbf438c824b975150e471, review-file hash 1b9f4b1e209ed7ff29ff34cce31fed6a6757be4a)
- **Merge evidence:** `gh pr view 194` state MERGED with that merge commit and date; the commit is reachable from the fetched origin/main and its second parent is the final head 09566c3, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent for the implementation · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-3 · **Milestone:** M4 (M4r-3b)

## What changed
Step 3 of `authorized_action` now keeps a grant that needs a step-up while `stepup.recent()` finds this session's evidence for that grant's purpose, read once per distinct purpose on every request; with nothing kept the answer is 403 `stepup-required`. `stepup.PURPOSES` is `factor.change` plus the catalogue's seven step-up purposes, so the step-up routes accept them. No migration, grant or new live route. 166 added lines, 40 removed.

## Why
Slice spec v2.5 Decisions 4, 7 (iv) and 34 (c), flow 5.1 and the §7 row "S action without fresh re-verification"; AUTH-09. It replaces M4r-3a's refusal of every step-up grant.

## Review rounds
- R1: Approved, no findings

## Deferred conditions
none

## Decisions worth keeping
Owner answers of 2026-11-26 applied here: three PRs for M4r-3 and all seven catalogue purposes at once. Readings, consequences and limits are in docs/DECISIONS.md, "2026-11-27 — M4r-3b". PR CI run 45917051017 on 09566c3 passed (2084 unit, 254 web, 2042 live database, 60 end-to-end).

## Follow-ups
- M4r-3c next (rename invariance and extra order cases, tests only).
- The wrapper now reaches `webauthn` through `stepup`; the first module outside `accounts` that imports `authorized_action` will break an import contract.
- Step-up evidence from a passkey or TOTP removed afterwards still counts until it is the configured maximum age old (unchanged behaviour).
- Builder mutant that survived: purposes collected from all held grants after the line refusal only adds a step-up read. The reviewer covered the mixed-line read count with a local probe; no committed test does. The reviewer did not repeat the mutation runs.
- CI on `main`: image paths still name `ghcr.io/skiw-dev1` (see the PR 193 log); their own deploy-path PR is not made.

## Appendix — final review round

## Round 1 — 2026-11-27 · scope: slice

- **Code review:** base and merge base `d18862ff26a7d5ac9e72c700194e7a97a780431c` · head `09566c328b0d62f4125cbf438c824b975150e471` · head rechecked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`), D7 and D25, and M4-rest v2.5 (`bb262ec4`), Decisions 4, 6–8, 26 and 34, §6.1, §7 and §9 row 3. Scope is the owner-approved M4r-3b split and catalogue purpose expansion.
- **Diff:** 10 files, +166/−40, one commit.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the archive and receipt.

### Findings

No open findings.

- `app/accounts/auth/wrapper.py:129`–`:140` checks the line before looking up proof and retains only the grants whose own purpose has fresh evidence, plus grants that require none. Lines 215–222 place that check before input validation. A user with an own-device grant retains only that grant when agency-wide proof is missing.
- `app/accounts/auth/stepup.py:56`–`:62` derives the seven new purposes from the catalogue and keeps `factor.change`. Both route schemas use that closed set. The existing proof lookup at lines 161–183 checks user, session, purpose, age and MAC within the bound tenant transaction.

### Self-check audit

| Rule | Applicability | Review |
|---|---|---|
| UNI-01–05 | Types, configurable age, request schemas, module boundaries and reuse | Exact-head typecheck and lint passed. Both real route schemas accepted the eight approved purposes and refused unlisted and malformed values in the local probe. The wrapper reuses the existing evidence function. |
| UNI-07, UNI-09, UNI-13 | Secret hygiene, security warning, required CI | Added-line scan and CI full-history secret scan were clean. The evidence warning carries no purpose, session, key or row value. All required jobs passed. |
| UNI-16 | Auth runbook | Local-dev line 53 explains per-grant proof, the refusal codes, both re-verification methods and the focused live test. |
| AUTH-01–03, AUTH-06, AUTH-09, AUTH-12 | Action order, role and line matching, persistent attempt budget, fresh proof, request-time refresh | Source, independent probes and exact-head CI agree. The TOTP-backed wrapper tests cover all 11 step-up pairs. Live passkey route tests cover all eight accepted purposes. Existing throttle and lock semantics remain in their shared verification code. |
| TEN-09–11 | Bound tenant transaction and server session | The role and proof reads run within the wrapper's tenant transaction. The proof lookup uses the MAC-checked session, and the queried evidence is constrained to its user, stored session key and purpose. No schema or grants change. |

### Verification performed

| Check | Result |
|---|---|
| GitHub pin, commit and merge base, effective diff and end-of-round pin | Matched. Removed the detached checkout after confirming it was clean. |
| `git diff --check` and added-line secret-pattern scan | Clean. No prompt-injection text found in the diff or PR body. |
| Focused wrapper, proof, route-registry and CSRF tests | 324 passed in an offline, resource-limited container with read-only source and dummy settings. |
| Independent wrapper probe | Eight cases passed with stubbed grant and proof reads. Confirmed own-only access without proof, agency scope with matching proof, wrong-purpose refusal, no proof read for an off-line grant mixed with a valid grant, and deduplication by purpose. |
| Independent request-schema probe | 22 cases passed using the actual TOTP and passkey validators and unmodified purpose list. |
| GitHub Actions run 45917051017 | All four required jobs passed on this exact head, including strict typecheck, 24/24 Semgrep rule fixtures, 2,084 Python unit tests, 254 web unit tests, 2,042 live database tests, the tenancy schema check and 60 end-to-end tests. The wrapper role file passed 17 live cases and the passkey step-up file passed 25. Publish and staging deployment skipped. |

### Residual risks and test gaps

- Live database and browser checks were verified through exact-head CI. The mutation runs were not independently repeated. The mixed-line read-count case that survived a builder mutation was verified by the local wrapper probe.
- The first non-accounts import of the wrapper requires resolving the documented transitive WebAuthn contract. The import contract passes on this head and no live route uses a catalogue permission yet.
- Rename invariance and additional ordering tests belong to the approved 3c split.

### Required before merge

- Archive this round and record the review receipt for the exact reviewed head.

### Deferred conditions

- None.
