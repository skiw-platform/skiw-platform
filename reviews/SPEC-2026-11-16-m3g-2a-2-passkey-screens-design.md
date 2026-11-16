# Review — 2026-11-16-m3g-2a-2-passkey-screens-design

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 2 — 2026-11-16 · scope: slice spec
- **Spec review:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` · version 1.1 draft · hash (`git hash-object`) `4b204c423ffe305459c6ce88f2197e4246397ebe`
- **Parent spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.22 · hash `79a9a40ee1a686ae1082e8d11a73b299deb66d38`
- **Repo evidence:** `main` = `origin/main` = `af01756f454e2ae3cf4b3360accc51be82ae615c`; the revised draft is untracked and no implementation PR exists. Read-only review of v1.1, Round 1, handoff, parent/plan/decisions/runbook, PR 161 Round 9, current client contracts, active guardrails and the freshly fetched Web Interface Guidelines. No file was written except this review.

**Verdict:** Revision required

Version 1.1 resolves the exact registration wire format, hash URL, Malaysia date/time identifier, source/role corrections and server-versus-browser proof ownership from Round 1. It also introduces a credible shared post-send reconciliation design. It is not implementation-ready because the operation rules disable or expose the wrong controls while the modal is active, Sign out conflicts with the no-protected-POST reconciliation gate, successful factor-list bodies have no semantic validator, and repeated Remove buttons remain indistinguishable by accessible name. The ambiguous remove message is backwards, and the changed PR cut remains an unanswered owner question with one PR above the project's split-or-explain threshold.

**Model used:** Codex (GPT-5), deep review · **Switch model next step?** No — the remaining work is a small set of auth/UI contract corrections; use the deep tier again because post-mutation token ownership remains security-sensitive.

### Round 1 resolution audit

| Round 1 finding | Round 2 result |
|---|---|
| Registration browser/server boundary | Resolved by decision 5: all creation-option binary fields and exact confirm credential shape are pinned. |
| URL-less primary page | Resolved by decision 2: `/#security`, real anchors, history/reload/direct-open and signed-out/sign-out behavior are defined. |
| Sent mutation lifecycle | Partly resolved by decision 6; the new Sign out and StepUp contradictions below remain. |
| Accessible async behavior | Partly resolved by decision 8; modal operability, runtime-unsupported focus and repeated destructive-control names remain incomplete. |
| Added-date identifier | Resolved by decision 3: fixed `Asia/Kuala_Lumpur` date/time, null form, collision suffix and matching confirmation. |
| Sources, roles and proof ownership | Resolved by decisions 4/permissions and threat-model row 7. |
| PR split | Three PRs chosen, but the builder changed the owner's cut and still asks for acceptance; 2b also lacks the required >450-line rationale. |

### Findings

### [P1] The single-flight rule disables the StepUp control it needs and treats a modal's background as operable
- Category: internal contradiction / likely accessibility failure
- Rule: A11Y-01; A11Y-03; FE-21; FE-70; Web Interface Guidelines “Accessibility” and “Focus Management”
- Evidence: decision 6(d) disables “every Add, Remove and confirm control” throughout “ceremony, step-up, sent mutation” (`docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md:29`), so on its literal reading the StepUp Confirm control is disabled during the step-up phase. Decision 8 instead says the heading, nav and Sign out remain operable during every operation (`:31`). The mounted `StepUp` declares `role="dialog" aria-modal="true"` (`web/src/screens/StepUp.tsx:100-105`), but its current implementation only handles Escape; it does not make the background inert or contain focus. PR 161 explicitly deferred real mounting of this component to this slice, so its prior focus review is not proof of modal behavior.
- Failure scenario: Add receives `stepup-required`; the dialog opens, but its Confirm is covered by the global disabled rule. If a builder interprets “confirm” narrowly to avoid that, Tab can instead leave the asserted modal for Security navigation or Sign out, and assistive technology is told that content is modal while the application deliberately keeps that content interactive. On runtime `NotSupportedError`, the specified failure focus target is Add just as the next render removes Add.
- Why it matters: the required extra check can become impossible or the modal can lie about its interaction boundary. Both are keyboard/screen-reader failures on a security operation.
- Required correction: define states and control ownership explicitly. While StepUp is open, the outer Security page is inert and its Add/Remove/nav/Sign out controls are unavailable; focus is contained in StepUp, whose code input, Confirm, passkey and Cancel controls use StepUp's own busy state. Cancel/Escape returns focus to the originating Add or Remove control. Outside StepUp, single flight locks only competing factor operations. When runtime support loss removes Add, focus moves to a durable target (Security heading; on the enrolment offer, Skip) rather than Add. State whether only one inline removal confirmation may be open.
- Owner: builder
- Verification: Vitest mounts StepUp from Add and Remove and proves outer controls are inert/unavailable, dialog controls remain usable, repeated operations cannot start, Escape/Cancel restore origin focus, and runtime support loss lands on the durable target; M3g-2b performs keyboard, focus-containment and axe checks in both browser projects.
- Status: open

