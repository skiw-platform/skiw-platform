# Guardrails — universal (always on)

**Stack:** any. The "Platform security" section applies to web apps.

The builder must follow these. The reviewer checks them on every change.

## Code
- **UNI-01** Strict typing on. No escape-hatch types (`any`, `# type: ignore`, etc.) without a comment saying why.
- **UNI-02** No business value hardcoded in code: prices, rates, percentages, limits, expiry windows, tax, numbering patterns, reminder timing. They live in the config location named in `PROJECT.md` §8, with an audit trail on change.
- **UNI-03** Validate at system boundaries. Trust internal code.
- **UNI-04** Module boundaries in `PROJECT.md` §9 are enforced by tooling (lint rules, package exports), and CI fails on a violation. A boundary that only lives in prose is a finding.
- **UNI-05** No dead code, unused imports, commented-out blocks, or duplicated logic left behind.
- **UNI-06** Every new dependency passes the ladder in the decisions log: needed at all? can the platform or framework do it? does an existing dependency do it? maintained? size cost? licence and supply-chain OK?

## Secrets and data
- **UNI-07 (hard)** No secrets in the repo. Only `.env.example` with placeholder values.
- **UNI-08** Production secrets come from a secrets manager or the host's secret store, never a committed file.
- **UNI-09** Logs, error trackers and analytics carry no PII, tokens, passwords or secret values.
- **UNI-10** Audit logs are append-only.
- **UNI-11** No project data, client data or code is sent to an external service (AI tool, converter, uploader) unless the owner has authorised that service for this project.
- **UNI-12** Agents write only inside the project folder. Never into a parent folder, a sibling project, or the master kit.

## Delivery
- **UNI-13** CI runs typecheck, lint, tests, a production build, dependency audit and secret scan (plus a container image scan if the app ships as an image). Failing CI blocks merge.
- **UNI-14** Lockfile committed. Build tooling and integrations pinned; no floating `latest` in CI or deploy.
- **UNI-15** Database migrations are additive (expand → migrate → contract). Never a destructive change in the same release as the code that stops using the old shape.
- **UNI-16** A change to deployment, env vars, domains or auth updates its runbook in the same PR.

## Platform security (web apps)
- **UNI-17** Nonce-based CSP, HSTS, `frame-ancestors 'none'` (unless embedding is a feature). Where the headers are actually applied (app, proxy, host config) is recorded in the decisions log, and a test asserts the config.
- **UNI-18** Cookies: `Secure`, `HttpOnly`, `SameSite`.
- **UNI-19** Only intended endpoints are unauthenticated (health check, signed webhooks). No cron-by-HTTP endpoints; scheduled work runs in a worker.
