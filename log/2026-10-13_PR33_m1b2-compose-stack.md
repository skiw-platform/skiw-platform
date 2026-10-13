# PR 33 — feat(infra): host Compose stack and Compose config tests (M1b-2)

- **Merged:** 2026-10-13T13:52:35Z (GitHub) · **Merge commit:** `3f3f74f7fe28bbee7cf781e7cd5af77acd90cb18` · **Branch:** `feat/m1b2-compose-stack` (final head `05b190b2f4f0be988a16e64ac8becb8328c1093e`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-33.receipt` on `agent-logs` (written before the merge); names head `05b190b…`, review `reviews/PR-33.md`, CI green on that exact head (run 38406280580: checks, host, image, security).
- **Merge evidence:** `gh pr view 33` → MERGED, mergedAt 2026-10-13T13:52:35Z, merge commit `3f3f74f`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 3f3f74f origin/main` succeeded; `infra/host/compose.yml` is on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1b-2 (host part of plan M1b)

## What changed
`infra/host/compose.yml` (project `skiw`: `caddy`, `web`, `worker`, `migrate` [profile `deploy`], `db`, `clamav`, `backup` [profile `ops`]; networks `edge`, `app`, `ops`, `egress`; only Caddy publishes 80 and 443; file secrets from `/etc/skiw/secrets/`; images pinned by digest), env files `infra/host/env/{ci,staging,production}.env` (hostname and worker timeouts empty on hosts, so Compose refuses to render them until set), and `infra/host/tests/test_compose_config.py` (now part of `make host-test`, 30 tests). Local-dev runbook host-test row and DECISIONS entry M1b-2.

## Review rounds
- R1 (Revision required): [P1] TEN-01 missing from the self-check → row added. [P2] named hardening exceptions allowed arbitrary values → exceptions bounded (Caddy only `NET_BIND_SERVICE`; ClamAV only its five capabilities; `migrate` and `backup` keep `restart: "no"`), four planted tests added.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Digests resolved 2026-10-13: Caddy `2.11.7-alpine` `sha256:d8542f48…`, ClamAV `1.5.4` `sha256:638d9020…` (amd64 only), Postgres `17.11` `sha256:d74eeac9…` (equal to `docker-compose.yml`; the tag now points to a newer index `2d2b8998…`; bump both files together later).
- Not proven yet: the real stack was never started. Secret mounts (M1d), `caddy-data` writability by uid 10002 and TLS (M1c), ClamAV outside emulation (M1i), host proof (M1k).
- Builder assumptions to confirm or replace: subnets `172.31.10-13.0/24` (hosts) and `172.31.20-23.0/24` (CI), uids 10001/10002/10003, pids limits, staging memory limits, secret file names for M1d.
- Open owner gates: G9 hostname, G13 Caddy ports (a non-root Caddy bound port 80 locally because Docker sets `net.ipv4.ip_unprivileged_port_start=0` in containers).
- Follow-up: `agents/PROJECT.md` section 7 `pending M1b` line becomes a note that `make host-test` includes the Compose config tests.
