# PR 36 — feat(infra): Caddy edge, maintenance page and live edge tests (M1c)

- **Merged:** 2026-10-14T03:04:14Z (GitHub) · **Merge commit:** `927d891833a101e321e664ac7a3016436832bf4f` · **Branch:** `feat/m1c-caddy-edge` (final head `1462c6add30eb2e910a656c06e6ad4ba32de0a19`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-36.receipt` on `agent-logs` (written before the merge); names head `1462c6a…`, review `reviews/PR-36.md`, CI green on that exact head (run 38499645520: checks, host, image, security).
- **Merge evidence:** `gh pr view 36` → MERGED, mergedAt 2026-10-14T03:04:14Z, merge commit `927d891`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 927d891 origin/main` succeeded; `infra/host/caddy/` is on `origin/main`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1c

## What changed
Caddy edge: `infra/host/caddy/{edge.caddy,Caddyfile,ci.Caddyfile,maintenance.html}`. One HSTS header (`max-age=31536000`) on the plain-HTTP 308 redirect (fixed HTTPS target), app responses and the maintenance page; `request_body max_size 25MB`; `reverse_proxy web:8000` with 60 s timeouts; `handle_errors 502 503 504` serves the maintenance page with status 503 and `Retry-After: 30`; no `trusted_proxies`; admin off; `tls internal` only in `ci.Caddyfile`. `SECURE_PROXY_SSL_HEADER` only when `DJANGO_BEHIND_CADDY` is true (`env.flag`). Compose: read-only Caddy file mounts and `DJANGO_BEHIND_CADDY: "1"` for web and worker. Live tests `infra/host/tests/test_edge_live.py` (7 `host_live` + 1 static) with a test-only override, probe view and stub; `make host-test-live` is real and runs in the CI `host` job. Browser checks `web/e2e/maintenance.spec.ts` (16 runs: structure, no overflow at 360/768/1280, axe WCAG 2.2 AA, no scripts, no-JS, no console errors).

## Review rounds
- R1 (Revision required): [P1] `Stack.fetch` used `**kwargs: Any` with no justification → explicit keyword signature. [P1] maintenance page (UI) was excluded from the frontend rules and had no browser proof → browser spec and FE/A11Y self-check rows.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- Not proven yet: real ACME certificates, DNS and G9 hostnames, `/readyz` 200 through a publicly valid certificate, `caddy-data` writability on a host (M1k).
- Open owner items: G13 (Caddy ports; a non-root Caddy bound 80/443 locally because Docker sets `ip_unprivileged_port_start=0`), UDP 443 and HTTP/3 (publish with a firewall rule in M1f, or set `servers { protocols h1 h2 }`), `Retry-After` value (measured in M1k), HSTS scope (no `includeSubDomains` or `preload`).
- `env.flag` accepts `1`, `true`, `yes`, `on` (case-insensitive); `DJANGO_BEHIND_CADDY` follows it.
- A plain-HTTP request with a Host other than `SKIW_HOSTNAME` gets Caddy's automatic 308 to the same host, with no HSTS.
- Follow-up: `agents/PROJECT.md` section 7: the `make host-test-live` line (still "a stub until M1c, M1e and M1i") and the `make typecheck` line (`mypy app infra` vs `app infra/host`).
