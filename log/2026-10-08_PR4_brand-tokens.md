# PR 4 — feat(web): navy and gold brand tokens

- **Merged:** 2026-10-08T09:16:31Z (GitHub) · **Merge commit:** `ab68fea33de8cdc755ecdd7f782fab28694452ff` · **Branch:** `feat/m0b-brand-tokens` (final head `008487bc7cbbec92cb308c292d4b1c0cc7f23c96`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-4.receipt` on `agent-logs` (commit `74452c0`, written 2026-10-08T09:15:47Z, before the merge); names head `008487b…` and review-file hash `43717afa08b6554b4ace719293cfaf0849bf1af9`; the archived review `reviews/PR-4.md` (log-branch commit `3f4e94e`) has the same hash.
- **Merge evidence:** `gh pr view 4` → state MERGED, mergedAt 2026-10-08T09:16:31Z, merge commit `ab68fea`, final head `008487b` (equals the reviewed head of Round 2); `git merge-base --is-ancestor ab68fea origin/main` succeeded; `origin/main` log shows "Merge pull request #4".
- **Drafted by:** Claude Sonnet 5.5 (builder) · **Final verdict:** Approved (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 on main (`cf57625d`); the D2 colour wording is in PR 3 (v1.8, approved with conditions, not yet merged at this PR's merge) · **Plan:** none (follow-up condition of PR 2) · **Milestone:** M0b follow-up (brand tokens)

## What changed
`web/src/styles.css` tokens changed from the neutral green placeholders to the owner's brand colours: navy `#001C30` (sidebar, brand text, focus ring on light surfaces) and gold `#FFB300` (active nav pill, skip link, focus ring inside the navy sidebar; navy text on gold). `docs/DECISIONS.md` got an entry for the colour choice and the reviewer-environment ruling. Markup unchanged.

## Why
Owner choice A on 2026-10-07 (colours read from https://www.skiwealth.com/), and the follow-up condition from the PR 2 review.

## Review rounds
- R1 (Blocked): [P1] the PR self-check lacked individual A11Y-06, FE-50, FE-70 and UNI-13 rows → PR body corrected, same head. The reviewer also could not create a detached checkout (sandbox `.git` read-only).
- R2: Approved. The reviewer used the exact-commit snapshot fallback of the updated reviewer role, ran 18/18 Playwright locally, checked focus screenshots at 1280, 768 and 393 px.

## Deferred conditions
- none newly introduced; earlier conditions stay: M0d (name the asset cache constant, web build stage in the image, dependency audit, secret scan, image scan), M2 (CSP nonce).

## Decisions worth keeping
- Gold is never text on white and never a focus ring on white; text on gold is navy. Poppins from the site is not adopted.
- Reviewer's note: the `docs/DECISIONS.md` sentence about a clone fallback is historical; the reviewer role now permits an exact-commit snapshot.

## Follow-ups
- Refresh the environment note in the handoff (done on the next handoff update).
- Kit upgrade 1.7.1 → 1.7.3 (owner request) still needs the owner's `go`; it must not ride on a reviewed PR.
- Spec v1.8 (PR 3) merge, then `setup` Part B and the M0 plan update before M0c.

## Appendix — final review round
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