### [P1] Sign out is permitted exactly when the reconciliation gate forbids its protected POST
- Category: security weakness / internal contradiction
- Rule: AUTH-13; UNI-03; FE-21
- Evidence: once confirm/remove is sent, decision 6(b) says “no further protected POST is sent” until the result supplies a usable token or `readSession()` reconciles it (`:29`). Decision 8 simultaneously keeps Sign out operable throughout an operation (`:31`). Sign out is itself `POST /api/auth/logout` with the current token (`web/src/api.ts:39-42`, `:80-92`). A departed screen may not update but its shared token still must reconcile (`spec:29`, `:49`).
- Failure scenario: a confirm/remove commits and rotates the cookie while its answer is held or lost. The person activates Sign out before reconciliation; `logout()` sends the old in-memory token, recreating the stale-token protected-POST class decision 6 is meant to close.
- Why it matters: this is a direct contradiction at the AUTH-13 boundary. A builder cannot satisfy both requirements, and choosing the wrong one causes a security-state failure.
- Required correction: put Sign out behind the same protected-POST gate. Either disable it from the moment a mutation is sent until reconciliation finishes, or queue the intent and send logout only after a successful session/token read; state what the person sees if reconciliation remains unresolved. Navigation may leave the screen, but it must not bypass the gate. Align the modal rule with finding 1.
- Owner: builder
- Verification: held-answer tests for add and remove activate Sign out after send and prove no logout request precedes reconciliation, the eventual logout uses the reconciled token exactly, an unresolved read sends no protected POST, and no departed Security state is updated.
- Status: open

### [P1] Every destructive row action still has the same accessible name, “Remove”
- Category: likely accessibility failure / task error
- Rule: A11Y-01; A11Y-03; FE-22; Web Interface Guidelines “Accessibility”
- Evidence: decision 3 makes each row's displayed identifier unique and repeats it in the confirmation (`:26`), but decision 7 gives the row action only the text “Remove” (`:30`). Neither decision 8 nor the milestone requires `aria-label`/`aria-labelledby` that associates the action with the unique row text (`:31`, `:75-76`). A row's own accessible name does not automatically become the descendant button's accessible name.
- Failure scenario: two passkeys produce two controls announced only as “Remove, button.” A screen-reader user navigating by controls cannot tell which credential each destructive action targets even though sighted row text is unique.
- Why it matters: the user can retire the wrong credential. The project defaults likely accessibility failures to P1.
- Required correction: require every Remove button's accessible name to include the exact unique row identifier, for example `Remove Passkey, added 16 Nov 2026, 14:05 (2)`, using `aria-labelledby` or an equivalent label. Keep the visible label concise, and use the same identifier in the confirmation and focus-return association.
- Owner: builder
- Verification: Vitest creates same-minute and null collisions, asserts every Remove button has a distinct role/name tied to its row, activates by that name, and proves the confirmation and request id correspond to the selected row.
- Status: open

