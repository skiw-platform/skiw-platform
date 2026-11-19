# Plan — M3g-2b: real-browser passkey tests

- **Date:** 2026-11-20 · **Author:** Builder (deep tier) · **Status:** draft, part of PR M3g-2b-1 for review.
- **No slice spec.** M3g-2b has no reviewed spec of its own. Its scope is what earlier work deferred to
  it: slice spec `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 (§2, §7 rows "M3g-2b
  adds …", §9 last paragraph) and DECISIONS "M3i-3", "M3g-2a-1", "M3g-2a-2b-1", "M3g-2a-2c" and
  "M3g-2a-2d". It adds no product behaviour beyond the three review findings below.
- **Base:** `main` = `b463be5`.

## 1. What is deferred to M3g-2b

| # | Item | From | PR |
|---|---|---|---|
| D1 | Real (virtual) authenticator: add on the offer and on Security, remove | spec §2, §9 | 1 |
| D2 | Server-side refusal of a second credential from the same device (exclude list) in a real browser | spec decision 5 | 1 |
| D3 | `StepUp` in a real browser: code, and "Use a passkey instead" | spec §7, DECISIONS 2a-1 [A] | 1 (happy paths), 2 (keyboard) |
| D4 | Keyboard: focus containment in `StepUp` (Tab and Shift-Tab wrap, Escape, outer page `inert`), the inline remove question (Escape, focus back) | spec §7 "Modal not modal", decision 6(d) | 2 |
| D5 | axe and no horizontal overflow on Security, the offer and the dialog, desktop and mobile | spec §7 last row, DECISIONS 2a-1 [A] | 1 (open states), 2 (dialog and question at both widths) |
| D6 | FE-71 real content: longest labels (busy labels, "(n)" suffixes, the long status texts) at the mobile width | DECISIONS 2a-1 [A] | 2 |
| D7 | The "Passkey added" announcement on Today | DECISIONS 2d [A](c) | 1 |
| D8 | Sign in with a passkey on the code screen | DECISIONS M3i-3, 2a-1 | 3 |
| D9 | Server-side session revocation seen in a real browser: a second signed-in context is signed out by a passkey change (AUTH-07) | spec §9 | 3 |
| D10 | Real-browser replay of the PR 165 token-epoch order (a cancelled change's late session read must not replace the token) | DECISIONS 2c, Round 1 fix | 3 |
| D11 | Cross-browser matrix | spec §9 | 4 (owner decision, §4) |
| F-a | PR 165 P2: the sixth-attempt throttle test on the frozen `clock` | review | 1 |
| F-b | PR 166 P2: the Today notice mounts with its text already in the live region | review | 1 |
| F-c | PR 166 P3: the Today notice clears only when the page changes (the skip link keeps it) | review | 1 |

## 2. Approach

**Authenticator.** Chromium's virtual authenticator through the Chrome DevTools Protocol `WebAuthn`
domain (`newCDPSession(page)`, `WebAuthn.enable`, `addVirtualAuthenticator` with `ctap2`,
`internal`, resident key, user verification on and verified, automatic presence). The page keeps
the browser's own `navigator.credentials`, so origin, RP ID, client data and the exclude list are
Chromium's real code; only the device is simulated. Helper: `web/e2e/authenticator.ts`.
Playwright 1.63 also has `context.credentials`, which **replaces** `navigator.credentials.create`/`get`
with Playwright's own code. It works in every engine but skips the browser's WebAuthn code, so it
proves less; it is considered only for PR 4.

**Projects.** `playwright.config.ts` has two projects, `desktop` (Desktop Chrome) and `mobile`
(Pixel 7). Both are Chromium; "mobile" is a viewport, touch and user agent emulation, not an
Android browser. CI installs Chromium only (`.github/workflows/ci.yml`).

**axe.** `@axe-core/playwright` 4.13.0 is already a dev dependency (WCAG 2.0–2.2 A/AA tags, as the
existing specs). No new dependency is needed for any PR in this plan (UNI-06).

**Live regions.** No screen reader runs in CI. A `MutationObserver` added before the page loads
records, per `aria-live` region, text present when the region entered the DOM (`mounted`, which
screen readers commonly skip) and text written into a region already there (`changed`, the case
they announce). The test asserts "Passkey added" and "Passkey removed" are `changed`, never
`mounted`. This proves the DOM pattern, not an announcement.

**Users.** Each test makes its own invited user (`accounts_invite`, as M3i-3), with a random e-mail.
A passkey change re-issues the session, so each later change needs a new step-up: a code from the
next 30-second step, or the dialog's passkey.

## 3. PR split (≈ 400 changed lines each)

| PR | Contents | Est. lines |
|---|---|---|
| **M3g-2b-1** (this) | This plan. F-a, F-b, F-c with vitest and mutants. `e2e/authenticator.ts`; `e2e/passkey.spec.ts`: enrol → offer → add with the virtual authenticator → Today announces it (D7) → skip link keeps it, Security clears it → step-up by code → the same device refused (D2) → a second device adds → remove after the question, step-up by the dialog's passkey (D1, D3) → axe, overflow, console. Shared `enrolToCodes` in `seed.ts`. | ≈ 405 (measured) |
| **M3g-2b-2** | Keyboard and layout (D4–D6): Tab/Shift-Tab wrap and Escape in `StepUp` opened from Add and from Remove, focus back to the opener, Sign out and nav unreachable by keyboard while it is open; the remove question by keyboard; axe with the dialog and question open; long rows and busy labels at 412 px. Plus the skip-link question (§5 Q1) if the owner wants it fixed. | ≈ 300 |
| **M3g-2b-3** | Sign-in with a passkey (D8); a second context signed out by a passkey change, this one kept (D9); the token-epoch replay with held responses through `page.route` (D10). | ≈ 350 |
| **M3g-2b-4** | Only if the owner says yes (§5 Q2): Firefox and WebKit projects for the screens that need no authenticator (sign-in, enrolment, Security list, keyboard, axe, overflow), CI installing those browsers. | ≈ 150 |

**Why this PR 1.** The three findings are small and independent; the first real-browser test is the
one that checks F-b and F-c where they matter (a real hash change and a real DOM), and it gives the
shared helpers later PRs need. Keyboard containment (PR 2) is a separate concern with its own
failure modes.

## 4. What a cross-browser matrix can honestly cover

- **Chromium** (both projects): everything above, with the virtual authenticator.
- **Firefox, WebKit** (Playwright builds): no CDP `WebAuthn` domain, so no virtual device in the
  browser's own stack. Non-passkey screens, keyboard, axe and overflow can run there; passkey
  ceremonies only through `context.credentials`, which replaces the browser's WebAuthn and so tests
  our page logic, not Firefox's or Safari's. Playwright's WebKit is not Safari.
- **Not verifiable in CI at all:** real platform authenticators (Touch ID, Windows Hello, Android),
  security keys, cross-device (phone) sign-in, synced passkeys, real Safari and mobile browsers, and
  real screen-reader speech (VoiceOver, NVDA, TalkBack). These need a manual check by a person
  before go-live; this plan does not claim them.

## 5. Open questions for the owner

1. **Skip link on Security (found while building PR 1, verified in Chromium).** On `/#security` the
   skip link (`href="#main"`) changes the hash, and spec decision 2 ("any other hash reads as
   Today") then shows Today. The person is moved off the page they were on. Fixing it means amending
   decision 2 (for example: a hash other than `#security` keeps the current page; or the skip link
   moves focus without changing the hash). PR 1 does not change this; its test checks the skip link
   on Today only.
2. **Firefox and WebKit in CI (PR 4)?** Cost: two more browser installs and roughly doubled e2e
   time in the `checks` job; benefit limited as in §4.

## 6. Risks, rollback, CI

- **Flakiness.** TOTP codes depend on the 30-second step: the test uses the step after enrolment's,
  which the server accepts on either side of a step edge. The step-up window is
  `SKIW_STEPUP_MAX_AGE_MIN` (5); the test takes seconds. Random e-mails avoid collisions between
  parallel workers.
- **Chromium updates** can change the CDP `WebAuthn` domain; the helper is one file.
- **CI time:** one more test per project (≈ 4 s each locally); no new browser install in PRs 1–3.
- **Rollback:** each PR is tests plus, in PR 1, a small `App.tsx` change; reverting the PR is the
  rollback. No server, data, setting or dependency change.
