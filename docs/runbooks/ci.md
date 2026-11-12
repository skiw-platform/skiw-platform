# Runbook — CI and security gates

Workflow: `.github/workflows/ci.yml`, on every pull request and on pushes to `main`. Runner
`ubuntu-24.04`, `permissions: contents: read` for the workflow, every action pinned by full commit
SHA with its version in a comment. No cloud credentials, no OIDC. One secret, `STAGING_DEPLOY_KEY`,
read only by `deploy-staging`; only `publish` has `packages: write` (with the job's own
`github.token`); no production credential exists in GitHub (Q42). A newer push to a pull request
cancels its older run. On `main` a running publish or deploy is never cancelled; a waiting run is
replaced by a newer push (GitHub keeps one pending run per concurrency group), so that commit gets
no image, and `scripts/deploy-prod` refuses its run because it did not succeed.
`infra/host/tests/test_workflows.py` asserts these rules.

## Jobs (the gates run in parallel)
| Job | What it runs | Run it locally |
|---|---|---|
| `checks` | install, `make lint`, `make typecheck`, `make test`, `make test-live`, Playwright (`make e2e`) | the same `make` targets |
| `security` | gitleaks over full history, the gitleaks rule test, `pip-audit --strict`, `pnpm audit --audit-level high`, Semgrep registry rulesets | `make audit` and `make secrets-test` (need gitleaks); Semgrep below |
| `image` | `docker build` (web stage + manifest check), Trivy HIGH/CRITICAL; then the same for the pre-migration dump image (`infra/host/backup/predeploy`), on every PR whatever `SKIW_PUBLISH_PREDEPLOY` says; no push | `make image-scan` (needs trivy); the dump image: `docker build -t skiw-predeploy:ci infra/host/backup/predeploy`, then `trivy image --severity HIGH,CRITICAL --exit-code 1 skiw-predeploy:ci` |
| `host` | host tooling unit tests and Compose config tests (`infra/host/tests`, spec §8.4), then the live edge tests through Caddy (builds the app image, Docker on the runner, no host, secrets generated per run), the role and `pg_hba` tests, and EICAR and scan-limit hits through the pinned clamav image with its `CLAMD_CONF_*` settings (`app/documents/tests/test_clamd_live.py`) | `make host-test`, `make host-test-live` |
| `publish` | push to `main` only, after the four gates: build the app image once, label it from `migration_labels`, Trivy HIGH/CRITICAL on that image, push `ghcr.io/skiw-dev1/skiw-platform:<commit>`, artifact `image-digest` (`digest.txt`, 30 days); with variable `SKIW_PUBLISH_PREDEPLOY=enabled` also the dump image `ghcr.io/skiw-dev1/skiw-predeploy` and artifact `predeploy-digest` | build and label steps: `docker build`, then [deploy.md](deploy.md) "CI: publish"; no local push |
| `deploy-staging` | after `publish`, only with variable `SKIW_STAGING_DEPLOY=enabled`: `ssh skiw-deploy@<staging> deploy <digest> <run id>` with the staging key, host key pinned from `infra/host/env/staging.env` | not run locally; [deploy.md](deploy.md) "Turn on the staging deploy" |

Gate details:
- **gitleaks** v8.30.1: the workflow downloads the release binary and verifies its SHA-256 before use. Config `.gitleaks.toml` = defaults plus the key names of `agents/PROJECT.md` section 7 (a literal value assigned to one is a finding in every path, including `docs/specs/`; there are no path exemptions, and bare names pass). To bump: new version and the checksum from the release's `*_checksums.txt` in the workflow.
- **pip-audit** 2.10.1 on `uv export --frozen --all-groups --no-hashes` (`make audit-python`); **pnpm audit** (`make audit-web`).
- **Semgrep** 1.179.0, anonymous, `--metrics=off` (UNI-11): `uvx semgrep==1.179.0 --config p/python --config p/django --config p/typescript --config p/react --metrics=off --error app infra/host web/src scripts` (`scripts/deploy-prod` has a Python shebang and no suffix; Semgrep and, through `extend-include`, ruff read it; `make typecheck` runs mypy on it). The custom rules in `semgrep/` run in `make lint`. If the registry ever needs a login or fails to download, do not add one: remove the registry step and record the fallback to the custom rules in `docs/DECISIONS.md`.
- **upload-artifact** v7.0.2 (`actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9`, the commit the `v7.0.2` tag points to, checked 2026-10-23), in `publish` only, with `if-no-files-found: error`, no `overwrite`, 30-day retention.
- **Repository variables** (Settings → Secrets and variables → Actions → Variables, or `gh variable set`): `SKIW_STAGING_DEPLOY` and `SKIW_PUBLISH_PREDEPLOY`, each `enabled` or absent. Both are absent until M1k and the dump image fix; see [deploy.md](deploy.md).
- **Trivy** v0.75.0 (`trivy-action` v0.36.0) fails on any HIGH or CRITICAL finding in the image, whether or not an upstream fix exists (no `--ignore-unfixed`, no ignore file). The runtime base is `python:3.12.15-alpine` by digest, chosen because it has no HIGH/CRITICAL findings (Debian slim had 44 with no upstream fix). Dependabot (Docker) proposes new base digests. If a new finding fails the build: update the base digest, remove the package, or change the base image. Accepting a finding needs an owner-approved, reviewed plan or spec policy with each finding assessed (package and version, reachability, mitigation, owner, review date); the builder does not add suppressions.

## Local hook (the only pre-push control)
`make hooks` sets `core.hooksPath` to `.githooks` (once per clone). `.githooks/pre-push` runs gitleaks over the commits being pushed and blocks the push on a finding. It fails closed: without gitleaks installed (`brew install gitleaks`) the push is blocked. The one escape is `SKIW_SKIP_SECRET_SCAN=1 git push`, which prints a warning; CI still scans.

## GitHub Free plan limitations (private repo; owner decision 2026-10-10, option A)
These GitHub features are not available, so they are not relied on:
- **No branch protection or rulesets.** GitHub does not block a merge on red CI. Merge discipline is the agent-kit gate: an approved review receipt before the owner merges (`agents/START.md`). Confirming CI green on the exact head before `approved N` is a recorded builder working rule (`docs/DECISIONS.md` 2026-10-10), not a step of `agents/START.md`, until the owner changes the kit. Nothing technical stops a direct push to `main`; the builder never pushes there.
- **No secret-scanning push protection.** gitleaks in CI detects a secret only after it is pushed (and it is then in history: rotate it). The pre-push hook is the only pre-push control; it is local and bypassable (`--no-verify`, no `make hooks`, the env escape).
- **No CodeQL / code scanning** and **no dependency-review action.** Semgrep, pip-audit and pnpm audit cover part of this; they do not review a pull request's new dependencies.
- **Enabled:** Dependabot alerts and security updates; `.github/dependabot.yml` adds weekly version updates (uv, npm, GitHub Actions, Docker, Docker Compose for `/` and `/infra/host`; minor and patch grouped).
- **Revisit before production:** GitHub Pro (or Team) adds branch protection with required checks on private repositories. Secret push protection and code scanning on private repositories are separate paid GitHub products with their own eligibility, not included by Pro or Team alone; check the current terms at https://docs.github.com/en/get-started/learning-about-github/githubs-plans before deciding.