### [P1] A status-200 factor list has no semantic parsing boundary
- Category: untrusted-data boundary / task failure
- Rule: UNI-03; FE-21; FE-23
- Evidence: decision 3 assumes `passkey: [{id, created_at}]` (`:26`), while flow 5.1 treats only unreadable/non-200 answers as load failure (`:41`). No decision, threat row or milestone defines what happens when a readable status-200 body has a non-array `passkey`, missing/non-string/duplicate ids, or an invalid non-null timestamp (`:55-65`, `:75`). The shared API validates only the outer body; `Intl.DateTimeFormat.format(new Date(invalidValue))` can throw rather than render a controlled error.
- Failure scenario: a malformed-but-readable success body crashes Security during formatting, renders duplicate action identities, or permits a Remove request with an invalid id. The page neither shows its specified load error nor suppresses mutations on unvalidated data.
- Why it matters: the browser/server boundary remains untyped at runtime. A single malformed list answer can make the entire factor-management page unusable or target an unintended identifier.
- Required correction: define one factor-list parser used by initial load and every reconciliation read. A valid 200 body has a `passkey` array; each entry has an id matching the server's documented factor-id contract, unique within the answer, and `created_at` either null or a parseable finite ISO timestamp. Any semantic failure is the ordinary list-load error, renders no rows/add-remove mutation controls from that answer, and logs no credential data. Pin whether unknown top-level/entry keys are ignored or rejected.
- Owner: builder
- Verification: Vitest covers missing/non-array list, malformed/empty/duplicate ids, invalid dates, null date and unknown keys; every invalid answer reaches the controlled load error with no mutation request or render exception.
- Status: open

### [P2] One ambiguous-result message gives the wrong retry advice after removal
- Category: task error / ambiguity
- Rule: UNI-03; FE-22
- Evidence: decision 6(e) gives both ambiguous add and ambiguous remove the same text: “Check the list below; try again if it is not there” (`:29`). That is valid for add, where absence means it did not commit. For remove, absence means it did commit; presence is the condition that may call for retry. The flow does not define the pre-operation identity set used to interpret the refreshed list (`:43-45`).
- Failure scenario: a removal answer is lost but the server committed. The refresh correctly shows the credential absent, while the UI instructs the person to try removal again because it is not there—an impossible and misleading action.
- Why it matters: the list is meant to be authoritative reconciliation. Reversing its meaning undermines the recovery path precisely after an uncertain security mutation.
- Required correction: define action-specific reconciliation against the operation's known id/baseline. For add, a newly observed credential means added; unchanged means not confirmed. For remove, the selected id absent means removed; present means not confirmed/try again. Give each action accurate status text and say how unrelated concurrent list changes are described without claiming more than the client knows.
- Owner: builder
- Verification: ambiguous add/remove tests cover committed and uncommitted outcomes plus unrelated list changes, with exact action-specific text and no duplicate mutation automatically sent.
- Disposition (P2 only): before approval
- Status: open

### [P2] The revised PR cut is still owner-open and PR 2b exceeds the split-or-explain threshold
- Category: delivery ambiguity
- Rule: PROJECT.md §4 PR size rule
- Evidence: decision 11 records three PRs but says the builder adjusted the cut and points to Q1 (`:34`). Q1 still asks the owner to accept page+focus / add+remove / offer (`:80-81`), so the exact boundary is not decided. PR 2b is estimated at about 560 lines (`:76`). The project rule requires a split or a stated reason the work cannot be safely split past roughly 450 lines; the spec cites only the 600-line stop and supplies no >450 rationale (`:34`, `:76`, Q2 `:82`). The owner's recorded choice was three PRs with the helper/lifecycle in the smaller first PR, not approval of this changed 560-line middle.
- Failure scenario: work starts on a cut the owner has not accepted, and review receives a 560-line auth PR whose only size justification is that it remains below the absolute stop line.
- Why it matters: the unresolved cut changes sequencing and review surface. The project's target and split-or-explain rule apply before build, not only if measured lines cross 600.
- Required correction: obtain the owner's explicit answer to Q1. Then either recut/split 2b so each PR is near the target, or state the concrete coupling that makes a safe split worse and record owner acceptance of that rationale. Keep the hard stop: if measured scope passes 600, split before review. Remove resolved questions from §10 and make each milestone independently shippable.
- Owner: owner (cut/rationale acceptance); builder (revised milestones)
- Verification: the spec contains one accepted dependency order, estimates and independent done-when statements; every >450 estimate has a concrete safe-split rationale, and no estimate relies solely on being under 600.
- Disposition (P2 only): before approval
- Status: open

### Applicability and draft-coverage audit

