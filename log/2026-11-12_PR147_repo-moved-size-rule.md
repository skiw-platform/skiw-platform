# PR 147 — docs: repo moved to skiw-dev1, PR size rule text

- **Merged:** 2026-11-12 (02:35:33 UTC) · **Merge commit:** 2c193385b7d10b038ee0e86ad7bd5d61551b5608 · **Branch:** docs/repo-moved-size-rule (final head d19d33d0d241799dc422eca95a212e517c1fbbe5)
- **Gate breaches:** none. The review's final round (R1) head SHA equals the PR's final head; the receipt (`reviews/PR-147.receipt`, 2026-11-12T02:34:53Z, review-file hash a47d61bd, review commit 65eaad8) precedes the merge by 40 seconds.
- **Approval receipt:** `reviews/PR-147.receipt` on agent-logs (written by `approved 147` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 147` (repo skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-12T02:35:33Z, merge commit 2c19338; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** the Sonnet 5.5 builder (docs only, standard tier) · **Reviewed by:** Claude Opus 5.5, one round · **Final verdict:** Approved (round 1)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** none (housekeeping) · **Milestone:** none (between M3h and M3i)

## What changed
`agents/PROJECT.md` §4: Remote now `https://github.com/skiw-dev1/skiw-platform`, and a new PR size rule line (target 400 LOC; past about 450 split or say why in the PR body; past 600 stop and ask the owner). `docs/DECISIONS.md` entry "2026-11-11 — Repo moved to the organization skiw-dev1; PR size rule text". +11/-1 over 2 files. No code, test, workflow or config change.

## Why
The old organization hit its GitHub Actions spending limit (PR 143's first CI run failed in about 2 seconds on every job), so the owner moved the repo; and the PR 143 review suggested writing the size rule down so both roles cite one text.

## Review rounds
- R1 (head d19d33d): Approved, P3 only. Agreed that the image-path change is a separate deep-tier PR and that main's `checks` failure on cecddf3 was a runner DNS failure, not the code.

## Deferred conditions
- None. P3s, open: (1) the "still open" list of old-organization paths is incomplete: also `infra/host/env/staging.env:51`, `docs/runbooks/host-rebuild.md:587, 597, 623`, and the fixtures `infra/host/tests/test_check_hardening.py:96`, `test_compose_config.py:453`; the image-path PR works from `git grep -e 'ghcr.io/skiw-platform' -e 'skiw-platform/skiw-platform'` outside DECISIONS, not from the entry's list; (2) merging as written set the stop line at **600** (PR 142's body said 550; PR 143 went past both before the rule existed; the owner accepted by merging); (3) wording nit: say "added lines" instead of "LOC".

## Decisions worth keeping
- The repo is `skiw-dev1/skiw-platform`; use `--repo skiw-dev1/skiw-platform`.
- `publish` pushes with the repository's `GITHUB_TOKEN`, which cannot write another organization's packages: it is expected to fail at the push on the new organization until the image paths follow the repo. Nothing is deployed yet, so the red costs nothing; it is a known red on `main`.
- Size rule: 400 target, about 450 split-or-say-why, 600 stop and ask.

## Follow-ups
- **Next PR, deploy path, deep tier, own PR:** move the image paths (`ci.yml` `publish`, `infra/host/env/{ci,staging,production}.env`, `deploy.md`, `ci.md`, `host-rebuild.md`, the M1 plan, test fixtures) to the new organization; do it after a real `publish` run shows what the new token may push, or decide with the owner whether the images move to `ghcr.io/skiw-dev1/...`.
- Then M3i (first frontend PR: ask the owner first) and M3g, then the M3 gate review (deep tier).
- PR 143 P3 regenerate `hold` race test; PR 139 P3 (permission matrix, M4-rest); PR 140 P3s and the `apk add` layer removal; PR 140 review tier gap (standard instead of deep, no owner reply).
- Progress page: no milestone change; not republished.

## Appendix — final review round
# Review — PR #147 (docs: repo moved to skiw-dev1, PR size rule text)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 1 — 2026-11-12 · scope: docs (`agents/PROJECT.md` §4 Remote and a new PR size rule line; `docs/DECISIONS.md` 2026-11-11 entry; no code, test, workflow or config)
- **Code review:** base (merge base) cecddf3728c7a4b36ce5c932b3e017a672d66098 (= `origin/main`, PR 143 merged) · head d19d33d0d241799dc422eca95a212e517c1fbbe5 · one commit · +11/−1 over 2 files · head re-checked at end: yes (PR open, main unmoved)
- **Spec:** v1.22 unchanged by this PR. Source for the size rule: spec §9 "PR size target ≈ 400 LOC"; PR 143 R1 P3 note (write the rule down). Source for the remote: owner's move (the PR 143 CI billing failure).
- **CI:** green on this head: `checks`, `security`, `image`, `host` success; `publish`, `deploy-staging` skipped (PR event).
- **Checks run by the reviewer:** read the diff from git objects (docs only, so no checkout, DB or test run was needed beyond CI); `git diff --check` clean; secret-scan pattern on added lines: only the prose word `GITHUB_TOKEN`, no value; `git remote -v` is `skiw-dev1/skiw-platform`; PR sizes 141/142/143 re-read with `gh` (+488/−9, +521/−34, +665/−39, matching the entry); main run 43057339061 on `cecddf3` (attempt 2): `checks` failed at "Install browser" with `Temporary failure resolving 'azure.archive.ubuntu.com'`, the other gates green, `publish` skipped (matches the PR's claim); `git grep` for the old organization's paths across the head tree (results below).

**Verdict:** Approved. Findings are P3 only. One owner choice is surfaced (550 or 600 as the stop line); merging the text as written chooses 600.
**Model used:** Claude Opus 5.5 · **Switch model next step?** No for this PR. The follow-up image-path PR touches the deploy path and should be built and reviewed on the deep tier, as the PR itself says.

### Applicability (reviewer's own list)
UNI-07 (no secrets added: met, CI `security` green and the diff holds none), UNI-13 (CI green on the head: met), UNI-16 (docs describe what is true: partial, see P3 #1). All other UNI, AUTH, TEN, FE, MON, REC, FILE and EVT rules: n/a (no code, schema, route, workflow or config change). I agree with the PR's self-check, except UNI-16 is partial rather than pass.

### Findings

### [P3] #1 The "still open" list of old-organization paths is incomplete
- Category: docs accuracy
- Rule: UNI-16
- Evidence: the DECISIONS entry (and the PR body) list `ci.yml`, `infra/host/env/{ci,production}.env`, `deploy.md`, `ci.md` and the M1 plan. `git grep` at the head also finds `infra/host/env/staging.env:51` (`SKIW_IMAGE_REPOSITORY`), `docs/runbooks/host-rebuild.md:587, 597, 623` (`gh … --repo skiw-platform/skiw-platform`), and the fixtures in `infra/host/tests/test_check_hardening.py:96` and `test_compose_config.py:453`.
- Failure scenario: the follow-up deploy-path PR works from this entry as its checklist and misses `staging.env`. Staging would then pull from the old organization's package path after `ci.yml` and `production.env` have moved, and the operator steps in `host-rebuild.md` would still point `gh` at the old repo.
- Required correction (here or in the follow-up PR; either is fine): add the missing files to the entry, or replace the list with "every hit of `git grep -e 'ghcr.io/skiw-platform' -e 'skiw-platform/skiw-platform'` outside `docs/DECISIONS.md`".

### [P3] #2 The 600 stop line contradicts the line used before; PR 143 went past it without asking the owner
- Category: decision record
- Evidence: the PR body says "The 600 stop line is the one I have been using in briefs; it was not written anywhere before." The PR 142 body says "over the 450 split point, under the **550** stop line". PR 143 (+665) went past both. It offered the split to the reviewer ("Say if you want regenerate split off anyway"), not to the owner. The entry says the reviewer accepted PRs 141 to 143, which is true, but under the rule as now written, PR 143 needed the owner's yes first.
- Why it matters: the rule was written down because the two roles cited different lines. The text adds a third origin story for the number.
- Required correction: none from the builder unless the owner wants it. **Owner choice:** merging as written sets 600. If you meant 550, say so and the builder changes one number. Optional: one clause in the entry saying PR 143 exceeded the new stop line before it existed, and that the owner accepts it by merging.

### [P3] #3 Wording nits (optional)
- "LOC (code, tests and docs together)" does not say added or changed lines. Every PR so far has cited additions (+488, +521, +665). Suggest "added lines (code, tests and docs together)".
- "a larger PR is not itself a finding" is fine as long as the reviewer still judges the stated reason, which the same sentence says. No change needed.

### Builder's questions
- **Leaving the image paths for a separate deep-tier PR:** agreed. `publish` uses the repository `GITHUB_TOKEN`, which cannot write packages owned by another organization, so the first green push to `main` should fail at the push. Nothing is deployed yet (no VPS, staging deploy gated by `SKIW_STAGING_DEPLOY`), so the red `publish` costs nothing. It is a known red on `main` until the follow-up merges; the owner should expect it.
- **Main's `checks` failure on `cecddf3`:** confirmed: a runner DNS failure in "Install browser", not the code. A re-run of main or the next push to main should clear it.

### Verification performed
Diff read in full; `git diff --check`; secret pattern on added lines; old-org `git grep` over the head tree; PR sizes and the PR 142/143 bodies re-read; main CI run log inspected; CI status on this head. Not run locally: lint, tests, gitleaks (CI covers them, and the diff has no code).

### Residual risks
- `main` will show a failed `publish` after its next green `checks` until the image-path PR merges.
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
