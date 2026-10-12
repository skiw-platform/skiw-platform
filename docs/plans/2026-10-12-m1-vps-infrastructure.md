# Plan — M1 VPS infrastructure, deploy automation and vendor gate

- Spec section: §9 M1 (also §8.4 H1–H14, D3, D4, D14, D15, D17, D22, D23, T16, T17, T23–T25, §8.2, §8.3, §9 "Blocked until", Appendix C) · spec v1.18, hash `0edfb3cd` (`0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`, review Round 21 Approved, PR 22 merged 2026-10-12) · `agents/PROJECT.md` reconciled to v1.18 (PR 23) · Milestone: M1 · Target LOC: ≤ 400 per PR (excluding `uv.lock` and other generated files)
- Author: Builder (deep tier), 2026-10-12. Versions and upstream facts checked 2026-10-12 (§2).
- **Status (2026-10-12):** nothing is built. No PR of M1 is open. No VPS has been bought. G-VENDOR, G-S1, G-DRILL, G-LOAD and G-BACKUP have not run and have not passed. The CDK skeleton under `infra/` is still in the repository.

## 0. Gate before any code (builder §8)

M1 is the first PR of a new milestone, adds a new top-level package (`infra/host/`) and a new module (`documents.storage`), so the owner's yes is needed before M1a starts (builder §8). Each item below says whether it blocks, and from which PR. "Blocks building" means no code can be written; "blocks the real-host step" means the PR can be built and tested in CI but its acceptance on a real VPS waits. Recommendations are the builder's; no answer is assumed.

