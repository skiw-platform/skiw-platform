# PR 166 — feat(web): M3g-2a-2d offer a passkey after enrolment

- **Merged:** 2026-11-19T16:03:36Z · **Merge commit:** d67972b562618cbbcb30ca78635b2e37b973ca75 · **Branch:** feat/m3g-2a-2d-offer
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-166.receipt` (log-branch commit holding the review `c6f17d07ca2e49bada3c6fae00cccad6efaf815a`; receipt time 2026-11-19T16:03:09Z, 27 seconds before the merge; head `fbbce245d9dc2b80fb0a4489804412273ba5817c`; review hash `68a40ae5fc850a6d62af28b663cf60a4a8df2019`)
- **Merge evidence:** `gh pr view 166` state MERGED, merge commit above, an ancestor of the fetched `origin/main`. Final head SHA equals the reviewed SHA.
- **Drafted by:** deep-tier sub-agent (Claude Opus), orchestrated by Claude Sonnet 5.5 · **Final verdict:** Approved with conditions (round 1, reviewer Claude Opus 5.5)
- **Spec:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 · **Milestone:** M3g-2a-2d

## What changed
After the recovery codes, where the browser has WebAuthn, an "Add a passkey?" screen offers Add (the existing add flow and step-up dialog) and Skip, then goes to Today. A failed add keeps the screen with focus on Add; lost passkey support focuses Skip; an ambiguous add stays on the offer with the list. Final size 408 changed lines (396 added, 12 removed).

## Why
Slice spec decision 10 and flow 5.4: the last of four passkey-screen PRs (2a-2a to 2d).

## Review rounds
- CI before review: the first run failed in e2e (`enrol.spec.ts` "the done button..." expected Today; the offer now comes first) → the test passes through the offer and presses Skip (commit fbbce24). Not a flake.
- R1: Approved with conditions; no P0/P1.

## Deferred conditions
- [P2] "Passkey added" is written into a live region that mounts with the text already in it (A11Y-03) → keep the region mounted and empty first; real-browser announcement check; M3g-2b, before the M3 gate review.

## Decisions worth keeping
- docs/DECISIONS.md "2026-11-19 — M3g-2a-2d": ambiguous add shows the list read-only; add ok but list read failing stays on the offer; Today notice cleared on page change; Skip stays enabled during an add.
- Not run by the builder: `make test-live`, `make audit` (no server or dependency change).

## Follow-ups
- The P2 above (M3g-2b).
- [P3] any hash change, including the skip link, clears the Today notice; clear only on a real page change (optional, can ride with the P2 in M3g-2b).
- Also due in M3g-2b: freeze the clock in the password-limit live test (PR 165's deferred P2).

## Appendix — final review round
## Round 1 — 2026-11-19 · scope: slice (M3g-2a-2d, last of four passkey-screen PRs)

- **Code review:** merge base `3e50b9ae2aef897f48d6abd523ec7b50fb25ccaa` (= `origin/main`) · head `fbbce245d9dc2b80fb0a4489804412273ba5817c` · head re-checked on the host at end: yes, unchanged; PR open, not draft.
- **Spec:** slice spec `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 (hash `cd1a0ac7…`, Round 4 Approved with conditions), decisions 4, 6, 8, 10, flow 5.4; main spec v1.22 (`79a9a40e…`) unchanged.
- **Reviewer:** Reviewer (Claude Opus 5.5); builder: Builder; owner: Ying. Detached checkout `.agent/worktrees/review-166-fbbce245`; no project file changed (Rule 0). A disposable probe test was written there, run, and deleted; `git status --untracked-files=no` is clean.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No — auth UI; the remaining work (M3g-2b) is also deep-tier.

### Findings

No P0 or P1. One P2 deferred to M3g-2b, one P3. No injection-like text in the PR body, commits, code or comments.

### [P2] "Passkey added" is written into a live region that mounts with the text already in it
- Category: guardrail mismatch (likely accessibility failure)
- Rule: A11Y-03; slice spec decision 10 ("Passkey added" in the polite region), decision 8 (the region is "always in the DOM, empty until used")
- Evidence: `web/src/App.tsx:182-184` renders `<div aria-live="polite">{signOutError ?? view.notice}</div>` inside the `signed_in` case; `Offer.tsx` calls `onDone(content.security.addedNotice)` → `go("signed_in", { notice })` (`App.tsx:202`), which swaps the `Screen` case. Reviewer probe (disposable vitest through the real enrolment flow): the offer's region and the Today region are different nodes and the offer's is disconnected after the add (`same-node: false, offer-region-connected: false`), so Today's region is inserted already containing "Passkey added". The builder's own DECISIONS [A](c) says the announcement is unverified, but the self-check marks A11Y-03 **pass** citing `App.tsx:183`.
- Failure scenario: a screen-reader user adds a passkey from the offer. Most screen readers do not announce content that is present when a live region is inserted, so the person hears the focus move to `main` and nothing confirms the add.
- Why it matters: the add's only success feedback may be silent to assistive technology. Downgraded from P1 because the impact is isolated: the text is visible, sits directly after Today's heading and one card inside the focused `main`, nothing is lost or misreported, the same mount-with-text pattern already ships for SignIn's expired notice, and real-browser announcement checks are already scheduled in M3g-2b.
- Required correction: make the Today region exist empty before the notice is written — e.g. keep one polite region mounted across `offer` → `signed_in` (render it outside the `Screen` switch), or mount Today with an empty region and set the notice in a following commit. Correct the self-check A11Y-03 line to match.
- Owner: builder
- Verification: a vitest asserting the region node exists and is empty in the render before "Passkey added" appears in it; the M3g-2b real-browser check of the announcement.
- Disposition: deferred to M3g-2b (before the M3 gate review)
- Status: open

