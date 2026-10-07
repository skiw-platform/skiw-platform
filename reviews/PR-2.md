# Review — PR #2

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

> A preliminary verification attempt was void: `pnpm install` created a temporary `.pnpm-store/` in the builder checkout despite running from the isolated clone. I removed that generated cache, confirmed the builder checkout was clean, and restarted the checks below without invoking `pnpm` or writing outside the review checkout. The void attempt is not evidence for this verdict.

## Round 5 — 2026-10-07 · scope: slice (M0b)
- **Code review:** base (merge base) `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `958d368fdc1a4b996b2c46906a2d70e5b7fbcbe2` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`. The v1.8 proposal is in separate PR 3.

### Findings

### [P2] Name the one-year asset cache duration in M0d
- Category: guardrail mismatch
- Rule: FE-51
- Evidence: `app/shell/views.py:41` still sets `max_age=31_536_000` inline, and `app/shell/tests/test_shell.py:42-46` asserts the resulting cache header. The PR self-check marks FE-51 partial and carries the Round 4 M0d disposition.
- Failure scenario: the duration is changed later without its one-year meaning being clear or the test being updated.
- Why it matters: FE-51 bars magic numbers. P2 is appropriate because this is one isolated, standard duration for hashed assets, with a test, and does not affect tenant data or user input.
- Required correction: give the duration a descriptive name when M0d adds the production web build and asset-serving path; keep the header test in sync.
- Owner: builder
- Verification: inspect the named duration and cache-header test in the M0d PR.
- Disposition: deferred to the M0d PR (production web build and asset serving)
- Status: open

**Round 4 before-merge P2 resolved:** the host PR body's UNI-03 row now says only a *missing* manifest returns 503 and cites `test_shell_reports_a_missing_build_clearly` (`app/shell/tests/test_shell.py:35-39`). It explicitly says malformed JSON or a missing `index.html` entry is unhandled by `read_entry` (`app/shell/views.py:16-21`). This matches the code and the isolated reproduction in Round 4. The code head and CI run are unchanged.

### Self-check audit
- **Applicable to this slice:** UNI-01/03/04/05/06/07/11/12/14/16/19; FE-01/02/04/05/06/07/10/11/12/13/14/20/21/22/31/32/40/50/51/52/60/61/70; A11Y-01/02/06; TEN-02/10. UNI-13 is staged across M0b/M0d by the approved plan.
- **Not yet applicable:** UNI-02/08/09/10/15/17/18; FE-03/23/24/34/41/42/71; A11Y-03/04/05; tenancy table/policy rules and feature packs without code in this slice, for the reasons recorded in Round 4.
- **Comparison:** the PR body has a rule-by-rule table covering the applicable IDs. The UNI-03 claim is now accurate and tied to the named test. FE-51 is candidly partial with a named M0d follow-up. Independent source and check evidence from Rounds 3–4 supports the other results at this unchanged head. No before-merge discrepancy remains.

### Verification performed
| Command / check | Result |
|---|---|
| Git host PR metadata, body and checks | PR open at head `958d368`, base `b6abd9f`; CI `checks` passed (run `37557408500`). The UNI-03 body text changed; the code head did not. |
| `git fetch origin`, merge base and checkout | Fetch succeeded. Merge base is `b6abd9f`. Reused the clean, detached local-clone fallback `.agent/worktrees/review-clone-2-958d368f` at the exact host head; `.agent/`, its worktrees folder, clone and review file are not symlinks. |
| Diff and hygiene | `git diff --check b6abd9f...HEAD` passed. Main and review-clone tracked trees are clean. No new code diff since Round 3. |
| Prior checks at this exact head | Round 3 independently passed Ruff, import-linter, strict mypy, pytest (27), ESLint, TypeScript, Vitest (3), Vite build and Compose configuration. Round 4 reproduced malformed-manifest exceptions. These were not rerun because the head is unchanged. CI at this head includes live-role and Playwright checks. |

