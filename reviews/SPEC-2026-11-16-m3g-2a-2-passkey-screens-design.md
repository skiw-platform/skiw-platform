# Review — 2026-11-16-m3g-2a-2-passkey-screens-design

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 1 — 2026-11-16 · scope: slice spec
- **Spec review:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` · version 1.0 draft · hash (`git hash-object`) `20e6537f633f1a3b94911ed641c4805e09c276d1`
- **Parent spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.22 · hash `79a9a40ee1a686ae1082e8d11a73b299deb66d38`
- **Repo evidence:** `main` = `origin/main` = `af01756f454e2ae3cf4b3360accc51be82ae615c`; the draft is untracked and no implementation PR exists. Read-only review of the draft, parent spec, M3 plan, relevant durable decisions/runbook, handoff, PR 161 Round 9, current client/server contracts, active guardrails and the fresh Web Interface Guidelines. No file was written except this review.

**Verdict:** Revision required

The product choices are coherent: one Security home, created-time-only entries, try-first step-up, confirmation before removal, and an optional Add/Skip offer after recovery codes. The draft is not implementation-ready because its WebAuthn registration boundary is unspecified, its new navigation is deliberately absent from the URL, and its sent-mutation lifecycle does not yet prove token recovery after the screen is left. New asynchronous states also lack a complete accessible announcement/test contract. Three open owner/design choices and several source-of-truth mismatches remain.

**Model used:** Codex (GPT-5), deep review · **Switch model next step?** No — the corrections are design text and owner choices; use the deep tier again for the next review because this remains an auth boundary.

### Findings

### [P1] The registration ceremony has no exact browser/server boundary contract
- Category: guardrail mismatch / ambiguity
- Rule: UNI-03; AUTH-02; FE-23
- Evidence: decision 7 says only that `register(begin, confirm, signal)` runs begin → `navigator.credentials.create()` → confirm with the same commit rules as assertion (`docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md:31`). Milestone 1 likewise names outcomes but not the data transformation (`:78`). Registration is not the assertion shape already implemented: the server's creation options contain binary `challenge`, `user.id` and each `excludeCredentials[].id`; the browser response contains binary `clientDataJSON` and `attestationObject`, plus `getTransports()` where available. The server fixture shows the accepted response keys (`app/accounts/tests/authenticator.py:80-88`), while current `passkey.ts` decodes only assertion `challenge`/`allowCredentials[].id` and encodes `authenticatorData`/`signature`/`userHandle` (`web/src/passkey.ts:26-49`, `:55-67`).
- Failure scenario: a builder copies the assertion conversion. `user.id` or an excluded credential id remains base64url text instead of bytes, so `credentials.create()` rejects the options; or the confirm body sends assertion fields and omits `attestationObject`, so py_webauthn refuses every registration. Both readings satisfy the current prose.
- Why it matters: this is the core user task, and it crosses an untyped browser/server security boundary. A wrong shape makes every passkey add fail.
- Required correction: specify the exact creation-options conversion and exact credential JSON sent to confirm, including every binary field, optional field and omission rule. State whether the implementation is manual or uses a platform method and why it works in every supported browser. Pin the confirm body to exactly `{credential}` and the fields py_webauthn reads.
- Owner: builder
- Verification: Vitest proves the fake authenticator receives byte arrays for `challenge`, `user.id` and every excluded id; proves the exact base64url confirm body (`id`, `rawId`, `type`, `response.clientDataJSON`, `response.attestationObject`, transports, attachment and extension results as applicable); malformed/missing fields fail uniformly; M3g-2b proves the same contract against the real server with a virtual authenticator.
- Status: open

### [P1] A page in primary navigation cannot deliberately have no URL
- Category: guardrail mismatch / task failure
- Rule: FE-05 (hard); FE-31; Web Interface Guidelines “Navigation & State”
- Evidence: the draft adds Security as the second primary-nav item (`:25`) but requires it to exist only in React state, with no URL and reload returning to Today (`:20`, `:26`, `:41`, Q1 at `:86`). The live nav uses real anchors and `href` values (`web/src/App.tsx:75-84`). A URL-less page either turns navigation into a button, violating “links navigate, buttons act”, or uses a link whose URL does not represent its destination. It also makes browser Back/Forward, reload, direct open and link semantics disagree with the visible page.
- Failure scenario: a keyboard user activates Security, reloads to recover from an error, and unexpectedly lands on Today; Back does not return to Today because no history entry exists. Cmd/Ctrl-click cannot open Security because there is no destination.
- Why it matters: this is a primary application page, not a transient dialog. The draft knowingly removes standard navigation behavior and conflicts with the existing semantic nav.
- Required correction: give Today and Security distinct same-origin URLs and real anchors. This need not add a Django route: a reviewed query or hash contract on `/` can preserve the existing shell while supporting direct open, reload, Back/Forward and `aria-current`; alternatively choose `/security` and put its shell route in a prior server PR. Define how an unauthenticated request to that URL is handled and how the URL is normalized after sign-out.
- Owner: owner (route form); builder (spec contract)
- Verification: Vitest covers URL → view and active-nav state; M3g-2b covers click, keyboard activation, direct open, reload and Back/Forward in both browser projects.
- Status: open

### [P1] Sent add/remove mutations are not guaranteed to reconcile after navigation or unmount
- Category: security weakness / ambiguity
- Rule: UNI-03; AUTH-13; FE-21
- Evidence: add and remove both rotate the current session and CSRF token (`:30`). Decision 7 says an unreadable registration answer is reconciled, while flow 5.5 says that a sent confirm finishing after the person leaves changes no screen (`:31`, `:50`); it never says the unmounted caller must still consume a valid token or perform the authoritative session read. Removal has the same rotation but no corresponding lost-answer or leave-after-send rule (`:46`). The existing `api.rotated()` only calls `readSession()` for a status-200 answer with the expected `next` but a missing token; a network/truncated/non-matching answer returns false immediately (`web/src/api.ts:67-78`), so the new caller must explicitly own the wider reconciliation. Double-click/new-action behavior is also unstated even though a second registration begin replaces the first server challenge (`app/accounts/views.py:477-484`).
- Failure scenario: registration confirm or removal commits, rotates the cookie, and ends other sessions. The user navigates away before the body is usable. The component unmounts and suppresses all work, leaving the module token stale; the next protected POST is rejected by CSRF. Two quick Add activations can also replace the first challenge while its browser prompt remains open, making the first valid ceremony fail unpredictably.
- Why it matters: this recreates the exact stale-client/live-session class PR 161 spent nine review rounds closing, now on the factor-management mutations.
- Required correction: define one operation lifecycle for add and remove. Before commit, leaving aborts begin/prompt and starts no confirm. After confirm/remove is sent, the operation continues to consume the exact rotated answer or performs `readSession()` even if the UI owner unmounts; it may update the shared token but must not update the departed screen. A lost/malformed answer must never permit a protected POST on the old token. Only one action may be active: controls enter a named busy state and a new action cannot replace an in-flight prompt/commit. Define the list-read truth check for both ambiguous add and ambiguous remove.
- Owner: builder
- Verification: held-answer tests cover navigation/unmount before begin, during the prompt, after confirm/remove is sent, valid rotated body, lost/truncated body and failed session read; they assert exact request order/token, no stale protected POST, no state update after departure and no duplicate begin/confirm/remove on repeated activation.
- Status: open

### [P1] Loading and asynchronous outcomes lack an accessible announcement contract
- Category: guardrail mismatch / likely accessibility failure
- Rule: A11Y-01; A11Y-03; FE-70; Web Interface Guidelines “Accessibility”
- Evidence: the new page defines empty and load-error text but no loading state (`:41`); add/remove define messages and focus targets but do not require a live region, busy semantics or what remains operable while each request/prompt runs (`:43-48`). Milestones test empty/error and focus but omit loading, live announcements, busy state and repeated activation (`:78-80`). The approved deferral to M3g-2b covers real-browser verification; it does not waive semantic behavior or unit coverage in this slice.
- Failure scenario: a screen-reader user activates Add or Remove and hears no progress, refusal or completion; the list silently changes after a network response. A keyboard user activates an operation again because no busy state is exposed, or focus is sent to a success node that disappears on the next render.
- Why it matters: factor management is security-sensitive and fully asynchronous. Sighted text alone does not satisfy the project's WCAG 2.2 AA guardrail.
- Required correction: specify the initial loading UI, named polite/assertive live regions for load/add/remove/unsupported outcomes, `aria-busy`/disabled behavior, durable focus targets after success and failure, and the exact active control set during a ceremony, step-up and sent mutation. Keep the existing PR 161 focus condition for both SecondFactor and StepUp.
- Owner: builder
- Verification: Vitest asserts loading, accessible status names/live-region semantics, busy controls, focus after every success/refusal/cancel/unsupported/network path and no duplicate action. M3g-2b performs keyboard + axe + overflow checks at desktop/mobile widths.
- Status: open

### [P2] “Added date” is not precise enough to identify the passkey being removed
- Category: ambiguity / material risk
- Rule: UNI-03; FE-22; Web Interface Guidelines “Locale & i18n”
- Evidence: each entry is identified only as “Passkey, added <date>” in `Asia/Kuala_Lumpur` (`:27`), removal confirms only “Remove this passkey?” (`:29`), and Q2 still asks agency versus browser timezone (`:69-73`, `:87`). The durable owner decision is created time with no user label, but it does not define display precision. Two passkeys added on the same calendar date can render identically, making the generic destructive confirmation unable to tell the person which row is being retired.
- Failure scenario: a person adds a phone and laptop on the same day, then removes one. Both visible names and the confirmation are identical, so they can retire the wrong credential and only discover it at the next sign-in.
- Why it matters: removal is recoverable because TOTP remains, but the screen's sole distinguishing attribute must actually distinguish normal same-day additions.
- Required correction: retain the owner-approved no-label design but specify `Intl.DateTimeFormat` with the fixed agency timezone and explicit date/time fields precise enough for sequential registrations; include that same rendered identifier in the removal confirmation. Define the `null` form and a deterministic collision fallback. Resolve Q2 in the decision, not as an implementation-time choice.
- Owner: owner (display choice if calendar-date-only was intended); builder (format/test contract)
- Verification: deterministic tests cover two same-day entries, DST/UTC-boundary input, `null`, ordering independent of formatting, and confirmation text tied to the selected id.
- Disposition (P2 only): before approval
- Status: open

### [P2] The draft disagrees with the parent sources on roles, decision references and proof ownership
- Category: documentation consistency
- Rule: AUTH-03; FE-52; reviewer evidence rule §3
- Evidence: decision 4 and the configurable-values section cite D8 for factor step-up (`:28`, `:71`), but parent D8 is “No stored third-party passwords”; factor authentication/step-up is D7 (`docs/specs/2026-10-05-skiw-platform-stack-design.md:92-93`). The permissions table invents an `admin` role and omits General and Unit manager (`:53-55`), while the closed role catalogue is owner, general, unit_manager, adviser and staff (`parent spec:182`, permission matrix `:545-560`). Milestone 2 says frontend Vitest proves “other-session rotation” (`:79`), but only existing server/live tests can prove that server-side revocation; the browser can prove only its response/token behavior.
- Failure scenario: the implementation self-check cites the wrong design control, silently excludes two real roles from the UI spec, or claims a security property from a test layer that cannot observe it.
- Why it matters: these are lasting auth records and future review evidence; inaccurate citations and proof claims make the approval trail unreliable.
- Required correction: cite D7/AUTH-09 for factor step-up; enumerate the actual role catalogue or say “every signed-in user” and reference the server permissions; split server AUTH-07 proof from client rotated-token proof in the milestone.
- Owner: builder
- Verification: every cited parent section names the described control; the role row matches the parent catalogue; each done-when claim is observable by the named test layer.
- Disposition (P2 only): before approval
- Status: open

### [P2] The implementation split remains undecided and the suggested split does not bound its large half
- Category: delivery ambiguity
- Rule: PROJECT.md §4 PR size rule
- Evidence: the draft alternates between one “PR” (`:10`, `:15`) and an A/B split, estimates 650–800 lines, and leaves Q3 open (`:75-88`). The proposed A = milestones 1–2 contains the registration helper, two carried focus fixes, navigation/list states, add, remove, confirmation and step-up integration—the great majority of the estimate—so the text does not show that A falls below the 600-line stop line or near the 400-line target.
- Failure scenario: the builder starts one oversized branch on the default reading, or calls the draft “split” while PR A still crosses the stop line without the owner's recorded exception.
- Why it matters: boundaries affect reviewability and the order in which the deferred PR 161 focus condition becomes reachable.
- Required correction: resolve Q3 now. For each PR, name its milestones, dependency order, estimated code+test+docs lines and independent done-when. If any PR is expected past 600, record the owner's explicit go-ahead and why a smaller safe slice is worse; otherwise split again (for example helper/focus, Security management, enrolment offer).
- Owner: owner (exception or split); builder (boundaries/estimates)
- Verification: the revised spec has one split, no singular contradictory scope, and each PR can be reviewed and shipped without an unreachable or half-wired user path.
- Disposition (P2 only): before approval
- Status: open

### Applicability and draft-coverage audit

The reviewer built this list before treating the draft's threat model and milestones as evidence. There is no PR self-check yet, which is normal for a pre-build spec; the eventual PR self-check must include every applicable row below.

| Area | Applies? | Draft coverage | Reviewer result |
|---|---|---|---|
| UNI-01/03/05/09/13/16 | yes: typed browser boundary, shared logic, ephemeral credentials, gates, auth runbook | partial in decisions 6–7, threat model and milestone 4 | UNI-03 fails on findings 1 and 3; the rest is designable |
| AUTH-02/07/09/13 | yes: server authority, factor change, step-up, session/token rotation | decisions 4–7, permissions, threat model | partial/fail on post-send lifecycle and wrong source references |
| TEN-11 (hard) | yes: factor id/body must not choose tenant | §6 says no tenant field | pass at design level; server remains authoritative |
| FE-01/04-07/10/12-14/20-23/31-32 | yes: new page/nav/list/dialog/state | page/flow structure only | FE-05 fails on URL-less nav; async/component contract incomplete |
| FE-50-52/60-61 | yes: reuse current API/helper/components, quality gates | milestones 1 and 4 | partial; proof/reference errors in finding 6 |
| A11Y-01-04/06; FE-70/71 | yes: keyboard focus, announcements, responsive browser behavior, dates/long labels | focus rule; browser suite deferred to M3g-2b | semantic/live-state gap in finding 4; real-browser deferral is correctly named |
| Web Interface Guidelines | yes: UI spec | destructive confirmation/focus partly covered | URL state, async announcements and deterministic `Intl` date format need correction |
| Other active packs and PROJECT §9 | n/a / pass | no money, records, files, jobs, payments, public links, external services, new tenant source or locked switch | no scope creep found; passkeys remain optional and TOTP remains required |

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` | `20e6537f633f1a3b94911ed641c4805e09c276d1`, unchanged at review end |
| Main/source state | `main` and `origin/main` both `af01756`; draft untracked; unrelated `.DS_Store` and `.pnpm-store/` left untouched |
| Parent spec/plan/decision consistency | reviewed v1.22 D7/D8, Flow 5.1, role catalogue/matrix, M3/M3g; M3 plan; DECISIONS M3g-1c, 2s-1, 2s-2, 2a-1 |
| Prior-condition audit | PR 161 Round 9 focus P2 is carried into decisions 9/milestone 1; browser matrix remains named M3g-2b |
| Existing contract feasibility | inspected current `App`, `api.rotated`, assertion helper, Recovery, server factor routes and registration fixture |
| Auth runbook | existing host-rebuild add/remove section is present; revised spec must name its UI update |
| Fresh Web Interface Guidelines | checked accessibility, focus, navigation/state, destructive confirmation, locale/date and interaction rules |
| Whitespace check | no whitespace error reported for the untracked draft |
| Instruction-injection scan | no text asks an agent to skip a gate, change a verdict or expose data |
| Code/test/CI | not run: this is an untracked spec with no implementation PR |

