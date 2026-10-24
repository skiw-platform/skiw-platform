# PR 61 — fix(web): zod 4.6.7 and undici 8.12.3 for two high audit findings

- **Merged:** 2026-10-24T10:15:13Z (GitHub) · **Merge commit:** `2af8ff384975387470d7296f2fa2b6240a9c212e` · **Branch:** `fix/web-audit-zod-undici` (final head `c557a313bd2311b39257dd96cf2c3a43ab4a5b86`)
- **Gate breaches:** none (2 files, +27 / −12)
- **Approval receipt:** `reviews/PR-61.receipt` on `agent-logs`, written 2026-10-24T10:11:33Z (before the merge); names head `c557a31…`, review `reviews/PR-61.md` (hash `4bd96203…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 61` → MERGED, merge commit `2af8ff3`, final head equals the reviewed head; `git merge-base --is-ancestor 2af8ff3 origin/main` succeeded.
- **Built by:** builder · **Final verdict:** Approved (Round 1)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** none (main CI repair after PR 60)

## What changed
Main CI run 40068411894 (merge of PR 60) failed the `security` job: `pnpm audit --audit-level high` found `zod` below 4.6.6 (GHSA-mrhx-c7xc-m3w5, via `eslint-plugin-react-hooks`) and `undici` below 8.12.2 (via `jsdom`). `pnpm update -r zod undici` moved the lockfile to `zod` 4.6.7, `undici` 8.12.3 and `@babel/runtime` 7.29.10. Only `pnpm-lock.yaml` and a DECISIONS entry changed. No range in `web/package.json` changed. PR 60 changed no web file.

## Review rounds
- R1: Approved. One optional P3: the DECISIONS reason for the `@babel/runtime` move is wrong (7.29.10 sits only under `@testing-library/dom`; 7.29.7 stays elsewhere).

## Deferred conditions
- none.

## Decisions worth keeping
- Bump through the lockfile, not a `pnpm.overrides` pin and not an audit ignore. Same pattern as PR 51 (vite).

## Follow-ups
- Optional: correct the `@babel/runtime` sentence in the 2026-10-24 DECISIONS entry.
- Dependabot PRs 12–18, 26–28 and 48–50 are untouched.
