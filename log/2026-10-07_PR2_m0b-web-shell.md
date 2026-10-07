# PR 2 — feat: M0b web shell (React, Vite, Django serving, e2e)

- **Merged:** 2026-10-07T10:54:42Z (GitHub) · **Merge commit:** `1825ea01b43eeb11581c4ee39e8c8daf72e577ba` · **Branch:** `feat/m0b-web-shell` (final head `958d368fdc1a4b996b2c46906a2d70e5b7fbcbe2`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-2.receipt` on `agent-logs` (commit `0e6e781`, written 2026-10-07T10:53:42Z, before the merge); names head `958d368…` and review-file hash `2478c8753035c888e5ba632e0153539fca5b065f`; the archived review `reviews/PR-2.md` (log-branch commit `44f8891`) has the same hash.
- **Merge evidence:** `gh pr view 2` → state MERGED, mergedAt 2026-10-07T10:54:42Z, merge commit `1825ea0`, final head `958d368` (equals the reviewed head of Round 5); `git merge-base --is-ancestor 1825ea0 origin/main` succeeded; `origin/main` log shows "Merge pull request #2".
- **Drafted by:** Claude Sonnet 5.5 (builder) · **Final verdict:** Approved with conditions (round 5; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 (`cf57625d`) · **Plan:** `docs/plans/2026-10-05-m0-scaffold.md` · **Milestone:** M0b

## What changed
A React 19 + Vite + TypeScript web shell (skip link, top bar, named nav, one main, one h1, empty state). Django serves the build same-origin: `/` renders a template holding the full shell, which React hydrates; `/assets/<path>` is served with immutable caching. Added Node 24 pinning (fnm, `.node-version`, `make check-node`), web lint/typecheck/vitest, Playwright e2e (axe, keyboard, overflow, no-JS, slow-start focus, console errors; desktop and mobile), the CI web and e2e steps pulled forward from M0d, the local-dev runbook update and a decisions entry.

## Why
Plan M0b. The owner confirmed Node 24, `lang="en-MY"`, ASK-1(a), ASK-6(b) and the Fernly layout direction (visual reference only) on 2026-10-06.

## Review rounds
- R1 (Blocked): [P1] static shell was blank without JavaScript (FE-31/32) → full shell in the server HTML, no-JS e2e and a parity test; the PR body got a rule-by-rule self-check table (`cadc022`, `1aaa8be`).
- R2 (Revision required): [P1] `createRoot` cleared the server HTML and dropped keyboard focus at startup → `hydrateRoot`, compact template, delayed-start focus e2e (`958d368`). [P2] handoff drift → handoff updated.
- R3: [P2] self-check rows cited unrelated evidence and stale status/test count → PR body rewritten row by row (no code change).
- R4: [P2] UNI-03 row overstated a tested 503 for a malformed manifest → body corrected. [P2] unnamed one-year cache literal → deferred to M0d.
- R5: Approved with conditions.

## Deferred conditions
- M0d PR: name the one-year asset cache duration (`app/shell/views.py:41`, FE-51) and keep `test_assets_are_served_with_long_immutable_caching` in sync; add the production web build stage; verify production manifest/assets; remaining UNI-13 gates (secret scan, dependency audit, image scan).
- M2: CSP nonce and other security headers.
- Follow-up brand PR: navy `#001C30` / gold `#FFB300` tokens, contrast check, decision entry.

## Decisions worth keeping
- Static shell markup in `app/shell/templates/shell/shell.html` must match `web/src/App.tsx` output with no whitespace between tags (hydration); the parity e2e test guards content drift.
- A malformed `web/dist/.vite/manifest.json` is not handled (only a missing one returns 503); accepted because it is an internal build artifact.
- All M0b decisions are in `docs/DECISIONS.md` (entry 2026-10-06).

## Follow-ups
- Brand-colour decision (skiwealth.com navy/gold, owner 2026-10-07) is not yet in `docs/DECISIONS.md`; record it in the brand-tokens PR with the reviewer-environment ruling (PR 1 round 2).
- Spec v1.8 (PR 3) must be approved before M0c merges.

## Appendix — final review round
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