### Residual risks and test gaps
- Independent browser and live database execution remains unavailable in this sandbox; the pinned CI result covers those checks. This is a slice review, not a production release review.
- Malformed internal build manifests still raise on `/`; the PR body now states that accurately. M0d's production build must verify that the generated manifest and assets are valid before deployment.
- M0d still owns the production image web build stage and remaining UNI-13 security gates. M2 owns the CSP nonce. The brand-token PR after PR 2 owns the navy/gold change and contrast check.

### Required before merge
- None. The owner still runs `approved 2` to archive the review and approval receipt before merging.

### Deferred conditions
- M0d PR: name the one-year asset cache duration (FE-51), verify the production manifest/assets, add the production web build stage, and finish the remaining UNI-13 security gates.
- M2: CSP nonce and other planned security headers.
- Follow-up brand PR after PR 2: navy/gold tokens, contrast check and decision entry.

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the remaining follow-ups are named and bounded.
**Verdict:** Approved with conditions

## Round 4 — 2026-10-07 · scope: slice (M0b)
- **Code review:** base (merge base) `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `958d368fdc1a4b996b2c46906a2d70e5b7fbcbe2` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`. The v1.8 proposal is in separate PR 3.

### Findings

### [P2] The self-check claims malformed manifests get a tested 503 response
- Category: documentation problem
- Rule: reviewer role §3 (re-verify each pass against its evidence); UNI-03
- Evidence: PR body `## Self-check`, UNI-03 row, says “Missing/bad manifest returns 503” and cites `test_shell_reports_a_missing_build_clearly`. That test supplies no manifest (`app/shell/tests/test_shell.py:35-39`). `read_entry` returns `None` only when the file is absent (`app/shell/views.py:16-21`); malformed JSON raises `JSONDecodeError` and a manifest without `index.html` raises `KeyError` in an isolated call at this head. Neither becomes the cited 503 response.
- Failure scenario: the owner relies on the self-check to believe malformed build artifacts have a tested, controlled response; a malformed manifest instead produces an exception on `/`.
- Why it matters: the revised table is otherwise reviewable, but this row still attributes behavior to a test that does not cover it. The runtime case is narrow because the manifest is an internal build artifact.
- Required correction: make the PR-body claim match the existing test (“missing manifest returns 503”), or implement and test the broader malformed-manifest behavior if that is intended. A body-only correction can keep the same head.
- Owner: builder
- Verification: compare the revised UNI-03 row with `read_entry` and the named test; no unsupported “bad manifest” claim remains, unless code and a test actually cover it.
- Disposition: before merge
- Status: open

### [P2] One-year asset cache duration is still an unnamed literal
- Category: guardrail mismatch
- Rule: FE-51
- Evidence: `app/shell/views.py:41` sets `max_age=31_536_000` directly. The PR self-check marks FE-51 partial and identifies the same literal; `app/shell/tests/test_shell.py:42-46` checks the resulting cache header.
- Failure scenario: a future maintainer changes the asset policy without knowing the literal means one year or misses another reference to the duration.
- Why it matters: FE-51 bars magic numbers. Downgraded from the default P1 to P2 because this is one isolated, standard duration for hashed static assets, its current value is tested, and it does not affect tenant data or user input.
- Required correction: name the one-year duration where the asset policy is next revised and keep the cache-header test in sync.
- Owner: builder
- Verification: in the M0d PR, inspect the named duration and its test.
- Disposition: deferred to the M0d PR (production web build and asset-serving work)
- Status: open

**Round 3 P2 largely resolved:** the PR body now gives relevant, rule-specific evidence for the previously grouped UNI and FE rows, states that navy/gold tokens belong to a follow-up PR, and reports 18 browser cases. The only remaining self-check discrepancy is the malformed-manifest assertion above. There is no code change since Round 3; its resolved no-JavaScript, focus, and handoff findings remain resolved.

### Self-check audit
- **Applicable to this slice:** UNI-01/03/04/05/06/07/11/12/14/16/19; FE-01/02/04/05/06/07/10/11/12/13/14/20/21/22/31/32/40/50/51/52/60/61/70; A11Y-01/02/06; TEN-02/10. UNI-13 is staged across M0b/M0d by the approved plan.
- **Not yet applicable:** UNI-02/08/09/10/15/17/18; FE-03/23/24/34/41/42/71; A11Y-03/04/05; tenancy table/policy rules and feature packs without code in this slice. The reason for each group remains as in Round 3; this PR adds no business values, production secret source, business logging, audit event, migration, headers, cookies, forms, animation, images, registry components or real feature content.
- **Comparison:** the revised body covers every applicable ID, distinguishes the remaining M0d gates, and cites relevant source/checks for the earlier grouped rows. The UNI-03 evidence overstates its test; FE-51 is candidly marked partial and is dispositioned above. Independent source and check evidence supports the remaining outcomes at this unchanged head.

