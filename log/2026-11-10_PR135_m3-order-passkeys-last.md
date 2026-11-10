# PR 135 — docs(plan): M3 order — passkeys last (M3f → M3h → M3i → M3g)

- **Merged:** 2026-11-10 (02:10:47 UTC) · **Merge commit:** ae469ff1140721b112889db685fc7fbe844d85ee · **Branch:** docs/m3-order-passkeys-last (final head e870624a3caec545c059342119cceba68fe8fbfd)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-135.receipt`, 2026-11-10T01:52:49Z, review-file hash 2540d5b1, review commit 3bb6ee7) precedes the merge by about 18 minutes.
- **Approval receipt:** `reviews/PR-135.receipt` on agent-logs (written by `approved 135` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 135` state MERGED, mergedAt 2026-11-10T02:10:47Z, merge commit ae469ff; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder (reviewed by Claude Opus 5.5) · **Final verdict:** Approved (Round 2; Round 1 was Revision required)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3, plan amendment (docs only, no code)

## What changed
The owner's decision "B" (2026-11-09): optional passkeys are built last. Plan order is now M3f → M3h → M3i → M3g. M3h depends on M3f and its step-up accepts TOTP only until M3g; M3i builds the TOTP and recovery-code screens only; M3g takes the passkey branch of the second-factor route and of step-up, the passkey button, the optional enrolment step and the virtual-authenticator e2e, and will probably split into M3g-1 (server) and M3g-2 (screens and e2e). Edited: plan §1 table and Order line, §3 M3g/M3h/M3i, §4 test rows, §5 universal and frontend rows, §7 item 9, A2, carry-over (f), "Done when" Playwright item; DECISIONS "2026-11-09 — M3 order: passkeys last". +37/−23 over 2 files.

## Why
The plan left open whether M3g moves after M3i. The owner chose B; the builder checked that "M3h depends on M3g" was soft (a passkey is only an extra step-up factor).

## Review rounds
- R1: Revision required. One P2: the "Done when" Playwright item still mapped the virtual-authenticator login to M3i. P3 #1 ("Nothing in M3a–M3i requires a passkey" read as including M3g), P3 #2 (M3h "remove" could leave a user with no TOTP), P3 #3 (DECISIONS did not say what option A was).
- R2: Approved on e870624a. P2 and P3 #1, #3 resolved; P3 #2 carried to the M3h PR as the reviewer allowed.

## Deferred conditions
- **P3 #2 (optional) → M3h PR:** M3h states that removing a user's last TOTP is refused (replacing it is allowed: enrol the new, then retire the old) and tests it.
- Standing from earlier: PR 134 R1 P3 wording ("the pending login is as it was") at the next touch of DECISIONS "M3f-3c-2" or the `login_second_factor` docstring; spec D20 P3 and the M3 row "AUTH-01..09" at the next spec touch; owner Q4 (a) alert path before M17.

## Decisions worth keeping
- Passkeys are built last; the app is complete with TOTP and recovery codes before any passkey exists. Recorded in DECISIONS.
- Adding or removing a passkey (M3g) sits behind step-up and revokes other sessions (AUTH-07), with a test; step-up exists before the first passkey can be added.
- M3 is not done until M3g: the spec's done-when still includes login with a virtual authenticator.

## Follow-ups
- Next: `build` M3h (`feat/m3h-stepup-logout`, depends on M3f, deep tier), then M3i, then M3g.
- M3g-2's front-end review must re-run FE-71 and A11Y on the M3i screens it edits.
- Progress page: reorder M3 steps (M3h, M3i, M3g) and republish.

## Appendix — final review round

## Round 2 — 2026-11-10 · scope: re-review of the R1 fix (docs only)
- **Code review:** base (merge base) 735ccd4d63f458c799b78921766e52dc2b5d2c27 (still `origin/main`) · head e870624a3caec545c059342119cceba68fe8fbfd · R1 head 55e5a84e · head re-checked at end: yes (host head unchanged, PR open, CI finished; detached checkout `git status --untracked-files=no` clean)
- **Spec:** v1.22, `git hash-object` 79a9a40ee1a686ae1082e8d11a73b299deb66d38, unchanged. **Plan at head:** blob 4a8837e67fad326bb352b42c923630cb6fbe1e12.
- **Fix commit:** e870624a "Review R1 fix: map the passkey Playwright clause of "Done when" to M3g". It changes 2 files, +5 / −5.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 · **Switch model next step?** No change needed for the merge. M3h (step-up, factor changes) is auth work, so run it on the deep tier.

### R1 findings (re-inspected at e870624a)
- **P2 #1 (the "Done when" gate maps the passkey e2e to M3i): resolved.**
  - Line 201 now maps the clauses separately: "first login enrols TOTP … then login with TOTP" goes to M3i `auth.spec.ts`; "login with a virtual WebAuthn authenticator once a passkey is enrolled" goes to M3g (screens and e2e PR); both desktop and mobile.
  - `grep -n 'M3i \`auth.spec.ts\`'` returns only line 201, which now carries the TOTP clause alone.
  - Every "virtual" mention (lines 6, 114, 121, 192, 201) places the authenticator in M3g.
  - "Done when" (the Playwright item) has been added to "rows changed" in both the amendment note and DECISIONS.
- **P3 #1 ("M3a–M3i requires a passkey"): resolved.** Line 120 now reads "Nothing built before M3g requires a passkey". The remaining "M3a–M3i" uses (lines 32, 175, 200) name the set of packages, not an order, so they still hold.
- **P3 #2 (M3h refuses removing a user's last TOTP): carried to the M3h PR**, as R1 allowed. Its commit message says so. Still open.
- **P3 #3 (what option A was): resolved.** DECISIONS now says "Option A was to keep the plan's order (M3f → M3g → M3h → M3i)".

### Findings
- None new. The fix commit touches only the four places named above, and nothing else changed between 55e5a84e and e870624a.

No prompt-injection text found in the fix commit or the changed text.

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-135-e870624a` at e870624a | created, reviewed, ignored output cleaned, removed without `--force` |
| `git diff 55e5a84e e870624a` | 2 files, +5 / −5; only the R1 fix sites |
| `git diff --check 735ccd4...e870624a` | clean |
| `git hash-object` of the spec | 79a9a40e…, unchanged |
| `grep` for `M3i \`auth.spec.ts\``, "virtual", "M3a–M3i" over the plan | as above, consistent |
| `make install lint` | pass (Semgrep 0 findings / 20 rules, rule tests 20/20, eslint) |
| CI on head e870624a | checks, security, image, host: pass; publish/deploy-staging skipped |
| Host head SHA at end | e870624a3caec545c059342119cceba68fe8fbfd, unchanged |
| Not run | `make test`, `test-live`, `e2e`, `host-test`: no code changed (CI ran the suite green) |

### Residual risks and test gaps
- Unchanged from R1: no passkey can exist until M3g (accepted, spec v1.22 T5), and M3g-2's front-end review should re-check the M3i screens it changes (FE-71, A11Y).

### Required before merge
- None.

### Deferred conditions
- P3 #2 (optional): M3h states that removing a user's last TOTP is refused (replacing it is allowed) and tests it. Deferred to the M3h PR.

### Optional improvements
- None.

