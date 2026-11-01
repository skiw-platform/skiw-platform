# PR 79 — feat(auth): M3b-2 crypto (AES-GCM blob, Argon2id, spec-floor bounds)

- **Merged:** 2026-11-01 (05:42:40 UTC) · **Merge commit:** d676a63347037dbd38c8fbf063e214757b16078b · **Branch:** feat/m3b-2-auth-crypto
- **Gate breaches:** **GATE BREACH: no reviewer verdict on record before the merge — unverified at merge time.** The owner merged by accident (owner's words: "i accidentally merged 79") before `review 79` and `approved 79`. The only review (Round 1, Approved) was written AFTER the merge, against the merged head.
- **Approval receipt:** missing (none written; a receipt before a merge did not exist). Post-merge review archived at reviews/PR-79.md on agent-logs.
- **Merge evidence:** `gh pr view 79` state MERGED; merge commit is an ancestor of fetched origin/main; merged head d0012587e7972c55a8814d1f230513cdf9594922 equals the head the post-merge review read.
- **Drafted by:** Claude Sonnet 5.5 (Opus sub-agent wrote the code) · **Final verdict:** Approved, post-merge only (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3b · **Milestone:** M3 auth, M3b-2

## What changed
Adds `cryptography` 50.0.2 and `argon2-cffi` 25.1.0. Adds `accounts.auth.blob` (AES-256-GCM login and credential blobs, fixed length 222 / 62) and `accounts.auth.passwords` (Argon2id verify, needs_rehash, dummy_verify). Tightens the 10 auth settings bounds so the spec or owner value is the weakest allowed value (closes PR 78 P2). 11 files, code+tests+config +446 / -23, uv.lock +119, docs +16.

## Why
Plan §3 M3b second half, and the PR 78 deferred P2.

## Review rounds
- Post-merge R1: no P0, P1 or P2. PR 78 bounds P2 confirmed fixed. One P3 (below).

## Deferred conditions
- P3: two crypto properties can be tested (version in AAD; HKDF key not raw key) → M3c, add the two tests to the blob test module.

## Decisions worth keeping
- Public API `seal_login/open_login/seal_credential/open_credential`; dummy hash built on first use.
- Fails-per-account and lock-after floors are 3 (usability).
- Mutation check on bounds: 9 killed, 1 survived (pending-login cap, no spec value).
- Trivy, gitleaks CI-only; Risk 3 numbers from arm64.

## Follow-ups
- M3c: the two tests above; blob.py docstring wording ("of each version's key").
- M3e: cap password length at the boundary (UNI-03); one normalised email passed to `guard.auth_lookup_login`; keep the structural decoy-timing test; build the dummy hash at start-up; reset `unmatched_ignore_imports_alerting`; `host_live` same-origin POST test; no-token-in-path.
- M3d: `django.request` exception text (PII risk).
- Process: merge only after `review <n>` then `approved <n>`.

## Appendix — final review round
# Review — PR #79

## Round 1 — 2026-11-01 · scope: slice (M3b-2, second half of plan §3 M3b; plan `docs/plans/2026-10-31-m3-auth.md`)
- **Code review:** base (merge base) `f8f7075bfd4c98bd95636ea61b3173e3d8a6277b` · head `d0012587e7972c55a8814d1f230513cdf9594922` · head re-checked at end: yes (GitHub; state MERGED)
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371` (unchanged by this PR)
- Review checkout: `.agent/worktrees/review-79-d0012587` (detached worktree at the head SHA). Throwaway crypto checks ran in the reviewer's scratch folder, never in the checkout.

**Verdict:** Approved (post-merge review only — see the gate breach below)
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No — M3c (limits, throttle HMACs) stays on the deep tier.

### GATE BREACH — merged before review
- GitHub: PR 79 was merged on 2026-11-01T05:42:40Z by `charliekhc`, merge commit `d676a63347037dbd38c8fbf063e214757b16078b`. The PR had 0 reviews.
- `origin/agent-logs` has no `reviews/PR-79.md`, no `reviews/PR-79.receipt` and no `log/…PR79…` file. So no reviewer verdict and no approval receipt existed at merge time.
- The builder's `merged 79` log must record: "GATE BREACH: no reviewer verdict on record — unverified". This post-merge review does not clear the breach. It only says what the merged code does.
- I checked that the merge commit tree equals the PR head tree (`git diff d0012587 d676a633` is empty). So this review covers exactly what is on `main`.

### Findings

No P0, P1 or P2 findings.

**The PR 78 P2 (bounds weaker than spec) is closed.** Each bound now has the spec or owner value as its weakest end:

| Setting | Spec or owner value | Bounds now |
|---|---|---|
| `SKIW_ARGON2_MEMORY_KIB` | T5: 64 MiB | 65536–131072 |
| `SKIW_ARGON2_TIME_COST` | T5: t=3 | 3–10 |
| `SKIW_ARGON2_PARALLELISM` | T5: p=1 | 1–8 |
| `SKIW_AUTH_FAILS_PER_ACCOUNT` | Flow 5.1: 5 | 3–5 |
| `SKIW_AUTH_FAILS_PER_IP` | Flow 5.1: 20 | 5–20 |
| `SKIW_AUTH_WINDOW_MIN` | Flow 5.1: 15 | 15–1440 |
| `SKIW_AUTH_LOCK_AFTER` | Flow 5.1: 10 | 3–10 |
| `SKIW_AUTH_LOCK_MIN` | Flow 5.1: 30 | 30–1440 |
| `SKIW_STEPUP_MAX_AGE_MIN` | T5: ≤ 5 min | 1–5 |
| `SKIW_TOTP_SKEW_STEPS` | Flow 5.1: ±1 | 0–1 |
| `SKIW_ENROL_LINK_MIN` | owner Q5 (a): 30 | 5–30 |

The new `WEAKER_THAN_SPEC` test in `app/tests/test_auth_settings.py` refuses one step past each spec end.

The crypto is sound:
- `app/accounts/auth/blob.py`: AES-256-GCM. Layout is 2-byte version ‖ 12-byte random nonce ‖ ciphertext ‖ 16-byte tag. Each version's key comes from HKDF-SHA256 with info `skiw-blob-key-v1`. The AAD binds the header, the purpose and the value kind. `_open` returns `None` on a wrong length, an unlisted version or `InvalidTag`, and logs nothing.
- `app/accounts/auth/passwords.py`: Argon2id, salt 16 bytes, hash 32 bytes, parameters from settings. `verify` catches `VerificationError` and `InvalidHashError`. `dummy_verify` and `needs_rehash` exist for M3e.
- Dependencies: `cryptography==50.0.2`, `argon2-cffi==25.1.0`, plus transitive `argon2-cffi-bindings` 26.1.0, `cffi` 2.1.1, `pycparser` 3.12. All are hash-pinned. DECISIONS records the version ladder. `make audit-python`: no known vulnerabilities.

### [P3] Two crypto properties the builder called "not visible to a test" can be tested
- Category: test gap
- Rule: UNI-04 (a control has a test that fails when the control goes away); AUTH-04 / T5
- Evidence: the PR body says that the version-in-AAD binding and the HKDF step are not visible to a test. In a throwaway script I proved both are testable:
  1. Seal under version 2 with the same raw key listed as both v1 and v2. Rewrite the 2-byte header to v1. `_open` returns `None`. So the version is in the AAD. Without the AAD binding, the rewritten blob would open, because both versions share one key.
  2. Decrypt a sealed blob with `AESGCM(raw_key)` directly (no HKDF). It raises `InvalidTag`. So the code uses the derived key, not the raw key.
- Failure scenario: a later refactor drops the header from the AAD, or passes the raw key to `AESGCM`. Every current test still passes. A blob sealed for one key version could then be relabelled, or the raw key would be used directly, against the design in DECISIONS.
- Required correction: add these two tests to the blob test module.
- Owner: builder
- Disposition: deferred to M3c (next PR that touches `app/accounts/auth/`).
- Verification: the M3c review plants each regression in a scratch copy and sees the matching test fail.
- Status: open

### Notes for M3e (no severity; the login route is not in this PR)
- **Bound the password length at the boundary (UNI-03).** `passwords.verify` hashes whatever it gets. The login schema must cap the length before it reaches Argon2.
- **Use one normalised email.** Pass the output of `normalise_email` (NFKC, strip, lower) to `guard.auth_lookup_login`, and store that same form. Do not normalise in two places.
- **Decoy timing.** A decoy blob usually has an unlisted version header, so `_open` returns before the decrypt. The time difference is microseconds, next to an Argon2 verify of tens of milliseconds. The plan's structural test (count the calls on each path) is the right check. Keep it.
- **Warm the dummy hash.** `dummy_verify` builds its dummy hash lazily on the first call. M3e must build it at start-up, or the first unknown-user login is slower than the rest.

### Notes (no severity)
- **Docstring wording.** `blob.py` says "HKDF … of the key version". It means "of each version's key". This is minor.
- **One mutation survives.** Changing the pending-login cap does not fail a test. The spec gives no value for it, so this is not a finding.
- **No text in the PR body is addressed to an AI agent.**

### Self-check audit

I read the diff and built this list before I read the PR body.

My applicability list:
- UNI-01, 02, 03, 04, 05, 06, 07, 08, 09, 13 and 16 apply: new crypto code, tightened config bounds, new dependencies, log behaviour on failure, runbooks.
- UNI-10–12, 14, 15, 17–19 are n-a: no audit event, external service, migration, header, route or web change.
- AUTH-04 applies (Argon2id parameters). Other AUTH rules are n-a until a route exists (M3e).
- TEN rules are n-a: no table or grant.
- FE rules are n-a. E2E still runs in CI.
- PROJECT §9: `LOGIN_BLOB_KEY` mount unchanged.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy: no issues in 129 files | none |
| UNI-02 | yes (bounds) | pass | pass | bounds match spec ends; `WEAKER_THAN_SPEC` test | none (PR 78 P2 closed) |
| UNI-03 | yes (blob input) | pass | pass | `_open` refuses wrong length, unlisted version, bad tag | none |
| UNI-04 | yes | pass | pass with gap | AAD binding and HKDF step lack a test | P3 |
| UNI-05 | yes | pass | pass | no dead code; `dummy_verify` reader is M3e, recorded | none |
| UNI-06 | yes (2 new deps) | pass | pass | hash-pinned; ladder in DECISIONS; `make audit-python` clean | none |
| UNI-07, 08 | yes | pass | pass | keys made per test run; added-line secret scan clean | none |
| UNI-09 | yes (failure paths) | pass | pass | `_open` and `verify` log nothing | none |
| UNI-13 | yes | pass | pass | CI run 41277238862: checks, host, image, security pass | none |
| UNI-16 | yes | pass | pass | no new runbook step needed; DECISIONS updated | none |
| AUTH-04 | yes (Argon2id) | pass | pass | Argon2id; T5 floor enforced by bounds | none |
| PROJECT §9 | yes | pass | pass | key mount unchanged | none |
| Others | n-a | n/a | n/a | — | none |

### Verification performed
| Command / check | Result |
|---|---|
| `git diff --check f8f7075...d001258` | clean |
| `git diff d0012587 d676a633` (head vs merge commit) | empty |
| `make lint` | ruff pass; 10 contracts kept; Semgrep 9 rules 0 findings; `--test` 9/9 |
| `make typecheck` | mypy: no issues in 129 files; `tsc` pass |
| `make test` | 1403 passed |
| `make host-test` | 832 passed |
| `make audit-python` | no known vulnerabilities |
| PyPI per-version check (`cryptography` 50.0.2, `argon2-cffi` 25.1.0) | versions exist on PyPI |
| Throwaway: same key as v1 and v2, header rewritten | `_open` returns `None` (version is in the AAD) |
| Throwaway: `AESGCM(raw_key).decrypt` on a sealed blob | `InvalidTag` (HKDF is used) |
| `make test-live`, `make host-test-live`, `make e2e`, Trivy | not run locally beyond the above; CI run 41277238862 on `d0012587`: checks, host, image, security pass |
| Counts vs PR body | match (1403, 832) |
| Added-line secret scan; PR body scan for agent-addressed text | clean; none |
| `origin/agent-logs` for PR 79 verdict or receipt | none found |
| Clean-up: `rm .env`, `git clean -fdX` | done |
| End: GitHub head re-read; checkout `git status --untracked-files=no` | unchanged (MERGED); clean |

### Residual risks and test gaps
- Plan Risk 3 (Argon2 memory against the 512 MiB `web` limit) is measured only on arm64. Re-check on the x86 host when the login route lands.
- Trivy runs in CI only.
- Still open from earlier rounds: PR 78 P2 (`django.request` exception text) → M3d; PR 78 no-token-in-path rule → M3e; PR 77 P3 (`warn` switch-back) → M3e.

### Required before merge
- None (already merged; see the gate breach).

### Deferred conditions
- P3 two crypto tests → M3c.

### Optional improvements
- Fix the `blob.py` docstring wording.