### Verification performed
| Command / check | Result |
|---|---|
| Host PR metadata, body and checks | PR open at `958d368`, base `b6abd9f`, CI `checks` success (run `37557408500`). The PR body changed; the code head did not. Head re-checked at the end. |
| Checkout and diff | Reused clean, detached local-clone fallback `.agent/worktrees/review-clone-2-958d368f` at the exact head. Shared `.git/FETCH_HEAD` remains sandbox-denied. Merge base remains `b6abd9f`; `git diff --check` passes. |
| Prior checks at the unchanged head | Round 3 independently passed Ruff, import-linter, strict mypy, pytest (27), ESLint, TypeScript, Vitest (3), Vite build and Compose configuration. These were not rerun because the code head is unchanged. CI at this head covers live-role and Playwright checks. |
| Manifest claim | In the isolated checkout, calling `read_entry` with invalid JSON raised `JSONDecodeError`; with `{}` it raised `KeyError`. The cited test covers only an absent file. Temporary files were removed. |
| Checkout hygiene | No tracked or staged changes. Generated Python caches from the narrow runtime check were removed. |

### Residual risks and test gaps
- Independent browser and live database checks remain unavailable in this sandbox; CI passed at the pinned head. Detailed Actions step logs were not required for this body-only follow-up.
- A malformed build manifest currently raises on `/`; the M0d production build should verify asset integrity before deployment. The PR body should not claim this is already handled.
- M0d still owns the production image web build stage and remaining UNI-13 security gates. M2 owns the CSP nonce. The navy/gold token change remains in the follow-up brand PR.

### Required before merge
- Correct the UNI-03 PR-body assertion and run `review 2` again. If only the body changes, this code head and its CI result remain valid.

### Deferred conditions
- M0d PR: name the one-year asset cache duration (FE-51), add the production web build stage, and finish the remaining UNI-13 security gates.
- M2: CSP nonce and other planned security headers.
- Follow-up brand PR after PR 2: navy/gold tokens, contrast check and decision entry.

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the remaining before-merge correction is in the PR body.
**Verdict:** Revision required

## Round 3 — 2026-10-07 · scope: slice (M0b)
- **Code review:** base (merge base) `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `958d368fdc1a4b996b2c46906a2d70e5b7fbcbe2` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`. Spec v1.8 is in separate PR 3.

### Findings

### [P2] The PR self-check still gives unrelated evidence for several pass claims
- Category: documentation problem
- Rule: reviewer role §3 (re-verify every pass against its evidence)
- Evidence: PR body `## Self-check` marks UNI-01/03/04/05/06 pass using milestone count, commit style and diff-size disclosure; those do not establish strict typing, boundary validation, import boundaries or dead-code checks. Its UNI-11/12/16/19 row cites lockfiles, version pins and PR authorship rather than external-service authorization, write location, runbook updates and intended anonymous endpoints. FE-20/21/22 cites mobile CSS and overflow, which do not establish component structure or separation of content. Round 2 explicitly required correction of these grouped cells. The same PR body still says the brand-colour question is open although `.agent/handoff.md:30-32` records the owner's navy/gold choice, and its local test plan says 16 e2e passes although the suite now has nine tests across two browser projects (18 cases).
- Failure scenario: the owner reads the table as proof that these rules were checked and reads the stale UI status or test count as current.
- Why it matters: the self-check is the builder's reviewable evidence, and the prior before-merge correction remains incomplete. Independent checks support several outcomes, but the table's cited evidence does not.
- Required correction: revise the PR body so each grouped rule has evidence that actually checks it (or split rows and mark a rule `n/a` with its reason), and update the brand-colour status and e2e count. This can be a PR-body edit at the same code head.
- Owner: builder
- Verification: re-read the host PR body at this exact head; each pass cites a relevant file, command or check result, and the status/count match current evidence.
- Disposition: before merge
- Status: open

