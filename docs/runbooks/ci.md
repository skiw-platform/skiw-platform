# Runbook — CI and security gates

Workflow: `.github/workflows/ci.yml`, on every pull request and on pushes to `main`. Runner
`ubuntu-24.04`, `permissions: contents: read`, every action pinned by full commit SHA. No AWS
credentials, no OIDC, no secrets.

## Jobs (run in parallel)
| Job | What it runs | Run it locally |
|---|---|---|
| `checks` | install, `make lint`, `make typecheck`, `make test`, `make test-live`, Playwright (`make e2e`) | the same `make` targets |
| `security` | gitleaks over full history, `pip-audit --strict`, `pnpm audit --audit-level high`, Semgrep registry rulesets | `make audit` (needs gitleaks); Semgrep below |
| `image` | `docker build` (web stage + manifest check), Trivy HIGH/CRITICAL, no push | `make image-scan` (needs trivy) |
| `infra` | CDK synth test (`infra/tests/test_synth.py`): empty stack, region `ap-southeast-5`, no account | `make infra-test` |

Gate details:
- **gitleaks** v8.30.1: the workflow downloads the release binary and verifies its SHA-256 before use. Config `.gitleaks.toml` = defaults plus the key names of `agents/PROJECT.md` section 7 (a literal value assigned to one is a finding; `docs/specs/**` is exempt from that one rule only). To bump: new version and the checksum from the release's `*_checksums.txt` in the workflow.
- **pip-audit** 2.10.1 on `uv export --frozen --all-groups --no-hashes` (`make audit-python`); **pnpm audit** (`make audit-web`).
- **Semgrep** 1.179.0, anonymous, `--metrics=off` (UNI-11): `uvx semgrep==1.179.0 --config p/python --config p/django --config p/typescript --config p/react --metrics=off --error app infra web/src`. The custom rules in `semgrep/` run in `make lint`. If the registry ever needs a login or fails to download, do not add one: remove the registry step and record the fallback to the custom rules in `docs/DECISIONS.md`.
- **Trivy** v0.75.0 (`trivy-action` v0.36.0) fails on HIGH or CRITICAL with `ignore-unfixed: true`: a finding with no upstream fix has no action available; Dependabot (Docker) moves the pinned base digests when a fix ships. Review unfixed findings by running Trivy without that flag.

## Local hook (the only pre-push control)
`make hooks` sets `core.hooksPath` to `.githooks` (once per clone). `.githooks/pre-push` runs gitleaks over the commits being pushed and blocks the push on a finding. It fails closed: without gitleaks installed (`brew install gitleaks`) the push is blocked. The one escape is `SKIW_SKIP_SECRET_SCAN=1 git push`, which prints a warning; CI still scans.

## GitHub Free plan limitations (private repo; owner decision 2026-10-10, option A)
These GitHub features are not available, so they are not relied on:
- **No branch protection or rulesets.** GitHub does not block a merge on red CI. Merge discipline is the agent-kit gate: CI green on the exact head commit and an approved review receipt before the owner merges (`agents/START.md`). Nothing technical stops a direct push to `main`; the builder never pushes there.
- **No secret-scanning push protection.** gitleaks in CI detects a secret only after it is pushed (and it is then in history: rotate it). The pre-push hook is the only pre-push control; it is local and bypassable (`--no-verify`, no `make hooks`, the env escape).
- **No CodeQL / code scanning** and **no dependency-review action.** Semgrep, pip-audit and pnpm audit cover part of this; they do not review a pull request's new dependencies.
- **Enabled:** Dependabot alerts and security updates; `.github/dependabot.yml` adds weekly version updates (uv, npm, GitHub Actions, Docker; minor and patch grouped).
- **Revisit GitHub Pro (or Team) before production** to get branch protection with required checks, push protection and code scanning.
