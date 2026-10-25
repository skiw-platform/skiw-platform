# Runbooks

| Runbook | Status |
|---|---|
| [local-dev.md](local-dev.md) | Done (M0a-M0d) |
| [ci.md](ci.md) | Done (M0d): jobs, local gate commands, GitHub Free plan limits |
| [deploy.md](deploy.md) | Staging and production deploy, staging check, accepted-digest record (M1g); CI publish, staging deploy job, `scripts/deploy-prod` (M1h); measured values M1k |
| [rollback.md](rollback.md) | Automatic switch-back and manual `rollback` (M1g) |
| [restore.md](restore.md) | Pre-migration dump restore (M1g); backups and restore drill in M6 |
| [health-alerts.md](health-alerts.md) | Health checks every 5 minutes, monthly `check-hardening`, the alert message (M1j); turning on the Telegram alert channel, rotating its token, the weekly heartbeat and the UptimeRobot ping (M1j-2); real-host proof M1k |
| [host-rebuild.md](host-rebuild.md) | Host files, users, packages and units (M1f-1a, M1f-1b), secrets (M1d), database roles (M1e), hardening check (M1f-2a, M1f-2b); measured values M1k |
| [incident-pdpa-breach.md](incident-pdpa-breach.md) | Skeleton; filled in M6 |

A change to deployment, env vars, domains or auth updates its runbook in the same PR (UNI-16).