**Round 2 P1 resolved:** `web/src/main.tsx:2,12-19` now hydrates instead of clearing the populated root; `app/shell/templates/shell/shell.html:11-13` matches the React shell's current element/text structure. `web/e2e/shell.spec.ts:38-58` delays the script, focuses the original skip link, releases the script, and checks focus plus Enter navigation after load on desktop and mobile projects. The old keyboard test no longer waits before its first Tab. The host CI check passed at this exact head. Local browser execution remains unavailable in the reviewer sandbox.

**Round 2 P2 resolved:** `.agent/handoff.md:1,10,22-27,37-38` names head `958d368`, records the fixes, and requests Round 3. The builder says no finding remains on its side; this review records the remaining PR-body finding above.

### Self-check audit
- **Applicable to this slice:** UNI-01/03/04/05/06/07/11/12/14/16/19; FE-01/02/04/05/06/07/10/11/12/13/14/20/21/22/31/32/40/50/51/52/60/61/70; A11Y-01/02/06; TEN-02/10. UNI-13 is staged across M0b/M0d by the approved plan; web, browser and live-role checks are present now, with remaining security gates due in M0d.
- **Not yet applicable:** UNI-02/08/09/10/15/17/18; FE-03/23/24/34/41/42/71; A11Y-03/04/05; tenancy table/policy rules and other feature packs. This slice has no business values, production secret source, business logging, audit event, migration, headers, cookies, articles, variant props, data fetch, forms, animation, images or real feature content.
- **Builder table:** every applicable ID appears, and the no-JavaScript and focus pass claims now have relevant code and test evidence. The grouped rows identified in the P2 remain unsupported by their cited evidence. Independent review found no new code defect in this round.

### Verification performed
| Command / check | Result |
|---|---|
| Host PR metadata | PR open at exact head `958d368`; base `b6abd9f`; `ci / checks` success, run `37557408500`. Head re-checked after local checks. Detailed Actions logs were intermittently inaccessible through the host API. |
| Checkout | `git fetch` and `git worktree add --detach` were denied writing shared `.git` (`Operation not permitted`). The exact host head was already local; used the previously authorized local-clone fallback at `.agent/worktrees/review-clone-2-958d368f`, detached at that SHA. Its tracked tree is clean. |
| Effective diff and hygiene | 30 files in the M0b three-dot diff; Round 2 correction changes only template, client entry and e2e test. `git diff --check` passed; secret-name hits in reviewed surfaces were documentation or placeholders. |
| Python checks | Ruff check/format passed (44 files); import-linter kept four contracts; strict mypy passed for 17 source files; pytest: 27 passed, 7 live deselected. |
| Web checks | ESLint and TypeScript passed; Vitest: 3 passed; Vite production build passed under Node 24.21.0 using existing pinned package binaries. Temporary dependency symlink and build output were removed afterward. |
| Compose config | `docker compose --env-file .env.example config --quiet` passed. |
| Browser and database | Local Django `runserver` could not connect to the database because sandbox TCP access was denied; local Playwright/live-role checks were therefore not run. CI's single `checks` job includes `make test-live` and `make e2e`, and reported success at this head. |

### Residual risks and test gaps
- Local browser and live database behavior remain unverified in this sandbox. The pinned CI result covers those commands, but detailed step logs could not be retrieved.
- M0d still owns the production image web build stage and remaining UNI-13 security gates. M2 owns the CSP nonce. The owner-selected navy/gold tokens are scheduled for the follow-up brand PR after PR 2.

### Required before merge
- Correct the PR-body self-check evidence and stale UI/test-plan status, then run `review 2` again. No code change or new CI run is needed if the head stays `958d368`.

### Deferred conditions
- M0d: production image web build stage and remaining UNI-13 security gates.
- M2: CSP nonce and other planned security headers.
- Follow-up brand PR after PR 2: navy/gold tokens, contrast check and decision entry.

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — only PR-body evidence correction remains.
**Verdict:** Revision required