The applicability list was rebuilt before treating v1.1's threat model as evidence. There is no implementation self-check yet, which is expected for a draft.

| Area | Applies? | Round 2 result |
|---|---|---|
| UNI-01/03/05/09/13/16 | yes: typed boundary, shared lifecycle, ephemeral credentials, gates, auth runbook | Registration shape now passes; list parsing and operation/sign-out reconciliation fail findings 2 and 4. |
| AUTH-02/07/09/13 | yes: server authority, step-up, factor-change rotation | Server authority/proof ownership pass; protected-POST gate conflicts with Sign out. |
| TEN-11 (hard) | yes: client must not choose tenant/other user | Pass at design level: own factor id only, no tenant field. |
| FE-01/04-07/10/12-14/20-23/31-32 | yes: page/nav/list/dialog/state | URL/navigation now pass; list parser and modal state remain incomplete. |
| FE-50-52/60-61 | yes: reuse/tests/gates | Source references and test-layer ownership now pass; implementation gates are named. |
| A11Y-01-04/06; FE-70/71 | yes: modal, keyboard, announcements, responsive UI, dates | Loading/live-region/date rules pass at design level; modal interaction and unique destructive names fail findings 1 and 3. |
| Web Interface Guidelines | yes: UI spec | Fresh guidance checked for focus, modal state, control names, navigation, async feedback and locale. Findings 1 and 3 remain. |
| Other active packs and PROJECT §9 | n/a / pass | No money, records, files, jobs, payments, public links, external services, new tenant source or locked switch. Passkeys remain optional; TOTP remains required. |

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` | `4b204c423ffe305459c6ce88f2197e4246397ebe` before review write; rechecked unchanged below. |
| Main/source state | `main` and `origin/main` both `af01756`; revised draft untracked; unrelated workspace files untouched. |
| Round 1 correction audit | All seven findings traced to v1.1 decisions, flows, threat model, milestones and open questions; four fully resolved, two partial and the PR cut still open. |
| Existing contract feasibility | Inspected `StepUp` modal markup/controls and shared `api` token/logout/reconciliation behavior; current StepUp has Escape handling but no modal containment because this is its first mounted use. |
| Parent/plan/decision/runbook consistency | Rechecked parent v1.22 D7/roles/URL/session rules, M3 plan, durable M3g decisions, auth runbook and PR 161 Round 9 conditions. |
| Fresh Web Interface Guidelines | Fetched and checked accessibility, focus, semantic action names, modal/navigation state, async feedback and locale/date guidance. |
| Whitespace/instruction-injection check | No whitespace error; no text asks the agent to skip a gate, alter the verdict or expose data. |
| Code/test/CI | Not run: this is an untracked spec-only review with no implementation PR. |

### Residual risks and test gaps
- Real WebAuthn registration, first mounted StepUp behavior, keyboard focus containment, axe, responsive overflow and cross-browser focus remain correctly deferred to M3g-2b; that named condition must remain.
- The server owns proof that other sessions are revoked. This browser slice can prove only response/token handling and visible reconciliation.
- Recovery-code display despite failed token reconciliation remains the optional PR 161 P3 outside this slice unless the owner explicitly adds it.

### Required before approval
- Correct the modal/control-state model and runtime-unsupported focus target (finding 1).
- Gate or queue Sign out behind sent-mutation reconciliation (finding 2).
- Give each Remove action a unique accessible name (finding 3).
- Define one semantic factor-list parser and malformed-200 behavior (finding 4).
- Make ambiguous add/remove truth checks and messages action-specific (finding 5).
- Resolve the owner-open cut and the >450-line split-or-explain requirement (finding 6).
- Bump the spec version and rerun `review spec docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md`.

### Deferred conditions
- Real-browser registration/management, virtual authenticator, modal keyboard/axe, responsive overflow and cross-browser focus matrix → M3g-2b (correctly retained; re-review after this spec is corrected).

### Optional improvements
- Add hover/active feedback for secondary controls when these screens land; the current global secondary style still has none.
- PR 161 Round 9 P3 #1 (show exact-success recovery codes despite a token-reconciliation failure) remains an optional separate decision.

### Handoff block (only when handing off)
<!-- roles/reviewer.md §10 -->

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
