# PR 25 — chore(infra): M1a host scaffold, CDK removal, gitleaks key names

- **Merged:** 2026-10-13T03:08:41Z (GitHub) · **Merge commit:** `c0824b9d9b9eda86e1851d1174c5e61522bcaa55` · **Branch:** `chore/m1a-host-scaffold` (final head `38cb7d05fc73d59566a9de9243f394d279361ba6`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-25.receipt` on `agent-logs` (written before the merge); names head `38cb7d0…`, review `reviews/PR-25.md`, CI green on that exact head (run 38334879328: checks, host, image, security).
- **Merge evidence:** `gh pr view 25` → MERGED, mergedAt 2026-10-13T03:08:41Z, merge commit `c0824b9`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor c0824b9 origin/main` succeeded; `infra/app.py` and `infra/cdk.json` are absent on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1a of the M1 plan (PR 24)

## What changed
The AWS CDK skeleton, its dependency group and CI job are gone. New `infra/host/skiw_host/` package (Python stdlib only) and `infra/host/tests/` (`test_layout.py`, `test_gitleaks_config.py`). `make host-test` (unit only), `make host-test-live` (honest stub), `make secrets-test`; CI job `host`; security job runs the secrets test. `.gitleaks.toml` gains `lookup_decoy_key`, `field_kek`, `blind_index_key`, `crm_jar_kek`. New import-linter contract. `.env.example`, Dependabot `docker-compose` entries and stale runbook lines updated. DECISIONS entry 2026-10-13 records G1 (11 PRs) and the Hostinger comparison in the vendor gate.

## Review rounds
- R1 (Revision required): [P1] UNI-01 missing from the self-check → row added. [P2] test-only `Any` annotations unexplained → comment added.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- No `infra/host/tests/__init__.py` (mypy duplicate `tests` module); a host test file cannot share a filename with a file in `app/tests/`.
- Owner chose option 1 on 2026-10-13: iCore stays; Hostinger (VPS only; Web App hosting is Node.js only) is compared in G-VENDOR (M1k) with the same written questions.
- Follow-ups: tiny docs PR replacing the `pending M1` line in `agents/PROJECT.md` section 7 with `make host-test` / `make host-test-live`; Dependabot `/infra/host` is proven only once M1b adds `compose.yml`; owner gates G2 to G17 remain open.
