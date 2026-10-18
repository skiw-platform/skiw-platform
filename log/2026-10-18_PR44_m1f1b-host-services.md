# PR 44 — feat(infra): apply makes users, installs pinned Docker packages and reloads changed services (M1f-1b)

- **Merged:** 2026-10-18T00:59:31Z (GitHub) · **Merge commit:** `e9861c04866c27e621d8064be0af19c0d7a558ac` · **Branch:** `feat/m1f1b-host-services` (final head `0d5626e960222d3585e70e83987be40aa42df3cf`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-44.receipt` on `agent-logs` (written before the merge); names head `0d5626e…`, review `reviews/PR-44.md`, CI green on that exact head (run 39084189072: checks, host, image, security).
- **Merge evidence:** `gh pr view 44` → MERGED, mergedAt 2026-10-18T00:59:31Z, merge commit `e9861c0`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 0d5626e origin/main` succeeded; `origin/main` log shows `e9861c0`, `0d5626e`, `c4f983e`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier; deploy-log hardening and the Round 1 fixes by the builder) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1f-1b (second part of the first half of plan M1f)

## What changed
After the files, `apply` converges the system. It checks first and changes nothing on a refusal (exit 2): the PR 42 checks plus Docker's apt key (root-owned, not a link, not writable by others, exactly one primary key with fingerprint `9DC858229FC7DD38854AE2D88D81803C0EBFCD88`). Reloads owed are written to `/var/lib/skiw/apply.pending` before any file is installed and removed only after every reload succeeds, so a run that failed (exit 1) can be repeated. It makes the users `skiw-deploy` and `skiw-ops` (the latter in `sudo`; either one found in group `docker` is removed from it), installs `docker-ce` and `docker-ce-cli` `5:29.9.1-1~ubuntu.24.04~noble` and `docker-compose-plugin` `5.6.0-1~ubuntu.24.04~noble` plus `nftables` and `unattended-upgrades` (and `fail2ban` under that policy), enables the units, switches ssh from `ssh.socket` to `ssh.service`, and reloads only services whose file changed (`nft -f`, ssh, docker, journald, fail2ban). `bootstrap-db prepare` and `apply` write one value-free line to the journal and the deploy log (exit 3 if that step fails after the work). The deploy-log write (`bootstrap_secrets.record`, shared by both scripts) now uses `O_NOFOLLOW` and refuses an unsafe directory or file. Runbook Host section, DECISIONS entry (2026-10-17). 404 lines at the first head; pytest 219, host tests 139.

## Review rounds
- R1 (Revision required): [P1] fail2ban was only enabled and try-restarted, so an installed but stopped service stayed stopped while `apply` returned 0 → started when the policy selects it and it is not active (also on a no-change run), not started under `allowlist`, a failed start is retried. [P1] UNI-14 missing from the self-check → row added (signed repository, key fingerprint, exact pins, older, newer and matching cases, `containerd.io` unpinned by design). [P2] a newer installed Docker could not go back to the pin because apt refuses a noninteractive downgrade → only the three pinned packages are installed with `--allow-downgrades`, in their own call; the others never get the flag. The test model now keeps service state and models apt's refusal.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **M1f-2 (next):** `check-hardening` (effective sshd settings; nftables ruleset equals the rendered file; unattended-upgrades enabled; Docker daemon config; listening sockets only on 80, 443 and the SSH port; secret-file owners and modes; no secret in any container environment; `skiw-deploy` and `skiw-ops` not in group `docker`; the role set), the HBA-versus-env check, and stale-file handling (for example removing fail2ban itself, and Ubuntu's default jail, under an allow-list, which is still an open question for the owner).
- **Owner values still open:** G7 (SSH port; allow-list or fail2ban), G15 (reboot values), G4 (Ubuntu 24.04 assumed). `apply` refuses on staging and production until G7 and G15 are filled in. `skiw-ops` gets its password and SSH key by hand.
- **Not proven, needs a real Ubuntu 24.04 host (M1k):** that the `ssh.socket` switch keeps sshd and open sessions up; how `try-restart fail2ban` behaves with a missing unit; real `gpg --with-colons` and `dpkg-query` output; `sshd -t` needing `/run/sshd`; `live-restore` across a Docker restart. The apt and systemd rules are modelled from their documentation in tests, not run natively.
- Lesson kept: the fake runners missed both service state and apt's downgrade refusal until the reviewer probed them; model the real tool's failure rules, not unconditional success.
- Open owner side question (not in M1): host on the VPS or on the client's Mac Studio (spec D3).