| # | Decision or action | Blocks | Recommendation | Options (at most 2) |
|---|---|---|---|---|
| G1 | Start M1 with this PR split. The spec says "each milestone is 1–4 PRs" (§9) and also "≈ 400 LOC per PR"; M1 cannot meet both (estimate ≈ 3 300 LOC over 11 PRs). | building (M1a) | (a) | (a) accept 11 PRs of ≤ 400 LOC, all named M1a–M1k; (b) keep 4 PRs and accept PRs of ≈ 800–1 000 LOC |
| G2 | **Q38 — G-VENDOR.** The owner asks iCore Technology Sdn. Bhd. in writing for the eleven H12 items (data centre CJ1/AIMS of the VPS and of any backup or snapshot copy; static IPv4; backup/snapshot options; SLA; terms incl. data deletion and disk wipe; processor terms/DPA; security practice; resource guarantees; portal 2FA/API/rescue console; LUKS or custom image; separate client accounts for staging and production). The builder records the answers, each marked accepted, mitigated or blocking (M1k). | M1k and M1 done; any "blocking" answer returns hosting to the owner. Does not block M1a–M1i. | send the questions now | — |
| G3 | **Buy the VPSs**: staging NODE1 (4 GB, RM 39.90) and production NODE2 (8 GB, RM 59.90), no real data on either. | real-host steps of M1e–M1k | (b) | (a) buy both now under one client account; (b) buy after iCore answers items 1, 8 and 11 in writing (location, no overselling, separate accounts) |
| G4 | **Host OS** (H1: "choice recorded at M1"). | M1f (host config), real-host steps | (a) | (a) Ubuntu 24.04 LTS — standard support to 2029-05-31, ships Python 3.12 (the host scripts are Python stdlib, §1 note); (b) Debian 12 — regular security support ended 2026-07-11, now in Debian LTS to 2028-06-30, ships Python 3.11 |
| G5 | **Q35 key custody, M1 part only.** M1 needs, per environment, the owner's **public** age recipients for the offline **escrow** key (`bootstrap-secrets init` writes the escrow bundle, H4) and for the offline **dump** key (pre-migration dump, H3 step 4). Private keys never reach a host or the repo. | real-host steps of M1c and M1g | separate escrow and dump identities, and separate staging-only identities for staging (synthetic data) | (a) two identities (escrow, dump), as H4/H6 name them; (b) one identity for both |
| G6 | **Deploy keys.** The owner creates (i) the production deploy SSH key on the owner's machine, passphrase-protected, never in GitHub (Q42), and gives the builder only its public key and fingerprint for host config; (ii) the staging deploy key, whose private half the owner stores as a repository Actions secret (`STAGING_DEPLOY_KEY`, T25). | real-host steps of M1g–M1h | as written (Q42 is decided) | — |
| G7 | **SSH port and source policy** (H2 [A], recorded in DECISIONS at M1). | M1f host values | non-default port chosen by the owner; allow-list only if the operator's addresses are stable, otherwise key-only from anywhere plus fail2ban and the nftables limit | (a) allow-list; (b) fail2ban + rate limit |
| G8 | **Q20 alert channel** (H7). The channel is a service outside Malaysia (D19) and not yet authorised (UNI-11), so the health timer cannot send anywhere until it is recorded. External uptime ping: yes or no. | M1j done (alerts) | (a) | (a) email to the owner's mailbox through the agency's existing mail provider; (b) a Telegram bot to the owner |
| G9 | **Q9 domain, DNS and TLS.** Hostnames for staging and production, who edits DNS for `skiwealth.com`, and the ACME CA (Caddy default: Let's Encrypt, with ZeroSSL fallback). | real-host TLS checks (M1b acceptance on hosts, M1k) | the owner names both hostnames; Caddy's default ACME issuers | — |
| G10 | **GHCR package visibility and the host read token** (H3 step 3, "token type confirmed at M1 [A]"). GHCR accepts only a personal access token (classic) [V]; a classic `read:packages` token reads every package the issuing account can read. | M1h | (a) | (a) private package, classic PAT with `read:packages` only, issued by the owner, rotated yearly; (b) public package (no token; exposes the image and its code) |
| G11 | **Staging-check mechanism** (H3 step 3, "mechanism confirmed at M1 [A]"). Production must confirm staging runs the exact digest, healthy, with staging checks passed. Either option adds one name to the H4 secret inventory, recorded in DECISIONS. | M1g | (b) | (a) authenticated `/version` on staging over HTTPS with a bearer token held in both secret stores (spec wording; new app endpoint); (b) a forced-command SSH key on production, `restrict,command="/usr/local/sbin/skiw-staging-status"` on staging, which prints only the last staging state line (no app endpoint, same pattern as the deploy key) |
| G12 | **What "staging checks passed" means** (spec names it, does not define it). | M1g | `skiw-deploy` on staging writes `checks=passed` only after: `/readyz` 200 through Caddy with a valid certificate, worker registered within two heartbeats, migration head equal to the image label | accept, or name extra checks |
| G13 | **Caddy without `NET_BIND_SERVICE`** (tighter than H1). Under the daemon default `no-new-privileges: true` (H2) a non-root process cannot use the file capability the official image sets on `/usr/bin/caddy`. Proposal: Caddy listens on 8080/8443 in the container, Compose publishes 80→8080 and 443→8443, `cap_drop: ALL`. | not blocking (M1b) | accept (recorded in DECISIONS) | — |
| G14 | **File-store harness without the `document` table.** H5 ties the harness to M1, but the `document` table, `with_agency()` and RLS arrive in M4/M16. Proposal: M1 builds `documents.storage` (publish contract, verified open) and tests it against a test-only probe table created in the test session, as M0c did with `jobs_probe`; M16 re-runs the harness on the real table (spec §9 M16). | not blocking (M1i) | accept | — |
| G15 | **Q41 maintenance window**, M1 part: when may production reboot after security updates. | production host values (M1f) | automatic reboot off on production; the health timer alerts "reboot needed" and the owner reboots in the window; staging reboots automatically | (a) as recommended; (b) automatic reboot at a fixed time in the window |
| G16 | **G-LOAD profile** (H12: "[A — profile confirmed in the M1 plan]"). | not blocking | confirm the profile as stated (M14 profile: 50 simulated devices long-polling 5 min; plus 20 concurrent API users; plus one 20 MB PDF scan; production Compose limits). It runs at M14/M6, not in M1, because the long-poll endpoint is M14. | — |
| G17 | **Q34 backup cadence, Q36 off-site, Q37 R2, Q16 retention, Q19 break-glass.** | not blocking M1 | none needed now; M1 touches backups only through the pre-migration dump (§5) | — |

The builder writes no owner answer into code: until G2–G12 are answered, host config values that depend on them are absent and the scripts fail closed when a required value is missing (UNI-02, UNI-03).

## 1. PR split (ordered; each depends on the previous one being merged unless stated)

"VPS" = needs the real host; "CI" = built and accepted in CI without any host or owner action.

| PR | Branch | Needs | Scope | Acceptance test (spec §9 M1 row) | LOC est. |
|---|---|---|---|---|---|
| M1a | `chore/m1a-host-scaffold` | CI | remove the CDK skeleton and the CI `infra` job; `infra/host/` package and test scaffolding with `make host-test` and a CI `host` job; `.gitleaks.toml` new key names + test; Makefile, `pyproject.toml`, `.env.example`, Dependabot `docker-compose`, stale runbook lines | CDK skeleton and its CI job removed (UNI-05); CI runs the new tests on every PR (UNI-13); gitleaks test flags each of the four new names | ≈ 220 (≈ 120 deleted) |
| M1b | `feat/m1b-compose-stack` | CI | `infra/host/compose.yml` (H1 services, networks, fixed subnets, secrets, volumes), per-environment non-secret config, app reads secrets from `/run/secrets` files, `/readyz`; Compose config tests | the Compose config tests listed in §3 M1b | ≈ 390 |
| M1c | `feat/m1c-caddy-edge` | CI (TLS on hosts: VPS + G9) | `infra/host/caddy/Caddyfile`, maintenance page, body cap, proxy timeouts, HSTS on redirect/maintenance/app, `SECURE_PROXY_SSL_HEADER` in deployed settings; a CI stack test through Caddy with an internal CA | UNI-17 through Caddy: HSTS on the redirect, the maintenance page and an app page; client-sent `X-Forwarded-Proto` not trusted; 25 s long-poll completes (stub upstream); oversized body refused (FILE-02 outer cap); on hosts: `/readyz` 200 with a valid certificate and HSTS | ≈ 300 |
| M1d | `feat/m1d-bootstrap-secrets` | CI (host run: VPS + G5) | `infra/host/bootstrap-secrets` `init` and `restore`, inventory, `v<n>:<base64>` files, owners/modes, escrow bundle via `age` | init refuses when any secret or a restore marker exists; restore refuses a missing key and never mints one without `--allow-new-key-version`; values never printed | ≈ 360 |
| M1e | `feat/m1e-bootstrap-db` | CI (host run: VPS) | `infra/host/bootstrap-db` (closed role set incl. `skiw_backup`, `skiw_readonly`, NOLOGIN `skiw_tenant_guard`, `skiw_auth_lookup`), `pg_hba.conf`, local/CI Postgres uses the same role SQL; role-set and `pg_hba` tests | role-set test; each DB role connects only from its network or socket (`skiw_backup` only from `ops`, refused from `app`; `skiw_app` refused from `ops`) | ≈ 380 |
| M1f | `feat/m1f-host-hardening` | CI (host run: VPS + G4, G7, G15) | `infra/host/apply` (idempotent host install), nftables, sshd drop-in, Docker `daemon.json`, unattended-upgrades, fail2ban (if G7 (b)), journald; `infra/host/check-hardening` | `check-hardening` unit tests on fixtures in CI; on hosts: `check-hardening` passes on both; external port scan shows only 80, 443 and the SSH port | ≈ 390 |
| M1g | `feat/m1g-skiw-deploy` | CI (host run: VPS + G5, G6, G11, G12) | `skiw-deploy-ssh` forced command, `skiw-deploy` (validate, lock, pull, pre-migration dump, migrate, switch, health, automatic rollback), production staging check, accepted-digest record, `--rollback`, contract-migration refusal; `infra/host/backup/predeploy` minimal dump image | deploy-script tests in CI with fakes for `docker`, `ssh` and the clock (§3 M1g); on hosts: the deploy key cannot run `id`; malformed digest and foreign repository refused; a failing health check rolls back automatically | ≈ 400 |
| M1h | `ci/m1h-publish-and-staging-deploy` | CI + VPS (G6, G10) | CI `publish` job (build once, labels, Trivy gate, push by digest to GHCR with `GITHUB_TOKEN`, digest artifact) and `deploy-staging` job (staging key, forced command); `scripts/deploy-prod` owner wrapper; workflow secret-reference test | a merge to `main` deploys to staging from CI with no cloud key; no production deploy credential exists in GitHub (workflow and secret listing check); the owner wrapper refuses a digest without a green `main` CI run | ≈ 330 |
| M1i | `feat/m1i-file-store-harness` | CI (EICAR on staging if CI cannot run `clamd`) | `app/documents/storage.py` (publish contract, verified open, sweeper helpers), import-linter contract and Semgrep files-volume rule with fixtures, failpoint harness on a test-only probe table, `clamav` service | the five failpoints, the concurrent retry and the altered-file case pass; the import-linter/Semgrep files-volume rule rejects its fixture; FILE-01 wrong magic and SVG/HTML refused; EICAR rejected | ≈ 400 |
| M1j | `feat/m1j-health-alerts` | CI (delivery: VPS + G8) | `infra/host/skiw-health` + systemd timer, alert sender for the Q20 channel, journald settings, monthly `check-hardening` | alert payload test (check name, host, value only; no client data, UNI-09); no timer calls an HTTP endpoint other than the read-only `/readyz` probe (UNI-19 test) | ≈ 280 |
| M1k | `docs/m1k-gates-and-runbooks` | VPS + owner (G2, G3) | G-VENDOR record, G-S1 run and results, real-host evidence of every VPS acceptance item, measured deploy outage, runbooks completed with measured values, DECISIONS entries | G-S1: `make test-live` passes against the VPS Postgres as `skiw_app`, role-set test passes, `pg_dump -Fc` as `skiw_backup` succeeds and as `skiw_migrator` fails on a FORCE-RLS table, `pgcrypto` and definer ownership confirmed; G-VENDOR entry with each item marked; all VPS items of §3 evidenced | ≈ 250 (docs) |

PRs that can run in parallel after M1a: M1b → M1c; M1d and M1e need M1b (compose secrets and networks); M1f is independent of M1b–M1e; M1g needs M1b, M1d, M1e; M1h needs M1g; M1i needs M1b only; M1j needs M1f. M1k needs all, plus the bought VPSs.

**Language for host scripts:** Python 3.12, standard library only, in package `infra/host/skiw_host/`, with small executables at the spec's paths (`infra/host/bootstrap-secrets`, `infra/host/bootstrap-db`, `infra/host/check-hardening`, `infra/host/skiw-deploy`, `infra/host/skiw-deploy-ssh`, `infra/host/skiw-health`). Reasons: one language with the app, mypy strict and ruff already in CI, testable with pytest, no new dependency (UNI-06), and Ubuntu 24.04 ships Python 3.12 (G4). `infra/host/apply` copies them root-owned to `/usr/local/sbin` and `/usr/local/lib/skiw/`. Only `scripts/deploy-prod` lives outside `infra/host/` (PROJECT.md §3).

**Test command name:** `make host-test` — runs `pytest infra/host/tests` (unit tests, no Docker daemon needed) and the Compose config tests (`docker compose -f infra/host/compose.yml --env-file infra/host/env/ci.env config --format json`, parsed in pytest; needs the Compose CLI only). The live stack tests (M1c, M1e, M1i) run under `make host-test-live` in the CI `host` job. **PROJECT.md §7 follow-up:** after M1a merges, a tiny separate docs PR (not this plan, not M1a) replaces the `pending M1` line with `make host-test` and adds `make host-test-live` (the builder does not edit PROJECT.md in a feature PR; setup owns it).

## 2. Versions and upstream facts (checked 2026-10-12)

Every image is pinned by digest at implementation (`image: name:tag@sha256:<digest>`), read from the registry on the day of the PR and recorded in that PR's DECISIONS entry. No digest below is real; none is fabricated.

| Item | Pin / fact | How verified on 2026-10-12 |
|---|---|---|
| Caddy | 2.11.7, image `caddy:2.11.7-alpine` | GitHub release `v2.11.7` (2026-10-03); Docker Hub tag present. The official alpine Dockerfile runs `setcap cap_net_bind_service=+ep /usr/bin/caddy` and exposes 80/443/2019 (caddy-docker `2.11/alpine/Dockerfile`), hence G13 |
| Caddy proxy headers and timeouts | without `trusted_proxies`, `reverse_proxy` ignores incoming `X-Forwarded-For/-Proto/-Host` "to prevent spoofing"; HTTP transport `dial_timeout` 3 s, read/write/response-header timeouts none by default; no periodic flushing by default | caddyserver.com `reverse_proxy` docs (closes the H14 UNI-17 [A] on documented behaviour; the M1c test proves it) |
| Postgres | 17.11 — same digest as `docker-compose.yml` today (`postgres:17.11@sha256:d74eeac9…`) | Docker Hub: tag `17.11` exists, `17.12` returns 404 |
| ClamAV | 1.5.4 (`clamav/clamav:1.5.4`; 1.4.6 tags also published) | GitHub release `clamav-1.5.4` (2026-08-07); Docker Hub tags. **Not verified:** which line is LTS today, whether the image ships signatures, and whether it can run non-root — decided in M1i |
| age | v1.3.2, `age-v1.3.2-linux-amd64.tar.gz` | GitHub release (2026-08-29). The release ships `.proof` files, no checksum list was seen: M1d records the SHA-256 of the downloaded archive and installs the checksum-verified binary in the `backup` image and on hosts. Proof verification **not verified** |
| Docker Engine / Compose plugin | Engine 29.9.0, Compose v5.6.0 | GitHub releases `moby/moby docker-v29.9.0` (2026-10-08), `docker/compose v5.6.0` (2026-10-02). Exact apt version strings in `download.docker.com` **not verified**; M1f pins them by reading the repository on the day |
| Trivy / trivy-action / gitleaks | v0.75.0 / v0.36.0 (`ed142fd0…`) / v8.30.1 | latest GitHub releases; already pinned in `ci.yml` |
| Host OS | Ubuntu 24.04.5 LTS (support to 2029-05-31) or Debian 12.15 (regular support ended 2026-07-11, LTS to 2028-06-30) | endoflife.date API (not re-checked on ubuntu.com or debian.org) |
| GHCR auth | "GitHub Packages only supports authentication using a personal access token (classic)" | GitHub docs, Container registry page |
| GHCR cost | Container registry storage and bandwidth "currently free", with one month's notice of change; Free plan otherwise 500 MB / 1 GB per month for private packages | GitHub billing docs for Packages. Keeps §8.2 "RM 0 [A]"; risk 7 |
| Dependabot | `package-ecosystem: docker-compose` is valid (v2, v3 files) | GitHub docs options reference. Whether it bumps `@sha256` digests in `infra/host/compose.yml` is **not verified**; M1a checks the first Dependabot run |
| Python on host | 3.12 on Ubuntu 24.04 | not re-checked this session (known distro default) |

Actions keep the existing SHAs (checkout v7.0.1, setup-uv v10.2.0, setup-node v7.0.0, pnpm action-setup v6.1.0, trivy-action v0.36.0). M1h adds no new action: GHCR login and push use `docker login --password-stdin` and `docker push` with the job's token.

## 3. Per-PR files, tests and checklists

### M1a — `chore/m1a-host-scaffold` (CI)
Files:
- Delete `infra/app.py`, `infra/cdk.json`, `infra/skiw_infra/__init__.py`, `infra/skiw_infra/placeholder_stack.py`, `infra/tests/test_synth.py`.
- `.github/workflows/ci.yml`: remove job `infra`; add job `host` (checkout, setup-uv, `make host-test`); Semgrep registry path list `app infra web/src` → `app infra/host web/src`.
- `pyproject.toml`: remove group `infra` (`aws-cdk-lib`); `[tool.ruff] src = ["app", "infra/host"]`; per-file-ignores `"infra/tests/**"` → `"infra/host/tests/**" = ["S101", "S603"]`; `mypy_path = "app:infra/host"`; `[tool.pytest.ini_options] testpaths = ["app", "infra/host/tests"]`; import-linter root package `skiw_host` and a contract "app packages and `skiw_host` do not import each other" (UNI-04). `uv.lock` regenerated (generated file).
- `Makefile`: drop `infra-test`; add `host-test`, `host-test-live` (stub that M1b fills), `secrets-test`; `typecheck` becomes `uv run --locked mypy app infra/host` (no `--group infra`); `PYTHONPATH := app:infra/host`; Dockerfile `uv sync … --no-group infra` → drop the flag.
- `infra/host/skiw_host/__init__.py`, `infra/host/tests/__init__.py`, `infra/host/tests/test_layout.py` (no file left under `infra/` outside `infra/host/`; nothing under `scripts/` except `deploy-prod`).
- `.gitleaks.toml`: add `lookup_decoy_key`, `field_kek`, `blind_index_key`, `crm_jar_kek` to the regex and `keywords`. `infra/host/tests/test_gitleaks_config.py`: writes, into a temporary directory, one line per key name assigning a random 32-character value generated at test time, runs `gitleaks dir --no-banner --config .gitleaks.toml <tmp>` and asserts one finding per name with rule id `skiw-secret-key-assignment`; a bare name passes. No fake secret is committed, so no path allow-list is needed (PR 9 review R1). Runs as `make secrets-test` in the CI `security` job (gitleaks is installed there).
- `.env.example` line 2 → `# Placeholders below are not secrets; on hosts, secrets live only in the host secret store (spec §8.4 H4).`
- `.github/dependabot.yml`: add `package-ecosystem: docker-compose`, `directory: /infra/host` (and `/` for the local `docker-compose.yml`), weekly, prefix `chore(deps)`.
- Runbooks, stale facts only: `ci.md` (infra row → host row, Semgrep path), `local-dev.md` (`make infra-test` row → `make host-test`), `deploy.md`, `rollback.md`, `restore.md`, `incident-pdpa-breach.md` first lines (AWS/`ap-southeast-5` → iCore VPS, "filled in M1g/M1k" or "M6"), `README.md` status column.
- `docs/plans/2026-10-05-m0-scaffold.md`: one line under the header, "Historical: the `infra/` CDK items were superseded by spec v1.14 and removed in M1a." No other change.
- `docs/DECISIONS.md`: M1 entry (CDK removal, `make host-test`, host scripts in Python stdlib, gitleaks names, Dependabot entry).

Checklist:
- [ ] `make install lint typecheck test host-test` green; `rg -n "aws-cdk|cdk.json|skiw_infra|ap-southeast-5" -g '!docs/specs/**' -g '!docs/DECISIONS.md' -g '!docs/plans/**'` returns nothing.
- [ ] `make secrets-test` fails if any of the four names is removed from `.gitleaks.toml` (shown in the PR body), passes as committed; `make secrets` (full history) still green.
- [ ] CI shows jobs `checks`, `security`, `image`, `host`; no `infra`.

### M1b — `feat/m1b-compose-stack` (CI)
Files:
- `infra/host/compose.yml`: services `caddy`, `web`, `worker`, `migrate` (profile `deploy`, started only by `skiw-deploy`), `db`, `clamav`, `backup` (profile `ops`; M1 uses it only for the pre-migration dump, M6 adds the schedule). Networks `edge`, `app` (`internal: true`), `ops` (`internal: true`), `egress`, each with a fixed subnet from host config. Images by `${SKIW_IMAGE}` digest (app) and pinned digests (others). Per service: `user`, `read_only: true`, `tmpfs: /tmp` where needed, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `mem_limit` per H1, `pids_limit`, `restart: unless-stopped`, `logging.driver: journald`. `worker` command `python app/manage.py runworker`, `stop_grace_period` from host config. Volumes `skiw-db`, `skiw-files` (mounted read-write only in `web`, `worker`; read-only in `backup`), `caddy-data`, `caddy-config`; bind `/srv/skiw/backups` only in `backup`. Secrets as Compose file secrets from `/etc/skiw/secrets/<name>`, each listed only under the services of the H4 inventory.
- `infra/host/env/{staging,production,ci}.env`: non-secret values (subnets, memory limits, `deploy.health_timeout_s` 60, `jobs.worker_hard_exit_s` mirror, hostnames left empty until G9; `ci.env` uses test values). The scripts refuse an empty required value.
- `app/config/env.py` + `settings.py`: read `DJANGO_SECRET_KEY_FILE` (`v<n>:<base64>` lines: newest → `SECRET_KEY`, older → `SECRET_KEY_FALLBACKS`) and `DATABASE_PASSWORD_FILE` (password not in `DATABASE_URL`) when set; env values stay for local/CI. Fail closed on a malformed file.
- `app/health/views.py` + `app/config/urls.py`: `/readyz` — 200 only when the DB answers as `skiw_app` and no migration is unapplied (reuses `jobs.startup._pending`, moved to a shared function), else 503; no body detail beyond `ok`/`not ready` (UNI-09).
- Tests `infra/host/tests/test_compose_config.py` (parses `docker compose config --format json`), `app/tests/test_readyz.py`, `app/tests/test_secret_files.py`.

Checklist (Compose config tests, spec §9 M1):
- [ ] only `caddy` has `ports:`; it publishes exactly 80 and 443.
- [ ] `db` and `backup` are on no network that is not `internal`; `db` has no `ports:`.
- [ ] every `image:` matches `@sha256:[0-9a-f]{64}$` (UNI-14).
- [ ] every service has the H1 user, `read_only: true`, memory limit, `pids_limit`, `restart: unless-stopped`, journald logging, or is in a named exception list in the test with its reason (expected: `db` writes its data volume and runs as `postgres` after init; `clamav` [A]).
- [ ] `worker` command is `runworker` and `stop_grace_period` equals the declared value (D5, H13).
- [ ] no `web`/`worker`/`migrate` service mounts the `skiw_backup` secret or `/srv/skiw/backups`; files volume only in `web`, `worker` (rw) and `backup` (ro) (FILE-03 M1 part, UNI-04).
- [ ] no service has a secret value in `environment:` (only `*_FILE` paths); a planted `DATABASE_URL` with a password in the fixture env fails the test.
- [ ] `/readyz` returns 503 with an unapplied migration and 200 after `make migrate` (live test).

### M1c — `feat/m1c-caddy-edge` (CI; host TLS needs VPS + G9)
Files: `infra/host/caddy/Caddyfile` (site block from `SKIW_HOSTNAME`; explicit `http://` block that sets HSTS and redirects with 308, so the redirect carries HSTS; `header Strict-Transport-Security "max-age=31536000"` on every response; `request_body max_size 25MB`; `reverse_proxy web:8000` with read/write timeouts ≥ 40 s; `handle_errors` for 502/503/504 serving `maintenance.html` with status 503 and `Retry-After`; no `trusted_proxies`; admin endpoint off), `infra/host/caddy/maintenance.html`, `infra/host/caddy/ci.Caddyfile` overlay (`tls internal`), `app/config/settings.py` (`SECURE_PROXY_SSL_HEADER` only when `DJANGO_BEHIND_CADDY=1`), `infra/host/tests/test_edge_live.py` (stack in CI: caddy + web + db on `compose.yml` with `ci.env`; a stub upstream for the long-poll case), `Makefile` `host-test-live`, CI `host` job runs it.

Checklist:
- [ ] HSTS present on the HTTP→HTTPS redirect, on the maintenance page (web stopped) and on an app page (UNI-17).
- [ ] a request with `X-Forwarded-Proto: https` sent over plain HTTP to Caddy reaches Django as `http` (Django's `request.is_secure()` false; probe in the test settings only).
- [ ] a 25 s response from the stub upstream completes through Caddy; a 26 MB body is refused with 413 (FILE-02 outer cap).
- [ ] maintenance page: HTTP 503 with `Retry-After`.
- [ ] VPS (M1k): `/readyz` 200 through Caddy with a publicly valid certificate and HSTS, on both hosts.
- [ ] DECISIONS: where each header is applied (Caddy: HSTS, redirect; Django: CSP, `frame-ancestors`, HSTS from M2), UNI-17.

### M1d — `feat/m1d-bootstrap-secrets` (CI; host run needs VPS + G5)
Files: `infra/host/bootstrap-secrets`, `infra/host/skiw_host/secrets.py` (inventory: the H4 names with the service that reads each — `tenant_token_key`, `approval_mac_key`, `lookup_decoy_key`, `tenant_source_key`, `login_blob_key`, `audit_mac_key`, `django_secret_key`, `field_kek`, `blind_index_key`, `crm_jar_kek`, DB passwords of `skiw_migrator`, `skiw_app`, `skiw_readonly`, `skiw_backup`, `postgres`, `ghcr_read_token` (owner-supplied, not minted), plus the G11 name), `infra/host/skiw_host/escrow.py` (calls the pinned `age` binary with the owner's escrow recipient from host config), `infra/host/tests/test_bootstrap_secrets.py`, `docs/runbooks/host-rebuild.md` (new: secrets section).

Behaviour: `init` mints 32 bytes from `os.urandom` per app key as `v1:<base64>`, writes `/etc/skiw/secrets/<name>` 0400 owned by the reading service's uid (root 0700 directory), never prints a value, refuses if any secret file or `/etc/skiw/secrets/.restored` exists, then writes `/srv/skiw/escrow/<time>.bundle.age` (all app key versions; no DB passwords, deploy keys or GHCR token). `restore` reads the decrypted bundle on stdin, checks the manifest (every inventory app key present, per-version SHA-256), installs versions verbatim, writes `.restored`, refuses on any missing key, and mints nothing unless `--allow-new-key-version <name>` (logged to the journal and the deploy log). DB passwords are always newly set (by `bootstrap-db`).

Checklist (tests use a temporary root and a fake `age`):
- [ ] `init` twice → second refuses; `init` after `restore` refuses; values never on stdout/stderr (captured).
- [ ] modes 0400, owners per inventory, directory 0700.
- [ ] `restore` with one key missing refuses and writes nothing; with a wrong SHA-256 refuses; with the override mints only the named key and logs it.
- [ ] bundle contains every app key version and no DB password.

### M1e — `feat/m1e-bootstrap-db` (CI; host run needs VPS)
Files: `infra/host/db/roles.sql` (closed role set with D4/H6 attributes: `skiw_migrator`, `skiw_app` (no memberships), `skiw_readonly`, `skiw_backup` `LOGIN NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 2`, member of `pg_read_all_data`, `ALTER ROLE skiw_backup SET default_transaction_read_only = on`; NOLOGIN `skiw_tenant_guard`, `skiw_auth_lookup` (the latter BYPASSRLS per H6 role-set test); database owner `skiw_migrator`), `infra/host/db/pg_hba.conf` (rendered with the subnets: `skiw_app`, `skiw_migrator` from `app`; `skiw_backup` from `ops`; `skiw_readonly`, `postgres` `local` only; everything else `reject`; `scram-sha-256`), `infra/host/bootstrap-db` (applies `roles.sql` through the unix socket as `postgres` with `docker compose exec db`, sets every password from the secret files without echoing), `docker/postgres/10-roles.sh` replaced by a call to the same `roles.sql` (local and CI then have the closed role set; `.env.example` `POSTGRES_USER=postgres`; `make clean` needed once, noted in `local-dev.md`), `app/tests/test_live_role_set.py`, `infra/host/tests/test_pg_hba_live.py` (CI stack with the `app` and `ops` networks: connect attempts from a probe container on each), `docs/runbooks/host-rebuild.md` (db section).

Checklist:
- [ ] role-set test: exactly the closed role set besides `pg_*`; only `postgres` superuser; BYPASSRLS only on `postgres`, `skiw_auth_lookup`, `skiw_backup`; `skiw_app` member of no role; `skiw_backup` read-only by default (TEN-02, hard).
- [ ] `skiw_backup` from `app` refused, from `ops` accepted; `skiw_app` from `ops` refused; `skiw_readonly` over TCP refused (TEN-10 ops mapping).
- [ ] existing `make test-live` stays green on the new local role set.
- [ ] `bootstrap-db` is idempotent (second run changes nothing but passwords when asked).

### M1f — `feat/m1f-host-hardening` (CI; host run needs VPS + G4, G7, G15)
Files: `infra/host/apply` (idempotent: apt pins for Docker Engine and Compose plugin from the signed Docker apt repo, users `skiw-deploy` and `skiw-ops` not in group `docker`, installs files, enables units), `infra/host/nftables.conf` (default deny inbound; 80/443; SSH port from host config; per-source new-connection limits; allow-list or not per G7), `infra/host/sshd/50-skiw.conf` (`PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitRootLogin no`, `MaxAuthTries`, `Port`), `infra/host/docker/daemon.json` (`live-restore: true`, `no-new-privileges: true`, `log-driver: journald`, no `hosts` TCP entry), `infra/host/apt/52skiw-unattended` (security origin, reboot per G15), `infra/host/fail2ban/jail.local` (only for G7 (b)), `infra/host/journald/skiw.conf` (`Storage=persistent`, `MaxRetentionSec=90day`, `SystemMaxUse` from host config), `infra/host/check-hardening` + `skiw_host/hardening.py`, `infra/host/tests/test_check_hardening.py` (fixtures of `sshd -T`, `nft list ruleset`, `ss -tlnp`, `docker info`, `stat` output, `docker inspect` env), `docs/runbooks/host-rebuild.md` (host section).

`check-hardening` verifies: sshd effective settings; nftables ruleset equals the rendered file; unattended-upgrades enabled; Docker daemon config; listening sockets on public addresses only 80, 443 and the SSH port; secret-file owners and modes (H4 [A] on Compose secret uid/mode); no secret value in any container environment (`docker inspect`, UNI-07, T16); deploy/pull accounts not in `docker`; the role set (calls the M1e query through the socket).

Checklist:
- [ ] each check has a passing and a failing fixture; exit code non-zero on any failure; output names check and value only.
- [ ] VPS (M1k): `check-hardening` passes on staging and production; external `nmap -p- <host>` from the owner's machine shows only 80, 443 and the SSH port (output in the PR body of M1k).

### M1g — `feat/m1g-skiw-deploy` (CI; host run needs VPS + G5, G6, G11, G12)
Files: `infra/host/skiw-deploy-ssh` (reads only `SSH_ORIGINAL_COMMAND`; accepts `deploy <digest> [<run-id>]` or `rollback <digest>`; anything else, including `id`, exits non-zero), `infra/host/skiw-deploy` + `skiw_host/deploy.py`, `infra/host/sudoers.d/skiw-deploy` (exactly that command), `infra/host/backup/predeploy/Dockerfile` (FROM the pinned `postgres:17.11` digest + checksum-verified `age` binary) and `predeploy.py` (as `skiw_backup` on `ops`: `pg_dump -Fc`, excluding data of `guard.tenant_mac_key`, `guard.approval_mac_key`, `guard.lookup_decoy_key` when they exist; `pg_restore --list` on the stream; `age -r <dump recipient>`; writes `/srv/skiw/backups/predeploy/<time>.dump.age` + SHA-256), `app/config/management/commands/migration_labels.py` (prints migration head and contract list from the migration files, no DB), `infra/host/tests/test_deploy.py`, `docs/runbooks/deploy.md`, `docs/runbooks/rollback.md`, `docs/runbooks/restore.md` (section "Restore the pre-migration dump" only).

`skiw-deploy <digest>` steps (H3): (3) refuse unless `sha256:` + 64 hex and the fixed repository from host config; take `/run/skiw-deploy.lock`; `docker pull` by digest with the GHCR read token from the secret file (`--password-stdin`). Production only: refuse unless the staging status (G11) reports that exact digest running, healthy and `checks=passed`; refuse the staging key: each `authorized_keys` line fixes its own key role in its `command=` (for example `command="/usr/local/sbin/skiw-deploy-ssh --key production"`), so the role comes from the host file, never from the caller. (4) run `migrate --plan` in the new image's `migrate` service; if not empty, run the pre-migration dump; failure stops. (5) `migrate` as `skiw_migrator`; failure stops, old containers keep serving. (6) switch `web` and `worker` (`SKIW_IMAGE` in the state file, `docker compose up -d`). (7) `/readyz` 200 within `deploy.health_timeout_s` and worker registered within two heartbeat intervals; else switch back to the previous digest and alert; never reverse migrations. (9) production only: append one line to `/var/lib/skiw/accepted-digests` (digest, commit, run id, staging check time, deploy time, `/readyz` result, migration head, contract list, key fingerprint; `chattr +a` [A]). (11) journal and deploy log line. Staging only: after step 7, run the G12 checks and write the staging state line. `--rollback <digest>`: owner key only; digest must be in the accepted-digest record; no staging check, no `migrate`; refused when the host state's applied-contract list (union of the contract lists of every digest whose `migrate` succeeded on this host) contains a migration not in the target's migration head; steps 6–7 apply.

Contract migrations: a migration is a contract migration when its class sets `skiw_contract = True`; `migration_labels` lists them; a test fails if any migration with `RemoveField`, `DeleteModel`, `RenameField`, `RenameModel` or `AlterField` lacks the flag. Today the list is empty (no own contract migration exists); the refusal is proven with fixture labels.

Checklist (CI, fakes for `docker`, `ssh`, `curl` and time):
- [ ] forced command: `id`, `deploy`, `deploy sha256:abc`, a 64-hex digest of another repository, shell metacharacters → refused, nothing run.
- [ ] failing `/readyz` after switch → previous digest restored, alert raised, no accepted-digest line (spec "deliberately failing health check rolls back").
- [ ] pending migration → pre-migration dump runs before `migrate`; dump failure stops the deploy (D16 M1 row "deploy test with a pending migration").
- [ ] production: staging key refused; digest not healthy on staging refused; successful deploy adds exactly one accepted-digest line.
- [ ] rollback: to the previous accepted digest with staging on a newer digest succeeds and skips the staging check; to an unknown, staging-only, or contract-crossing digest refused; with the staging key refused (UNI-15, T25).
- [ ] VPS (M1k): the same cases on the real hosts; measured outage (old `web` stop → `/readyz` 200) recorded in `deploy.md` and DECISIONS.

### M1h — `ci/m1h-publish-and-staging-deploy` (CI + VPS, G6, G10)
Files: `.github/workflows/ci.yml` — job `publish` (`if` push to `main`, `needs` all gate jobs, `permissions: contents: read, packages: write`): `docker build` with labels `org.opencontainers.image.revision`, `skiw.migration-head`, `skiw.contract-migrations` (from `migration_labels`); Trivy gate on that exact image (HIGH/CRITICAL, as the `image` job); `docker push ghcr.io/charliekhc/skiw-platform:<sha>`; reads the pushed digest; uploads artifact `image-digest` (`digest.txt`); job `deploy-staging` (`needs: publish`, `contents: read` only): writes the staging key from the repository secret to a temporary file, runs `ssh … deploy <digest> <run-id>` against the staging host (host key pinned from a non-secret known-hosts line in `infra/host/env/staging.env`). `scripts/deploy-prod` (Python stdlib, owner's machine): `gh run view <run-id> --json conclusion,event,headBranch,headSha,workflowName` must be `success`/`push`/`main`/`ci`; `gh api repos/charliekhc/skiw-platform/compare/<headSha>...main` must show `headSha` on `main`; `gh run download <run-id> -n image-digest` must equal the digest argument; then `ssh -i <owner key> skiw-deploy@<production host> deploy <digest> <run-id>`. `infra/host/tests/test_workflows.py`: the only secret referenced in any workflow is `STAGING_DEPLOY_KEY`; no workflow names the production host or a production key; `packages: write` only on `publish`; `scripts/` contains only `deploy-prod`. `infra/host/tests/test_deploy_prod.py` with a fake `gh`. `docs/runbooks/deploy.md` (CI and owner steps), `docs/runbooks/ci.md`.

Checklist:
- [ ] a merge to `main` deploys to staging from CI with no cloud key (VPS; run link in M1k).
- [ ] `gh secret list` and `gh api repos/charliekhc/skiw-platform/environments` show no production credential (output in the PR body; Q42).
- [ ] the wrapper refuses: a failed run, a non-`main` run, a digest not equal to the run's artifact, a commit not on `main`.
- [ ] the published image is the scanned image (same digest in the Trivy step and the push log).

### M1i — `feat/m1i-file-store-harness` (CI; EICAR may need staging)
Files: `app/documents/__init__.py`, `app/documents/storage.py` (files root from settings; `write_quarantine(agency_id, stream, max_bytes)` with magic-byte check on the first bytes and size limit while streaming, `tmp/<uuid>.part` → fsync → rename → dir fsync; `publish_clean(...)` per H5 steps 2–6 under `pg_advisory_xact_lock`; `open_verified(row)` checks size and SHA-256 before the first byte; sweeper helpers for `tmp/*.part` and quarantine leftovers older than 1 h [A]; failpoint hooks enabled only by test settings), `semgrep/files-volume-only-storage.yml` + fixture, import-linter contract (`documents.storage` is the only module that may use the files root setting), `app/documents/tests/` (probe table `files_probe` created in the test session over `MIGRATION_DATABASE_URL` with grants to `skiw_app` only, dropped at the end — G14), `clamav` service in the CI stack.

Checklist:
- [ ] failpoints: crash during upload write; after quarantine rename before row commit; during output write; after publish rename before DB commit; after commit before quarantine delete — no partial or unvalidated file is returned by `open_verified`, every retry converges to exactly one committed artifact matching the row, the sweeper removes every leftover.
- [ ] concurrent second attempt on the same row converges (advisory lock); altered or truncated clean file refused by `open_verified` and the row marked `integrity_failed` (EVT-05 M1 part).
- [ ] wrong magic, SVG and HTML refused at the boundary (FILE-01); over-limit stream refused (FILE-02); EICAR rejected by `clamd` INSTREAM.
- [ ] Semgrep rule rejects its fixture (file I/O under the files root outside `documents.storage`); import-linter contract fails on a planted import (UNI-04).

### M1j — `feat/m1j-health-alerts` (CI; delivery needs VPS + G8)
Files: `infra/host/skiw-health` + `skiw_host/health.py`, `infra/host/systemd/skiw-health.{service,timer}` (every 5 min) and `skiw-hardening.timer` (monthly), `skiw_host/alert.py` (one sender for the Q20 channel; payload = check name, host, value; nothing from the database or app logs), tests. Checks: disk (alert at 80 %), memory and swap, load, container health and restarts, `/readyz` (local, read-only), TLS certificate age, newest local dump age (predeploy only until M6), pending security updates, reboot needed.

Checklist:
- [ ] alert payload test: only the three fields; a value containing an email or IC-like pattern is replaced (UNI-09).
- [ ] UNI-19 test: no systemd unit or Compose service triggers work through HTTP; the only HTTP call is the read-only `/readyz` probe.
- [ ] with no Q20 channel configured the sender writes to the journal and exits non-zero (fail closed, no silent drop).

### M1k — `docs/m1k-gates-and-runbooks` (VPS + owner)
Real-host work is done by the operator (the owner) with the builder's runbook steps; agents never hold the production key (PROJECT.md §11). Files: `docs/DECISIONS.md` (G-VENDOR entry with all eleven items marked; G-S1 results; OS, SSH policy, measured outage, staging-check mechanism, header placement), `docs/runbooks/{deploy,rollback,host-rebuild,ci,local-dev,restore,incident-pdpa-breach,README}.md` completed with measured values.

G-S1 procedure on each VPS (production NODE2 is the gate host; staging repeats it): `bootstrap-secrets init`, `bootstrap-db`; a test image (`Dockerfile` target `test`, dev group, never pushed to GHCR) run on the `app` network runs `make test-live` equivalents as `skiw_app` with `MIGRATION_DATABASE_URL` for the M0c harness; the role-set test; a spike-only script creates as `skiw_migrator` a probe table with RLS ENABLE + FORCE and a policy, a definer function owned by `skiw_tenant_guard`, `CREATE EXTENSION pgcrypto` and an `ALTER DEFAULT PRIVILEGES` statement, then `pg_dump -Fc` as `skiw_backup` (must succeed) and as `skiw_migrator` (must fail on the FORCE-RLS table), then drops every spike object. Results with commands and outputs (no secret values) go to DECISIONS. The M4 live suite re-run before go-live stays open (H12).

## 4. Out-of-sync inventory → PR

| Item | Change | PR |
|---|---|---|
| `.gitleaks.toml` | add `lookup_decoy_key`, `field_kek`, `blind_index_key`, `crm_jar_kek` + generated-fixture test | M1a |
| `Makefile` `infra-test`, `typecheck --group infra` | removed; `host-test`, `host-test-live`, `secrets-test` | M1a (live target filled in M1c) |
| `.github/workflows/ci.yml` `infra` job; Semgrep path `infra` | job → `host`; path → `infra/host` | M1a; `publish`/`deploy-staging` in M1h |
| `pyproject.toml` group `infra`, `src`, per-file-ignores, `mypy_path` | as in §3 M1a; `uv.lock` regenerated | M1a |
| `Dockerfile` `--no-group infra` | flag removed | M1a |
| `infra/app.py`, `infra/cdk.json`, `infra/skiw_infra/`, `infra/tests/` | deleted (UNI-05) | M1a |
| `.env.example` line 2 "AWS Secrets Manager (spec D16)" | host secret store (H4) | M1a; `POSTGRES_USER=postgres` in M1e |
| `.github/dependabot.yml` no `docker-compose` entry | added (closes the 2026-10-10 known gap) | M1a |
| `docs/runbooks/deploy.md` | stale line M1a; rewritten M1g/M1h; measured values M1k | M1a, M1g, M1h, M1k |
| `docs/runbooks/rollback.md` | stale line M1a; rewritten M1g | M1a, M1g, M1k |
| `docs/runbooks/restore.md` | stale line M1a; pre-migration dump restore M1g; complete recovery stays M6 | M1a, M1g |
| `docs/runbooks/ci.md` | infra row M1a; publish/deploy jobs M1h | M1a, M1h |
| `docs/runbooks/local-dev.md` | `make infra-test` row M1a; role set and `make clean` note M1e | M1a, M1e |
| `docs/runbooks/incident-pdpa-breach.md` | AWS line → iCore VPS and where logs live; full runbook M6 | M1a (line), M1k (log locations) |
| `docs/runbooks/host-rebuild.md` | new | M1d, M1e, M1f, M1k |
| `docs/plans/2026-10-05-m0-scaffold.md` | historical; one "superseded" line only | M1a |
| DECISIONS 2026-10-06 "staging TLS connection check due before the M1 deploy" and M0 plan "live TLS proof is M1" | closed by spec v1.14 H6 (no TLS on host-internal networks; `DJANGO_REQUIRE_DB_TLS` unset on hosts); recorded, not built | M1b DECISIONS entry |
| `agents/PROJECT.md` §7 `pending M1` | follow-up docs PR after M1a (not edited by this plan or by M1a) | follow-up |

## 5. Scope exclusions and what M1 leaves for later

- **M6 (backup runtime):** the `backup` schedule (`backup.cadence`, Q34), the backup coordinator and its contract test, the consistent cut and capture watermark, the files archive (base/delta), recovery-set manifests, dependent retention, the off-site puller and freshness alert (Q36), the anchor witness and signed restore transitions, the daily journal export pull, key-escrow pull, `bootstrap-secrets restore` exercised in a drill, G-DRILL, G-BACKUP, G-LOAD, key-rotation runbook, full incident runbook. M1 builds only the pre-migration dump (H3 step 4) in a minimal `backup` image and writes the escrow bundle locally.
- **M16 (files feature):** upload and download endpoints, signed links (FILE-04), the `document` and `file_tombstone` tables, tombstone sweeper, real upload paths. M1 builds the storage contract and harness only (G14).
- **M4 (jobs and tenancy):** `with_agency()`, guard keys written by `migrate`, scan job through `jobs.enqueue_in_tx`, the M4 live suite (required on the VPS before go-live, G-S1 second half).
- **M2:** Django security headers and sessions; M1 adds only `SECURE_PROXY_SSL_HEADER` behind a flag.
- **M14:** the real long-poll endpoint and G-LOAD's device profile.
- Not in v1 at all: WAF, OIDC, KMS, preview environments, host egress allow-list (H2).

## 6. Rule mapping (spec H14 and §9 M1, per PR)

No test below has run. "Evidence" is what the named PR must show; host evidence arrives in M1k.

| Rule | Design (from H14) | Evidence in M1 | PR |
|---|---|---|---|
| UNI-04 | `documents.storage` is the only module touching the files volume; `backup` tooling imports no app code; deploy and bootstrap scripts outside `app/` | import-linter contract and Semgrep rule with fixtures; Compose test that no app service mounts `skiw_backup` or the backup directory read-write; `skiw_host` ↔ app contract | M1i, M1b, M1a |
| UNI-05 | CDK skeleton and its CI job removed | the deletion and `rg` check | M1a |
| UNI-07 (hard) | no secret values in repo or image; key names only | gitleaks in CI and pre-push (existing) + `secrets-test`; hardening check: no secret in container env | M1a, M1b, M1f |
| UNI-08 | host secret store, one file per service | `check-hardening` owners, modes, mounts; `bootstrap-secrets` tests | M1d, M1f |
| UNI-09 | scrubbed logs; alerts carry no client data | alert payload test | M1j |
| UNI-13 | CI gates unchanged; Trivy before push; `infra/host/` config tests added | CI `host` job on every PR; Trivy in `publish` | M1a, M1h |
| UNI-14 | every image and tool pinned | Compose test: no unpinned image; age/Docker pins recorded | M1b, M1d, M1f |
| UNI-15 | additive migrations; rollback refused across a contract migration | existing `lintmigrations` gate; rollback-across-contract refusal test | M1g |
| UNI-16 | deploy, rollback, host rebuild runbooks rewritten with the change | runbook diffs in the same PRs | M1d–M1h, M1k |
| UNI-17 | Caddy: TLS, redirect, HSTS on every response incl. redirect and maintenance; Django trusts `X-Forwarded-Proto` only from Caddy; placement recorded in DECISIONS | header tests through Caddy; spoofed `X-Forwarded-Proto` test | M1c |
| UNI-19 | no HTTP cron; schedules in `worker` and the `backup` ops worker | Compose/systemd test: no timer calls an HTTP endpoint | M1j |
| TEN-01 | `skiw_migrator` owns the schema; only `migrate` uses it, started only by `skiw-deploy` | existing ownership query; Compose test (`migrate` only in profile `deploy`); G-S1 | M1b, M1g, M1k |
| TEN-02 (hard) | `skiw_app` unchanged; `skiw_backup` only in `backup`, subnet-restricted | role-set test, `pg_hba` connection tests, Compose secret-mount test; G-S1 | M1e, M1b, M1k |
| TEN-10 | ops access mapped: `backup` as `skiw_backup` from `ops`; `migrate` as `skiw_migrator`; `bootstrap-db` and break-glass via socket | `pg_hba` tests and role-set test (M1 part); coordinator contract test is M6 | M1e |
| FILE-01 | magic-byte allow-list; output re-validated | harness: wrong magic, SVG/HTML refused; EICAR rejected | M1i |
| FILE-02 | `upload.max_mb` while streaming; Caddy 25 MB outer cap | Caddy cap test; harness size test | M1c, M1i |
| FILE-03 | `quarantine/` and `clean/<agency_id>/<uuid>` | M1 part: files volume mounted only in `web`, `worker`, `backup` (Compose test); path-shape test is M16 | M1b |
| FILE-04 | signed link ≤ 300 s, re-checks, attachment, `nosniff`, `no-store`, verified before first byte | n/a in M1 except `open_verified` (altered-file refusal); the link tests are M16 | M1i (part) |
| EVT-01 | scan job enqueued in the upload transaction | n/a in M1 (M16) | — |
| EVT-02 | n/a: no relay; backup, puller and witness publish no events | — | — |
| EVT-05 | scan retries converge under the advisory lock | failpoint and concurrency tests (M1 part) | M1i |
| EVT-06 | app schedules in `worker`; backup schedule in `backup` | Compose test (backup schedule absent until M6; `worker` runs `runworker`) | M1b |
| D16 | `migrate` before switch; startup gate unchanged | deploy test with a pending migration | M1g |
| D19 | data in Malaysia | G-VENDOR location answer | M1k |
| UNI-11 | services: iCore, GitHub/GHCR, ACME CA; alert channel not adopted until Q20 | G-VENDOR record; Q20 DECISIONS entry before the sender is enabled | M1k, M1j |
| UNI-12 | host work done by the operator | process; no agent write path to a host | all |

Packs judged not relevant to M1: money, finalized-records, auth (no login or session change; M2/M3), frontend (no UI; the maintenance page is a static error page and gets the FE checks that apply to text and `lang`). Public-links and payments are unticked.

## 7. Risks / what the reviewer should look at first

1. **Forced-command and `sudo` boundary (T25, T23).** `skiw-deploy-ssh` is the whole attack surface of a stolen key. Review the argument parser first; any shell use is a finding. Deploy accounts must not be in `docker`.
2. **Production refuses the staging key.** Both keys reach the same script; the decision must use the key role fixed in each key's `command=` in `authorized_keys`, never a caller-supplied value.
3. **Rollback state lives on the host.** The applied-contract list is derived from the deploy log; a break-glass migration outside `skiw-deploy` would bypass it. The runbook forbids that; the risk is recorded.
4. **No `NET_BIND_SERVICE` for Caddy (G13)** changes H1 wording; if refused, `no-new-privileges` must be relaxed for Caddy only, which is weaker.
5. **ClamAV in CI.** Signature downloads from CI runners may be rate-limited and add minutes; if so the EICAR case runs on staging and CI uses `clamd` only for the INSTREAM protocol path (decided in M1i, recorded).
6. **Memory fit [A].** H1 limits total ≈ 7.5 GB of 8 GB; staging NODE1 has 4 GB and will need lower limits in `staging.env` (H8 says 4 GB lets staging run ClamAV [A]). G-LOAD is the proof, not M1.
7. **GHCR quota and token.** Container registry is free "currently"; a policy change or a classic token compromise (reads every package of the account) are the exposures; yearly rotation and G10.
8. **Secrets in files, not env.** Every service must read `*_FILE`; `check-hardening` plus the Compose test catch a regression.
9. **PR count (G1).** If the owner prefers 4 PRs, the reviewer gets ≈ 1 000-line diffs.
10. **Unverified pins:** apt version strings, ClamAV LTS line and image user, age archive checksum, Dependabot digest handling (§2).

## 8. Not claimed

- No VPS exists; no host has been hardened, scanned or deployed to; no TLS certificate has been issued.
- No gate has passed: G-VENDOR, G-S1, G-DRILL, G-LOAD, G-BACKUP are all open, so no real client data may go on any host.
- No test in §3 or §6 has run; no digest, action SHA beyond those already in `ci.yml`, or apt version has been read for M1.
- iCore's location, IPv4 stability, backups, DPA, disk wipe and resource guarantees rest on its web page until G-VENDOR; nothing here says iCore is PDPA-compliant.
- The deploy outage length (10–30 s [A]) is not measured.

## 9. Spec gaps and contradictions found while planning (for the owner and reviewer)

1. §9 "each milestone is 1–4 PRs" vs ≈ 400 LOC per PR: M1 needs about 11 (G1).
2. H1 Caddy "non-root with `NET_BIND_SERVICE` only" vs H2 daemon default `no-new-privileges: true`: file capabilities are not gained under no-new-privileges (G13).
3. H3 step 4 runs "the `backup` service" for the pre-migration dump, but the `backup` service is M6; M1 builds a minimal pre-migration subset (§5) and needs the dump public key (G5).
4. "Staging checks passed" is not defined (G12); the staging-check mechanism is [A] (G11) and either option adds a secret name to the H4 inventory.
5. The H5 file-store harness is assigned to M1, but its `document` row, `with_agency()` and scan job are M4/M16 (G14).
6. "A 25 s long-poll completes through Caddy" has no long-poll endpoint before M14; M1 proves it with a stub upstream behind the real Caddyfile.
7. H4 forbids secrets in environment variables, but the app today reads `DJANGO_SECRET_KEY` and the DB password from env; M1b adds file-based reading.
8. Contract migrations: the spec requires labelling them, but `lintmigrations --warnings-as-errors` already rejects destructive operations, so a contract migration cannot pass CI today without a per-migration linter ignore; M1 adds the `skiw_contract` flag and labels and leaves the linter policy for the first real contract migration (reviewed then).
9. G-S1 asks `pg_dump` as `skiw_migrator` to fail on FORCE-RLS tables, but none exist before M4; the spike creates and drops a probe table.
10. `/readyz` is required by H1/§8.3 but assigned to no milestone; M1b adds it.
11. The local/CI role set (two roles, superuser `skiw_owner`) differs from the closed role set; M1e aligns them.
12. Owner naming: PROJECT.md §1 names the owner "Ying", spec §8.4 names the operator "Charlie, the owner"; this plan says "the owner" throughout and does not resolve it.

## Done when

- Every acceptance item of the spec §9 M1 row has evidence: CI items in M1a–M1j, host items in M1k, each linked in M1k's DECISIONS entry.
- G-VENDOR is recorded with every item marked (any blocking answer returned to the owner), and G-S1 results are recorded.
- The CDK skeleton is gone, `make host-test` runs in CI on every PR, and the deploy, rollback and host-rebuild runbooks describe what was built, with the measured outage.
- The PROJECT.md §7 follow-up PR has replaced `pending M1`.
