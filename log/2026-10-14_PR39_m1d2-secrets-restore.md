# PR 39 — feat(infra): bootstrap-secrets restore and the owner-only key-version override (M1d-2)

- **Merged:** 2026-10-14T15:06:10Z (GitHub) · **Merge commit:** `6785ceb82537cbeab1f91a936b8e42eebb30cf40` · **Branch:** `feat/m1d2-secrets-restore` (final head `6270bced52aef3c3dcad9435be57a0ab30373948`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-39.receipt` on `agent-logs` (written before the merge); names head `6270bce…`, review `reviews/PR-39.md`, CI green on that exact head (run 38580321782: checks, host, image, security).
- **Merge evidence:** `gh pr view 39` → MERGED, mergedAt 2026-10-14T15:06:10Z, merge commit `6785ceb`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 6785ceb origin/main` succeeded; `restore` is in `infra/host/skiw_host/bootstrap_secrets.py` on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1d-2 (restore half of plan M1d)

## What changed
`bootstrap-secrets restore --env-file <env>` reads the decrypted escrow bundle on stdin, validates everything in memory (format, inventory closure, every app key present, well-formed and non-repeated versions, SHA-256, at least 32 bytes), then writes a fresh escrow bundle, makes its directory entry durable, installs every version verbatim and writes the `.restored` marker (root, `0400`; the last file before the commit point). `init` and `restore` refuse when the marker exists or the store is not empty. `--allow-new-key-version NAME` (restore only, app keys only) appends one new newest version minted from `os.urandom`, recorded by name and version on stderr, in the journal and in the deploy log. A final log failure after the commit point exits 3 with everything kept. Runbook restore section, DECISIONS entry (M1d-2). 14 new tests (63 host tests).

## Review rounds
- R1 (Revision required): [P2] the runbook's streamed restore (`ssh ... sudo bootstrap-secrets restore`) cannot run: no terminal for `sudo`, and stdin is the plaintext bundle → the command is now conditional (`ssh -T ... sudo -n ...`) with a `sudo -n -l bootstrap-secrets` preflight before decrypting, and the narrow noninteractive `sudoers` prerequisite is staged to M1f (provision) and M1k (prove).
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **M1f must provision** the narrow `sudoers` rule for the installed `bootstrap-secrets` only (no global passwordless `sudo`, no root login, no password in the stream) and test that a missing rule refuses with no store change; M1k proves it on both hosts. The plan's M1f section does not list it yet.
- An override makes data encrypted or signed under a lost key version permanently unreadable; the owner decides each use and records it (date, host, which bundle, each overridden key and its version, why the key was lost, the off-host copy).
- Open owner values: G5 (public escrow recipients), G10 (GHCR token type), G11 (staging-check key name). Real `age`, the owner's recipients, the off-host copy and a restore on a fresh VPS are M1k.
- The unsplit WIP commit `873f7d3` is in the history of PR 38 (the init-only branch started from it and a later commit cut the restore half); main therefore also contains that transient commit. No secret was in it. The local scratch branch `feat/m1d-bootstrap-secrets` pointed at it and was deleted after the merge.
