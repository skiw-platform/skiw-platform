# Review — PR 4

## Round 1 — 2026-10-07 · scope: brand-token code change
- **Code review:** base (merge base) `1825ea01b43eeb11581c4ee39e8c8daf72e577ba` · head `008487bc7cbbec92cb308c292d4b1c0cc7f23c96` · host head re-checked at end: yes.
- **Spec review:** approved v1.7 on main (`cf57625da85c77d9be83995721fce9ed45907a07`); D2 navy/gold proposal in PR 3, approved with conditions at head `07bd5bd` (spec hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`). Owner colour decision is in this PR's `docs/DECISIONS.md` addition.

**Verdict:** Blocked
**Model used:** Codex GPT-6 · **Switch model next step?** No — a code finding is a PR-body correction; the environment needs a checkout-capable reviewer session for the independent gate.

### Findings

### [P1] The self-check omits applicable browser and delivery rules
- Category: guardrail mismatch
- Rule: `agents/roles/reviewer.md` §3; A11Y-06; FE-50/70; UNI-13
- Evidence: PR 4 body's self-check has A11Y-01/02, FE-13 and a generic row marking “other applicable UNI/FE/TEN rules” `n/a`. It has no A11Y-06 row, and FE-50/70 and UNI-13 are not given their actual evidence or a specific deferral. These apply to the CSS change: browser keyboard/axe verification, production build, desktop/mobile checks and CI. The body separately reports `make e2e`, and the pinned `web/e2e/shell.spec.ts` runs keyboard and axe tests on desktop and Pixel 7, so this is a self-check documentation failure rather than proof of a UI defect.
- Failure scenario: a reviewer accepts the broad `n/a` and misses that the changed focus/contrast tokens require real browser checks at both widths; the still-deferred UNI-13 scans are not visible in the rule table.
- Why it matters: applicable guardrail rows must be re-verifiable individually; the generic `n/a` obscures test coverage and outstanding delivery gates.
- Required correction: update the PR body only: give A11Y-06, FE-50, FE-70 and UNI-13 individual rows with the exact-head CI/browser evidence; state which UNI-13 scans remain deferred to M0d. Do not claim a manual reviewer browser check occurred.
- Owner: builder
- Verification: each row cites the relevant Playwright test or CI step and names its remaining gap; reviewer re-checks the body at the same head.
- Status: open

### Checkout blocker

`git fetch origin` succeeded, the host head was fetched locally and the merge base matched PR 4's base. I resolved `.agent/` and `.agent/worktrees/` as real in-repo directories, then ran:

```text
git worktree add --detach .agent/worktrees/review-4-008487bc 008487bc7cbbec92cb308c292d4b1c0cc7f23c96
fatal: could not create directory of '.git/worktrees/review-4-008487bc': Operation not permitted
```

No review checkout was created. `agents/roles/reviewer.md` §4 requires checks in the reviewer's own detached checkout and Rule 0 lists the only permitted Git writes (`fetch`, `worktree add/remove`). The new `docs/DECISIONS.md` entry proposes an isolated-clone fallback, but it does not override Rule 0's Git-write limit. Therefore local lint, typecheck, build, tests and manual browser inspection were not run by this reviewer. The exact-head CI result and read-only diff are useful evidence, not a replacement for this required checkout gate.

### Self-check audit

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| FE-13 | Yes, design tokens | pass | Colours and shadow are named in `:root`; uses reference variables elsewhere | `web/src/styles.css` diff | No |
| A11Y-01/02 | Yes, focus and contrast | pass | Static color pairs calculate to white/navy 17.37:1, navy/gold 9.68:1, muted/white 7.13:1; focus behavior and axe passed in exact-head CI but not observed locally | CSS diff; `web/e2e/shell.spec.ts`; CI | Runtime not independently observed |
| A11Y-06 | Yes, real browser keyboard and axe | missing | Tests exist and CI passed; no reviewer browser run | PR body; e2e tests | Yes, P1 |
| FE-50/70 | Yes, CSS build and desktop/mobile verification | generic `n/a` | `make e2e` builds and Playwright config has desktop + Pixel 7 projects; CI passed; no local run | Makefile; Playwright config; CI | Yes, P1 |
| UNI-13 | Yes, CI gate | generic `n/a` | Current `checks` job passed; full secret/dependency/image scan still deferred to M0d as recorded after PR 2 | CI workflow; PR 2 review | Yes, P1 |
| FE-31/32, FE-40, UNI-05/06/07/11/12/14 | Change is CSS/decision only; no markup, dependency, lockfile or external data flow changed | pass or `n/a` | No contrary evidence in the two-file diff | Pinned diff | No |
| Tenancy, auth, money, finalized records, files, jobs | No changed behavior in this diff | generic `n/a` | Not exercised | Pinned diff | No |

### Verification performed

| Command / check | Result |
|---|---|
| `git fetch origin`; `git cat-file -e <head>^{commit}`; `git merge-base <head> origin/main` | Fetch succeeded; exact head present; merge base `1825ea01b43eeb11581c4ee39e8c8daf72e577ba`. |
| `git diff --stat/name-status <base>...<head>` and `gh pr diff 4 --patch` | Two files: `docs/DECISIONS.md`, `web/src/styles.css`; 31 insertions, 13 deletions; read-only diff inspected. |
| `git diff --check <base>...<head>` | Passed. |
| Secret-scan pattern against the two-file diff | No hits. Full repository scan was not run. |
| WCAG contrast calculation from changed CSS token values | White on navy 17.37:1; navy on gold 9.68:1; dark body text on white 16.83:1; muted text on white 7.13:1. Not a substitute for a browser check. |
| PR 4 host checks | `checks` SUCCESS at exact head `008487bc`; host head re-checked unchanged. |
| Reviewer checkout / local tests / manual browser | Checkout failed with `Operation not permitted` above; none run. |

### Residual risks and test gaps
- Browser rendering, keyboard focus appearance and axe findings were not independently exercised by this reviewer. CI ran the existing desktop/mobile Playwright suite at the pinned head.
- The owner-approved site colour provenance was recorded in `docs/DECISIONS.md`; opening the site in this review timed out, so its live CSS was not independently verified. This does not undermine the owner's chosen hex values.
- The prior PR 2 conditions remain: M0d names the one-year cache constant and adds the production web build stage/scans; M2 adds the CSP nonce. PR 3 carries the matching D2 spec revision.
- No instruction-like material directed the reviewer to change a verdict or skip a gate.

### Required before merge
- Correct the PR body self-check rows above.
- Run this review in an environment where `git worktree add --detach` succeeds, or amend the reviewer role through the owner-controlled kit process to permit and define the isolated-clone fallback, then repeat the independent checkout/browser checks at the pinned head.

### Deferred conditions
- None introduced by PR 4. Prior M0d/M2 conditions remain in their named PRs.

### Optional improvements
- None required for this round.
