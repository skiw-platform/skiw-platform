# PR 42 — feat(infra): host config templates, apply for files and the restore sudoers rule (M1f-1a)

- **Merged:** 2026-10-17T06:58:06Z (GitHub) · **Merge commit:** `f3ecd62bd8a5e7f160c7520ce895f4dc2855fc99` · **Branch:** `feat/m1f1-host-install` (final head `6892a4dba299e29ebe16303f93ecc9ee5bb99f86`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-42.receipt` on `agent-logs` (written before the merge); names head `6892a4d…`, review `reviews/PR-42.md`, CI green on that exact head (run 38914167913: checks, host, image, security).
- **Merge evidence:** `gh pr view 42` → MERGED, mergedAt 2026-10-17T06:58:06Z, merge commit `f3ecd62`, final head equals the reviewed head of Round 5; `git merge-base --is-ancestor 6892a4d origin/main` succeeded; `origin/main` log shows `f3ecd62`, `6892a4d`, `49138ef`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier; ownership, directory and creation-time fixes by the builder) · **Final verdict:** Approved (Round 5; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1f-1a (files half of the first part of plan M1f)

## What changed
`infra/host/apply --env-file <env>` checks every host value, renders the templates (`nftables.conf`, `sshd/00-skiw.conf`, `docker/daemon.json`, `apt/52skiw-unattended`, `journald/skiw.conf`, `fail2ban/jail.local`, the sudoers rule), runs `nft -c`, `sshd -t` and `visudo -c` on scratch copies, and installs only what differs, root-owned with named mode constants. It also installs `bootstrap-secrets`, `bootstrap-db`, `skiw_host/`, `db/` and the templates under `/usr/local`. New host keys in `env/*.env` (`SKIW_SSH_PORT`, `SKIW_SSH_POLICY`, `SKIW_SSH_ALLOW`, rates, `SKIW_AUTO_REBOOT`, `SKIW_JOURNAL_MAX_USE`); staging and production leave the port, policy and reboot values empty, so `apply` refuses there. The sudoers rule is `skiw-ops ALL=(root) NOPASSWD: /usr/local/sbin/bootstrap-secrets restore --env-file /etc/skiw/host.env` with no wildcard. Runbook Host section, DECISIONS entry (2026-10-15). 36 tests in `test_apply.py`; 197 pytest, 117 host tests.

## Review rounds
- R1 and R2 (Revision required; R2 repeated R1 because no fix had been pushed): [P1] a file with matching bytes and mode but a non-root owner counted as unchanged → content, mode, uid and gid must all match, links are replaced, and a directory that is a link or not `root:root` is refused.
- R3 (Revision required): [P1] a root-owned directory writable by group or others was trusted → refused before any install; new directories are made 0755 under any umask.
- R4 (Revision required): [P1] a new directory was writable between `mkdir` and `chmod` under umask 000, so a local user could plant a link → `mkdir(mode=0o755)` in the call itself; a link found at a path being created is refused.
- R5: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **Owner values still open:** G7 (SSH port; allow-list or fail2ban), G15 (reboot values), G4 (Ubuntu 24.04 is an assumption). `apply` refuses on staging and production until G7 and G15 are filled in.
- **M1f-1b (next):** users `skiw-deploy` and `skiw-ops`, taken out of group `docker`; Docker apt key fingerprint check, pins (docker-ce 29.9.1, compose plugin 5.6.0) and install; enabling units; the `ssh.socket` switch; service restarts after file changes; the `bootstrap-db` journal and deploy-log line. Decide fail2ban from `host_values()`, not from `SKIW_SSH_ALLOW`. The earlier unsplit patch (scratchpad `m1f1b-parts.patch`) predates `SKIW_SSH_POLICY`.
- **M1f-2:** `check-hardening`, the HBA-versus-env check, stale-file handling (for example the fail2ban jail after a switch to an allow-list).
- Rates (SSH 10/minute, web 30/second) and the journal caps (4G production, 2G staging) are builder values to measure in M1k. `age` v1.3.2 is a manual runbook step.
- The reviewer's root-run checks in Ubuntu 24.04 are the real host-style proof for this slice; a full host run is M1k.
- Tooling note: during the R3 fix `grep` in the builder's shell printed a "claude native binary not installed" error instead of output; results were read with Python instead. No repo effect.