### [P3] Any hash change clears the Today notice, including the skip link
- Category: defect (minor)
- Rule: DECISIONS "M3g-2a-2d" [A](c) intent ("the notice leaves with its page")
- Evidence: `App.tsx:54-57` `turn` clears `notice` on every `hashchange`/`popstate` while signed in, without comparing the page. The skip link `href="#main"` (`App.tsx:111`) changes the hash, and `pageOf("#main")` is still `today`.
- Failure scenario: on Today with "Passkey added", a keyboard user activates "Skip to content"; the page is still Today but the notice disappears.
- Why it matters: small; the add is done and Security shows it. The behaviour does not match the stated intent.
- Required correction: clear the notice only when the page actually changes (compare `next` with the current page).
- Owner: builder
- Verification: a test that the skip link keeps the notice and the Security link clears it.
- Status: open (optional; can ride with the P2 in M3g-2b)

### Self-check audit
Applicability list built before reading the table: UNI-01, 02, 03, 05, 07–09, 12, 13, 16; AUTH-05, 07 (via runner), 09, 13; TEN-11 (spec §6); FE-01, 04–07, 13, 14, 20–22, 50–52, 60, 61; A11Y-01, 03; A11Y-06/FE-70/71 (deferred to 2b by recorded decision); PROJECT §9 out-of-scope and locked switches. Every item is in the builder's table.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | `tsc --noEmit` clean locally; no `any`/ignore in diff | — |
| UNI-03 | yes | pass | pass | Offer only consumes `addPasskey`'s parsed result; `parseFactors`/`settle` unchanged | — |
| UNI-05 | yes | pass | pass | `FAILED` exported from `Security.tsx:20`, not copied | — |
| UNI-09 | yes | pass | pass | nothing logged; test asserts recovery code gone from DOM | — |
| UNI-13 | yes | pass | pass | run 44526444891 on head `fbbce24`: checks, host, image, security pass | — |
| UNI-16 | yes | pass | pass | `host-rebuild.md` "Add or remove a passkey" updated, accurate to code | — |
| AUTH-05 | yes | pass | pass | cancel/timeout/refused → one text `notAdded` (tests) | — |
| AUTH-09 | yes | pass | pass | 403 → `StepUp`, one retry; second 403 → generic, no third POST (test) | — |
| AUTH-13 | yes | pass | pass | Skip during held begin aborts, nothing sent (test); reviewer probe: Skip **after** confirm sent → Today, Sign out disabled with "Finishing your change…", no notice later, Sign out re-enabled | — |
| TEN-11 | yes | n-a (folded into tenancy note) | pass | only the shared runner's own-factor calls; no id or tenant field sent | — |
| FE-01/05/06/07 | yes | pass | pass | `<button type="button">` ×2, one `<h1>` | — |
| A11Y-01 | yes | pass | pass | focus to Add after failure/ambiguous/Cancel, to Skip after unsupported; outside inert during dialog (tests) | — |
| A11Y-03 | yes | pass | **partial** | offer outcomes in always-mounted `offer-status` ✓; Today notice in a region inserted with its text ✗ | P2 above |
| A11Y-06 / FE-70 / FE-71 | yes | n-a here (2b) | accepted | DECISIONS "M3g-2a-1" [A]; slice spec §9 | — |
| §9 out-of-scope / locked switches | yes | pass / n-a | pass | web-only; no server, route, setting, table, flag | — |

Spec conformance (decision 10, 6(f)): offered only when `passkeySupported()`; reads nothing first; Skip → Today silently; exact success + parsed list → Today with notice; failed → stays, Add focused, Skip available; runtime unsupported → Add hidden, focus Skip; ambiguous → stays, list shown, "could not confirm", no retry. Builder's [A] items (a)–(d) are reasonable readings of 6(f)/6(d) and are accepted; (c) is where the P2 lies.

### Verification performed
| Command / check | Result |
|---|---|
| `gh pr view 166` / `git cat-file -e` | head `fbbce245…` local; base `main`; open |
| `git diff --stat`, `--check` merge-base…head | 8 files, +396/−12 (408, under 450); `--check` clean |
| `pnpm install --frozen-lockfile` (review checkout) | ok |
| `pnpm -C web typecheck` | pass |
| `pnpm -C web lint` | pass |
| `pnpm -C web exec vitest run` | 9 files, 252 passed |
| Reviewer probe vitest (disposable, deleted) | Skip-after-send path correct per 6(e); Today notice region is a new node mounted with text (P2) |
| CI run 44526444891 | `headSha` = `fbbce245…`; checks (incl. live DB + e2e), host, image, security pass |
| Secret-scan pattern on added lines | no hits |
| End: host head SHA re-read; `git status --untracked-files=no` | unchanged; clean |

Not run locally: `make test-live`, `make e2e`, `make audit` (no server, DB or dependency change; CI `checks` covers live and e2e on this head).

### Residual risks and test gaps
- Screen-reader announcement of "Passkey added" on Today is unverified (P2).
- No offer-specific test for Skip after confirm was sent (reviewer probe passed; the runner path is covered by Security's tests). Worth adding in 2b.
- Real-browser axe/width checks of the offer screen are M3g-2b, as recorded.

### Required before merge
- None.

### Deferred conditions
- P2 "Passkey added" live region → M3g-2b, before the M3 gate review (with the existing PR 165 frozen-clock P2).

### Optional improvements
- P3 skip link clears the notice.
