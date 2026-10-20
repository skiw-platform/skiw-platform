# PR 45 — feat(infra): check-hardening framework and the sshd, nftables, upgrades, Docker, socket, group and stale-file checks (M1f-2a)

- **Merged:** 2026-10-20T03:53:45Z (GitHub) · **Merge commit:** `d80170bbb3399c7308882895efefc06b22ea2b2c` · **Branch:** `feat/m1f2-check-hardening` (final head `a4316581b06618f1d5b88a186d265ed08c67eaa8`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-45.receipt` on `agent-logs` (written before the merge); names head `a431658…`, review `reviews/PR-45.md`, CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 45` → MERGED, mergedAt 2026-10-20T03:53:45Z, merge commit `d80170b`, final head equals the reviewed head of Round 5; `git merge-base --is-ancestor a431658 origin/main` succeeded; `main` log shows `d80170b`, `a431658`, `e87866a`.
- **Drafted by:** Claude Sonnet 5.5 (builder; first code by an Opus subagent, deep tier; all review fixes by the builder) · **Final verdict:** Approved (Round 5; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1f-2a (first half of plan M1f-2)

## What changed
`infra/host/check-hardening` is a read-only command that prints one PASS or FAIL line per check (exit 0 all pass, 1 any fail, 2 refused). Checks: sshd (effective `sshd -T` values; no `Match` block sets a checked key, also under its old name; only the drop-in `Include`), nftables (ruleset equals the rendered file), unattended-upgrades (security origins only), docker-daemon (file, live `SecurityOptions`, start line), listening sockets (80, 443, SSH port; no `dockerd` TCP listener), docker group (`skiw-deploy` and `skiw-ops` not in it), stale files. Files are read with `O_NOFOLLOW`; owner, mode and directory chain are checked. `apply` installs the command. Runbook table and DECISIONS entry (2026-10-19). 798 lines added.

## Review rounds
- R1 (Revision required): [P1] `Match` blocks hid weaker SSH values → closed-policy scan. [P1] Docker file values could pass while the live daemon differed → live `SecurityOptions` and start-line parse. [P1] named apt origin entries bypassed the security-only comparison → whole origin subtrees validated.
- R2: [P1] `ChallengeResponseAuthentication` is the old name of `KbdInteractiveAuthentication` and evaded the scan → alias map.
- R3 and R4 (R4 was an unchanged-head recheck): [P1] quoted SSH keywords (`"PasswordAuthentication"`, `"Match"`, `"Include"`) evaded the scan → any keyword with a quote or backslash fails closed, in the main file and every drop-in.
- R5: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **M1f-2b (next):** secret-store, container-env (16-character minimum accepted), role-set (needs `--compose-file`; the compose path is decided in M1g) and pg-hba checks. The parts are saved outside git and re-applied on this framework.
- **Owner values still open:** G7 (SSH port; allow-list or fail2ban), G15 (reboot values), G4 (Ubuntu 24.04 assumed). `apply` refuses on staging and production until G7 and G15 are filled in. Open question: should `apply` remove fail2ban fully under an allow-list.
- **Not proven, needs a real Ubuntu 24.04 host (M1k):** every check ran against fixtures and tool-output models; native `sshd -T -C` quoted and alias cases were proven by the reviewer on macOS OpenSSH only.
- Lesson kept: a text scan of a config the real tool parses must either follow the tool's grammar or fail closed on any form it does not understand (aliases and quoting each cost a round).
- Open owner side question (not in M1): host on the VPS or on the client's Mac Studio (spec D3).