## Round 2 — 2026-10-07 · scope: slice (M0b)
- **Code review:** base (merge base) `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `1aaa8beab184abf32f6e313a583a3d58e773e59f` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`. Spec v1.8 remains in separate PR 3.

### Findings

### [P1] Replacing server HTML drops keyboard focus during load
- Category: guardrail mismatch
- Rule: A11Y-01, A11Y-06, FE-31, FE-32
- Evidence: `app/shell/templates/shell/shell.html:12-34` now sends a usable, focusable shell. `web/src/main.tsx:2,12-16` calls `createRoot(root).render(...)` on that populated root. React's official `createRoot` reference says the first render clears existing HTML in the root; use hydration for server-rendered HTML ([reference](https://react.dev/reference/react-dom/client/createRoot)). `web/e2e/shell.spec.ts:29-32` explicitly waits for the replacement before pressing Tab, so its keyboard test excludes the transition. In an isolated jsdom reproduction using the installed React version, focusing the original skip link then calling `createRoot`/`flushSync(render)` changed `document.activeElement` from the skip link to `BODY`.
- Failure scenario: a keyboard user presses Tab while the static shell is visible but before React mounts; the focused skip link is removed and focus returns to the document body.
- Why it matters: the user loses their place in the tab order during a normal slow load. The new no-JavaScript fallback is good, but the JavaScript path must preserve the same keyboard interaction.
- Required correction: preserve the focused node through client startup, either by hydrating matching server markup or by mounting React only where interactivity needs it. Add a browser test that delays the client script, focuses the server skip link, then permits client startup and verifies focus and the following keyboard action remain intact. The test must not wait for `networkidle` before the first Tab.
- Owner: builder
- Verification: run the delayed-start keyboard test at desktop and mobile widths; the skip link retains focus through startup and Enter still moves focus to `main`.
- Status: open

### [P2] Handoff still identifies the old head and says PR 2 has not been reviewed
- Category: documentation problem
- Rule: reviewer role §2 (report handoff drift)
- Evidence: `.agent/handoff.md:1,10,25,34` still says head `08309d4`, tells the owner to run the initial review, and says no PR 2 finding is open. GitHub reports PR 2 head `1aaa8be`; this round records an open P1.
- Failure scenario: the next builder session resumes from the old commit or assumes this review has not happened.
- Why it matters: the handoff is the in-flight task state, so inaccurate status can misdirect the next step.
- Required correction: update the local handoff to the current PR head and this review's findings after the builder receives this round. No code commit is required solely for that update.
- Owner: builder
- Verification: compare handoff head and finding status with the PR and newest review round.
- Disposition: before merge
- Status: open

**Round 1 finding:** resolved. The server template now contains the skip link, named navigation, one `main`, one `h1`, and the empty state (`app/shell/templates/shell/shell.html:12-34`). The Django and no-JavaScript browser tests assert that structure (`app/shell/tests/test_shell.py`, `web/e2e/shell.spec.ts:85-96`). This resolution does not cover the startup focus issue above.

### Self-check audit
- **Applicable to this slice:** UNI-01/03/04/05/06/07/11/12/14/16/19; FE-01/02/04/05/06/07/10/11/12/13/14/20/21/22/31/32/40/50/51/52/60/61/70; A11Y-01/02/06; TEN-02/10. UNI-13 is staged across M0b/M0d by the approved plan, with the remaining security gates due in M0d.
- **Not yet applicable:** UNI-02/08/09/10/15/17/18; FE-03/23/24/34/41/42/71; A11Y-03/04/05; tenancy table/policy rules and other feature packs. This slice adds no business values, production secret source, business logging, audit event, migration, headers, cookies, articles, variant props, data fetch, forms, animation, images, or real feature content.
- **Builder table:** the PR body now has a self-check table and covers the applicable IDs. FE-31/32 are supported for the no-JavaScript response. The A11Y-01 pass is contradicted by the focus-loss reproduction; its cited test waits until after the swap. Several grouped evidence cells describe unrelated facts (for example, UNI-11/12/16/19 cites package pins), so the table should be corrected on the next push. Independent source and check evidence was used for this verdict.

