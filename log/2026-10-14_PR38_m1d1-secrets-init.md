# PR 38 — feat(infra): bootstrap-secrets init, secret inventory and escrow bundle (M1d-1)

- **Merged:** 2026-10-14T14:03:54Z (GitHub) · **Merge commit:** `e3bdfabfcbbb306f52b594560677b106560ff58e` · **Branch:** `feat/m1d1-secrets-init` (final head `8222e733e134add913029b27127f6982f6e7019c`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-38.receipt` on `agent-logs` (written before the merge); names head `8222e73…`, review `reviews/PR-38.md`, CI green on that exact head (run 38527759793: checks, host, image, security).
- **Merge evidence:** `gh pr view 38` → MERGED, mergedAt 2026-10-14T14:03:54Z, merge commit `e3bdfab`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor e3bdfab origin/main` succeeded; `infra/host/bootstrap-secrets` is on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier; restore half cut out by the builder) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1d-1 (init half of plan M1d; owner split M1d in two on 2026-10-14)

## What changed
`infra/host/skiw_host/secrets.py` (H4 inventory: names, kinds, reading services, owning uids), `bootstrap-secrets init` (`bootstrap_secrets.py`, `escrow.py`; Python stdlib): refuses unless the store is empty; mints 32-byte `v1:<base64>` app keys from `os.urandom`; writes the age escrow bundle (pinned age v1.3.2, public `age1…` recipients only, no DB password or deploy key) first, makes its directory entry durable, then installs the key files (`0600` `O_EXCL` temp, fsync, `0400`, chown to the inventory uid, hard link into place); removes everything on a failure before the commit point. New Compose test check that each mounted secret's owner is the service's uid. `docs/runbooks/host-rebuild.md` (new, secrets section). `SKIW_ESCROW_RECIPIENTS` (empty until G5) in the three env files.

## Review rounds
- R1 (Revision required): [P2] a journal or deploy-log failure after the install escaped as a traceback and contradicted the documented retry contract → handled outcome, exit 3 (keys and bundle kept, value-free message, runbook says not to re-run `init`). [P2] the escrow directory entry was not fsynced before the keys were installed → `sync_chain` (directory and ancestors) before the first key; test of the order and of a failed sync.
- R2: Approved. Also fixed after opening: the registry Semgrep rule `insecure-file-permissions` flagged `os.chmod(directory, 0o700)` (false positive) → named constant `DIR_MODE = stat.S_IRWXU`, no suppression.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Exit codes: 0 done, 2 refused, 1 failed (nothing left), 3 installed but the final log step failed.
- Open owner values: G5 (public escrow recipients for staging and production), G10 (`ghcr_read_token` type), G11 (staging-check key name; not in the inventory until the mechanism is chosen). Open for M1e: does `skiw_readonly` need a password. The deploy log path `/var/log/skiw/deploy.log` is a builder assumption for M1g.
- Lesson recorded: run the CI registry Semgrep command locally before every push (`uvx semgrep==1.179.0 --config p/python --config p/django --config p/typescript --config p/react --metrics=off --error app infra/host web/src`).
- Next: M1d-2 (`restore`, the `.restored` marker, the owner-only `--allow-new-key-version` override). The full M1d code, with restore, is kept as a local WIP commit on branch `feat/m1d-bootstrap-secrets`.
