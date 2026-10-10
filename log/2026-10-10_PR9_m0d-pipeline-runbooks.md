# PR 9 — ci(m0d): security, image and infra gates, web build stage, runbooks

- **Merged:** 2026-10-10T02:26:25Z (GitHub) · **Merge commit:** `a305a2bc6f6fe90caa391276cb82eca2b54eb4dd` · **Branch:** `ci/m0d-pipeline-runbooks` (final head `2f2b68a0eb53601d8ec387072d2b8ee79a86d0d1`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-9.receipt` on `agent-logs` (commit `464cb5a`, written 2026-10-10T02:25:36Z, 49 seconds before the merge); names head `2f2b68a…` and review-file hash `28b3f015c98e468748e8cb6ebdd6b87f589b8263`, and records CI green on that exact head (run 37948273073); the archived review `reviews/PR-9.md` (log-branch commit `78efdc6`) has the same hash.
- **Merge evidence:** `gh pr view 9` → state MERGED, mergedAt 2026-10-10T02:26:25Z, merge commit `a305a2b`, final head `2f2b68a` (equals the reviewed head of Round 2); `git merge-base --is-ancestor a305a2b origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder; implementation by a Sonnet 5.5 subagent) · **Final verdict:** Approved (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8 (`67e36a52…`) · **Plan:** `docs/plans/2026-10-05-m0-scaffold.md` · **Milestone:** M0d (completes M0)

## What changed
CI jobs `security` (gitleaks v8.30.1 binary with checksum, full history; pip-audit; pnpm audit; Semgrep registry packs, anonymous), `image` (docker build, Trivy v0.75.0 failing on any HIGH/CRITICAL) and `infra` (CDK synth test); a Node 24 web build stage and `shell.verify_dist` manifest check in the image; the runtime base moved to `python:3.12.15-alpine` (digest-pinned), `uv`/`uvx` no longer shipped; named `ASSET_CACHE_SECONDS`; `.gitleaks.toml`, `.github/dependabot.yml`, the pre-push gitleaks hook (`make hooks`), runbook skeletons plus a filled `docs/runbooks/ci.md`, the `infra/` CDK skeleton, `extension/README.md`, `agents/PROJECT.md` section 7 commands, and the decisions entry for the GitHub Free plan limits.

## Why
Closes M0: UNI-13 (CI gates), UNI-07 (secret scanning), and the PR 2 review conditions (image web build stage, manifest verification, cache constant). Owner decision 2026-10-10 (option A): private repo on GitHub Free; branch protection, push protection, CodeQL and dependency-review are unavailable and not relied on (answers ASK-3 and ASK-4). Dependabot alerts and security updates were enabled on the owner's instruction.

## Review rounds
- R1 (Revision required): [P1] the gitleaks `docs/specs/**` exemption hid secret-value assignments there → removed; fixtures prove names pass and values fail in `docs/specs/`, `docs/plans/` and `app/`. [P1] `ignore-unfixed` weakened the approved Trivy gate → removed everywhere; runtime base moved to Alpine (0 HIGH/CRITICAL vs 44 on Debian slim) rather than adding a waiver. [P2] `docs/runbooks/ci.md` misstated the merge gate and Pro entitlements → corrected (`2f2b68a`).
- R2: Approved.

## Deferred conditions
- none introduced. Standing: M4 worker-enqueue spec-change PR (from PR 8); M1 production secret manager and TLS flag validation; M2 CSP nonce; Q32 queue isolation and retention.

## Decisions worth keeping
- No GitHub-enforced merge gate on Free: merge discipline is the kit gate. Builder working rule: confirm green CI on the exact head before `approved N` (receipts now record the CI run). The kit's `START.md` does not state it; the owner decides on a kit change.
- Trivy fails on any HIGH/CRITICAL, fixed or not; no suppression file. A new unfixable finding means a new base digest, removing the package, or a different base; accepting one needs an owner-approved, reviewed policy with per-finding assessment.
- gitleaks custom rule `skiw-secret-key-assignment` has no path exemption.
- CI gitleaks detects only after push; the pre-push hook is local and bypassable. A stale remote-tracking ref of a deleted scratch branch made local gitleaks see a planted FAKE value until `git fetch --prune`.
- All M0d decisions are in `docs/DECISIONS.md` (entry 2026-10-10).

## Follow-ups
- Optional (reviewer): add a `docker-compose` ecosystem entry to Dependabot so the pinned `postgres` digest is updated.
- Owner: `! brew install gitleaks` then `make hooks`; decide on a kit change for the explicit green-CI check.
- M0 is complete. Next: M4 worker-enqueue spec change; M1 plan; UI kit decision (emilkowalski/skills, shadcn/ui, SmoothUI) with a spec D2 change; API Anything / FAME spike stays parked.

## Appendix — final review round
## Round 2 — 2026-10-10 · scope: slice (M0d security fixes and Alpine runtime)
- **Code review:** base (merge base) `a70d1e1656a2461962b035b815676cb40ac0d662` · head `2f2b68a0eb53601d8ec387072d2b8ee79a86d0d1` · host head re-checked at end: yes; unchanged and OPEN.
- **Spec:** v1.8 at `docs/specs/2026-10-05-skiw-platform-stack-design.md`, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, unchanged.
- **Mode:** exact-head snapshot `.agent/worktrees/review-9-2f2b68a0`; fetch denied by read-only .git/FETCH_HEAD; target commit already local. Host main confirmed base. Source integrity checked against commit file hashes before removal. Exact image built from git archive of the reviewed SHA, with a review-only tag. Disposable tmpfs databases/networks/containers used for image tests and removed; review image tag removed. No builder stack, worktree, branch or database altered.

**Model used:** Codex GPT-6 · **Switch model next step?** No for archive/merge; M1 infra/security planning retains the project's deep-tier requirement.

### Findings
No blocking findings or new defects. Both P1 findings and the P2 before-merge finding from Round 1 are resolved.

#