### Verification performed
| Command / check | Result |
|---|---|
| Host PR metadata and `gh pr checks 2` | PR open at exact head `1aaa8be`; base `b6abd9f`; `ci / checks` success, run `37490008251`. Head re-checked after local checks. |
| Detached checkout | Shared `.git/worktrees` registration denied by sandbox; used the previously authorized separate clone `.agent/worktrees/review-clone-2-1aaa8bea`, detached at the exact host head. Its tracked tree is clean. |
| Effective three-dot diff | 30 files; reviewed the M0b shell, serving path, tests, CI, runbook, dependencies, and the two Round 1 correction commits. `git diff --check` passed. |
| Ruff, import-linter, strict mypy | Pass: 44 files formatted, four contracts kept, 17 source files typechecked. |
| pytest | 27 passed, 7 live tests deselected. |
| ESLint and TypeScript | Pass under Node 24.21.0 using existing pinned binaries against the isolated clone; temporary dependency symlink removed afterward. |
| Docker Compose configuration | `docker compose --env-file .env.example config --quiet` passed. |
| Focus transition reproduction | Installed React and jsdom: focused static skip link before `createRoot`/`flushSync(render)`; active element was `BODY` afterward. This is a DOM-level reproduction, not a real-browser test. |
| Browser, Docker, CI step logs | Browser and live database unavailable in reviewer sandbox. CI succeeded at this head, but detailed step logs were intermittently unavailable through the host API. The checked-in keyboard test omits the startup transition. |

### Residual risks and test gaps
- A real-browser test for the focus transition is still needed; the existing browser test waits until after the replacement.
- Independent live database and browser runs remain unavailable in this sandbox; CI passed at the pinned head.
- M0d still owns the production image web build stage and remaining UNI-13 security gates. M2 owns the CSP nonce. The separate owner colour decision is scheduled for a follow-up PR after PR 2.

### Required before merge
- Preserve keyboard focus during client startup and add the delayed-start browser test.
- Correct the PR self-check evidence for A11Y-01 and the unrelated grouped cells; update the local handoff to the actual PR head and findings.
- Push the correction to PR 2, wait for CI on the new head, then run `review 2` again.

### Deferred conditions
- M0d: production image web build stage and remaining UNI-13 security gates.
- M2: CSP nonce and other planned security headers.
- Follow-up PR after PR 2: owner-selected navy/gold tokens and corresponding contrast check, as recorded in the handoff.

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the correction and test target are specific.
**Verdict:** Revision required

## Round 1 — 2026-10-06 · scope: slice (M0b)
- **Code review:** base (merge base) `b6abd9f605bdabda6c8c4522b061ce763bc8be1c` · head `08309d4a8425f562fd0ce25295986672ff37063d` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings

### [P1] The static shell has no usable content when JavaScript is unavailable
- Category: guardrail mismatch
- Rule: FE-31, FE-32
- Evidence: `app/shell/templates/shell/shell.html:10-13` sends only an empty `#root`, a message telling users to enable JavaScript, and a script. The header, navigation, heading and empty state exist only in `web/src/App.tsx:9-29`. Against the actual built assets, an independent Django `Client().get("/")` returned HTTP 200 with zero `<main>` and zero `<nav>` elements and one `<noscript>`. `web/e2e/shell.spec.ts:57-64` checks only for the enable-JavaScript message and therefore accepts this failure.
- Failure scenario: JavaScript is disabled, blocked by a browser policy, or fails to load; the adviser sees no navigation or page content despite this M0b shell being static.
- Why it matters: FE-31 requires static content to remain usable without JavaScript and FE-32 requires navigation and content visibility without it. A React SPA for later interactive modules does not require the current static shell to be blank without JavaScript.
- Required correction: render meaningful shell structure and content in the server response when JavaScript does not run, including navigation and a main landmark; update the no-JavaScript browser test to assert those elements and their content, while preserving one main and one h1 when JavaScript runs.
- Owner: builder
- Verification: inspect the server HTML and run the desktop/mobile Playwright tests with JavaScript disabled; the no-JavaScript page has a named navigation, one main, one h1 and a usable empty state.
- Status: open