### Residual risks and test gaps
- Real WebAuthn creation, StepUp mounting, keyboard behavior, axe, responsive overflow and cross-browser focus remain intentionally deferred to M3g-2b; the revised spec must preserve that named condition.
- The server can prove other-session revocation, but the frontend slice can only prove it consumes the rotated response and token correctly.
- The PR 161 P3 suggestion to show one-time recovery codes despite token reconciliation failure remains optional and outside this spec unless the owner adds it.
- Unsupported-at-runtime behavior (`NotSupportedError` after the offer was shown) should be made explicit while resolving finding 4: retain Skip/remove, hide unusable Add, and announce the next step.

### Required before approval
- Define the exact registration options/credential wire format (finding 1).
- Give Security a real URL/navigation contract (finding 2).
- Complete the sent-mutation, unmount and duplicate-action lifecycle (finding 3).
- Define and test accessible loading/busy/status/focus behavior (finding 4).
- Resolve the passkey identifier/date format, source mismatches and PR split (findings 5–7).
- Bump the spec version and rerun `review spec docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md`.

### Deferred conditions
- Real-browser passkey registration/management, virtual authenticator, keyboard, axe and responsive matrix → M3g-2b (already named; re-review after this spec is corrected).

### Optional improvements
- Consider PR 161 Round 9 P3 #1—preserve/show exact-success recovery codes even if token reconciliation fails—as a separate explicit decision; it is not required for this slice.
- Add hover/active feedback for secondary controls when these screens land; the current global secondary style has none.

### Handoff block (only when handing off)
<!-- roles/reviewer.md §10 -->
