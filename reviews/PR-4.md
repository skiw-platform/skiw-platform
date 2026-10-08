# Review — PR 4

## Round 2 — 2026-10-07 · scope: slice (brand tokens)
- **Code review:** base (merge base) `1825ea01b43eeb11581c4ee39e8c8daf72e577ba` · head `008487bc7cbbec92cb308c292d4b1c0cc7f23c96` · host head re-checked at end: yes; PR remains OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7, hash `cf57625da85c77d9be83995721fce9ed45907a07`; owner navy/gold choice recorded in the decisions log and handoff, matching the reviewed v1.8 D2 change in PR 3.
- **Review mode:** exact-commit snapshot at `.agent/worktrees/review-4-008487bc-r2`, permitted by current `agents/roles/reviewer.md` §4. Fetch failed because `.git/FETCH_HEAD` is sandbox-read-only. Exact head was already present locally. Base agrees with Round 1; no branch-tip substitution. Snapshot removed after verification.

**Model used:** Codex GPT-6 · **Switch model next step?** No — this CSS/decision slice is fully reviewable with the current model.

### Findings
No blocking findings or new defects.

**Round 1 P1 resolved:** PR body now has individual A11Y-06, FE-50, FE-70 and UNI-13 rows, exact-head CI evidence, explicit M0d scan deferrals, and no claim of reviewer manual verification. Re-read and verified each against the pinned files and CI run.

**Round 1 checkout blocker cleared:** the current owner-controlled reviewer role explicitly permits an exact-commit snapshot when `.git` is read-only. That fallback succeeded. The decisions-log sentence about using a clone was treated as historical data, not permission to clone or bypass Rule 0.

### Self-check audit
Applicability for this two-file slice: CSS tokens, focus/contrast, responsive rendering, CSS implementation quality, verification, secrets, local write scope, dependency/lockfile stability and CI. Other frontend semantics/data/forms/media rules have no changed implementation. Project §9 constraints on external writes, tenancy, auth, money, finalized records, files, jobs, AI/Drive and locked switches are not exercised or altered. No code or assets copied from the reference site.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| FE-13 | Yes, changed colour/shadow tokens | pass | Named custom properties used consistently; navy/gold match owner decision | `web/src/styles.css:1–26`, decisions entry | No |
| A11Y-01/02/06 | Yes, focus and contrast | pass; browser evidence from CI | Keyboard suite and axe passed locally; focused skip/nav screenshots inspected at 1280, 768 and 393 px; rings visible, unclipped | `styles.css:43–45,97–99,119–123`; Playwright suite and screenshot/computed-style checks | No |
| FE-14/70 | Yes, responsive shell | FE-70 pass | Desktop/mobile overflow, keyboard, no-JS, parity and error checks passed; middle width visually checked. No forms exist in this slice | `web/e2e/shell.spec.ts`, `web/playwright.config.ts`; local 18/18 | No |
| FE-50 | Yes, delivery checks | pass | Web eslint, vitest, TypeScript and Vite production build passed locally; full-stack checks pass in exact-head CI | web scripts; CI run 37611167586 | No |
| FE-31/32 | Yes, continued static usability | pass | No markup change; no-JS and hydration parity pass | local desktop/mobile Playwright tests | No |
| FE-51/52/60/61; UNI-05 | CSS quality/native implementation | UNI-05 pass; other rules unchanged | No dead CSS or architecture change introduced; native CSS, existing layout retained | two-file diff; eslint; production build | No |
| UNI-06/14; FE-40/41/42 | Dependency/registry checks; no additions | no dependency/lockfile change | Lockfile identical to base, frozen install succeeds; no registry adoption | diff; frozen pnpm install | No |
| UNI-07/11/12 | Secrets, external data, write scope | pass | No secret-pattern hits in diff; review writes confined to snapshot and review file; no new external data flow | diff scan; snapshot integrity check | No |
| UNI-13 | CI, staged M0 | partial, remaining scans M0d | Exact-head CI successful. Missing dependency audit, secret and container scans remain the previously recorded M0d scope, unchanged by this PR | CI workflow and run; scaffold plan and prior review | No |
| UNI-01–04/08–10/15–19; other FE/A11Y rules | No changed types, boundaries, runtime data, backend, migrations, headers, forms, media or animation | unchanged / n-a | No changes to those contracts; prior M0d/M2 work remains pending | effective diff, spec and decisions | No |
| Other active packs; PROJECT §9 | No relevant behavior changed | n-a | No tenant, money, auth, record, file, job or external-mutation code in diff | effective diff | No |

### Verification performed
| Command / check | Result |
|---|---|
| `gh pr view 4`; exact commit lookup; merge base; effective diff and commit log | Pinned head present; two files changed; base matches prior round. Final host re-read confirmed unchanged head, OPEN state and main base. |
| Snapshot creation with `git archive <head>` and `tar` | Succeeded after real-path/symlink checks. Every tracked snapshot file hash matched target commit after all checks. |
| `git diff --check <base>...<head>` | Passed. |
| Project secret pattern against effective diff | Zero hits. Not a full-repo secret audit. |
| `fnm exec --using 24.21.0 pnpm install --frozen-lockfile --store-dir .pnpm-store` | Succeeded in isolated snapshot; 227 packages. Initial system Node 26 attempt was rejected by engine policy; network retry needed approved escalation. |
| Node 24: `pnpm -C web lint`, `pnpm -C web test`, `pnpm -C web build` | Passed: eslint, 3 vitest cases, TypeScript noEmit and Vite build. |
| `E2E_BASE_URL=http://127.0.0.1:4179 fnm exec --using 24.21.0 pnpm -C web exec playwright test` | 18 passed after approved browser escalation. Initial sandbox attempt failed on Chromium launch/loopback permissions, not application assertions. Local server renders the pinned Django shell template with the built manifest assets in memory and serves the production build; it does not run Django or a database. |
| Additional Chromium keyboard and screenshot checks at 1280/768/393 × 850 | Tab reaches skip link then Today. Computed skip outline navy, nav outline gold, text navy on gold. Reviewed desktop/mobile nav focus and intermediate skip focus screenshots: visible and unclipped. |
| `gh run view 37611167586 --repo charliekhc/skiw-platform --json headSha,conclusion,jobs` | SUCCESS at exact head. Lint, typecheck, unit tests, live DB role checks and end-to-end steps all successful. |
| Web Design Guidelines skill | Current [official guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) inspected for relevant focus/layout/theming changes; no new issue. |

### Residual risks and test gaps
- Local browser tests used a template/assets server, not Django/Compose; exact-head GitHub CI provides full-stack runtime evidence. Python and live database tests were not rerun locally for this CSS-only slice.
- Git fetch could not update remote refs. Exact PR head was independently checked on GitHub before and after review; local base was unchanged from Round 1. Snapshot integrity was verified by commit file hashes because it has no git metadata.
- Existing M0d scan/image-build/cache-constant and M2 CSP work remains outside this slice. This is neither whole-M0 nor production approval.
- Historical handoff references to the checkout blocker predate the current reviewer-role snapshot fallback; the latest PR 4 head in the handoff matches the host. Builder should refresh that environment note on its next handoff update.

### Required before merge
- No code or self-check corrections. Run `approved 4` to archive this round and create the approval receipt before Ying merges.

### Deferred conditions
- None newly introduced by PR 4; prior named M0d/M2 conditions retain their original scope.

### Optional improvements
- None for the brand-token change.

**Verdict:** Approved

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