### Self-check evidence gate
- The PR body has a short `## Self-check` paragraph, not the required rule-by-rule table. Reviewer role §3 says no self-check table means **Blocked**. The paragraph also omits applicable FE-31, while it claims FE-32 is covered by the browser tests even though the no-JavaScript test asserts only the warning. The builder needs to add the table with each applicable rule, result, evidence and a reason for every `n/a`; the reviewer will re-audit it on the next round.

### Self-check audit
- **Applicable to this slice:** UNI-01/03/04/05/06/07/11/12/14/16/19; FE-01/02/04/05/06/07/10/11/12/13/14/20/21/22/31/32/40/50/51/52/60/61/70; A11Y-01/02/06; TEN-02/10 for the unchanged runtime role and widened import contracts. UNI-13 is staged across M0b/M0d by the approved plan; this PR adds web, browser and live-role checks but not the remaining M0d security gates.
- **Not yet applicable:** UNI-02 (no business values), UNI-08/09/10/15/17/18 (no production secret source, logging, audit, migration, security headers or cookies added here; M2/M0d as planned), FE-03/23/24/34/41/42 (no articles, props with variants, business-logic component, data fetch or registry component), A11Y-03/04/05 (no forms, animation or images), FE-71 (the empty scaffold has no real content yet), tenancy table/policy rules (M4), and other ticked packs without feature code in this slice.
- **Compared with builder self-check:** FE-01/05/06/07, FE-13, FE-40/50/51/60/70 and A11Y-01/02/06 have source or CI evidence; FE-32 is contradicted by the actual server response. The summary does not cover many applicable rules, especially FE-31. No table is available for the mandated complete audit.

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin`, host PR metadata, merge base and diff | PR open at exact head `08309d4`; base `b6abd9f`; host reports `ci / checks` success (run `37472464228`). Effective diff: 30 files, including web shell, Django serving, CI and runbook. |
| `git worktree add --detach` | Denied writing `.git/worktrees` (`Operation not permitted`). Used separate local clone `.agent/worktrees/review-clone-2-08309d4a`, detached at the exact host head. |
| Ruff, import-linter, strict mypy | Pass; 44 formatted files, four contracts kept, 17 source files typechecked. Existing pinned Python tools from the main checkout's `.venv` ran against the isolated clone. |
| pytest | Pass; 27 selected, 7 live tests deselected. |
| ESLint, TypeScript, Vitest, Vite build | Pass against the isolated clone's source under Node 24.21.0 using existing pinned package binaries; 3 Vitest tests passed, Vite produced the manifest and hashed assets. Independent dependency installation was not repeated after the void attempt. |
| Django client against the built assets | HTTP 200 at `/`; actual response has no server-rendered `main` or `nav`, one `noscript`, and correct manifest asset links. |
| `docker compose --env-file .env.example config --quiet`, `git diff --check`, secret-name scan | Pass; secret-name hits in changed surfaces are placeholders or documentation only. |
| Local browser / Docker | Chromium launch was denied by the sandbox during the void preliminary attempt (`MachPortRendezvousServer: Permission denied`), so it was not repeated. Docker socket remains unavailable here. The checked-in Playwright suite and host CI pass at the exact head, but interactive behavior is unverified locally. |
| GitHub Actions detailed step logs | `gh run view` could not connect to the API during the preliminary attempt; host check conclusion and checked-in workflow were inspected in this restarted review. |

### Residual risks and test gaps
- The no-JavaScript shell is an open P1; the existing test currently approves the empty static response.
- Independent browser, Docker and dependency-install checks were unavailable in this sandbox. CI passed at the pinned head, but individual Actions step logs were inaccessible.
- M0d still needs the web build stage in the production image and the remaining secret, dependency and image scans; M2 adds the CSP nonce. These are scheduled by the approved plan.

### Required before merge
- Correct the P1 no-JavaScript shell and its browser test.
- Add the required self-check table to the PR body, then rerun `review 2` on the new head after CI passes.

### Deferred conditions
- M0d: production image web build stage and remaining UNI-13 security gates.
- M2: CSP nonce and other planned security headers.

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the correction and evidence gate are specific.
**Verdict:** Blocked
