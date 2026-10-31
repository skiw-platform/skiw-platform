# PR 77 — fix(accounts): auth groundwork for M3 (M3a)

- **Merged:** 2026-10-31T14:46:02Z (GitHub) · **Merge commit:** 77d0569a44090e59a1f1c26dc4350b3eb0a35558 · **Branch:** fix/m3a-auth-groundwork
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-77.receipt` on agent-logs (review commit 4639dc2852faeedcb0e3f97c6518457314291edb); head 5b3c6a99 and review-file hash 6b170407 match the final round; written 2026-10-31T14:43:45Z, before the merge
- **Merge evidence:** `gh pr view 77` state MERGED, merge commit above, merged 2026-10-31T14:46:02Z; commit is an ancestor of the fetched `origin/main`; final head SHA 5b3c6a9942b06dbadb46a4bd0b9ffc332c667187 equals the reviewed SHA
- **Drafted by:** Opus sub-agent (code), Claude Sonnet 5.5 (checks, commit, PR); reviewer Claude Opus 5.5 · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3 (M3a)

## What changed
`django.security` warnings now reach stderr with `DEBUG` off (closes the PR 74 deferred P2). The key version is bounded to six digits at both readers. A test proves a fresh `SessionStore` loads a renewed row. `runworker` checks `tenant_source_key` at start-up. The TEN-10 contract gets `accounts.models` in its forbidden list and one named edge `config.urls -> accounts.views` (owner Q10 (a)), with three Semgrep rules and contract fixture tests. The e2e base URL moves to `http://localhost:8000`; Chromium keeps the `__Host-csrftoken` cookie there. The DECISIONS entry records the M3 plan answers (all (a)), the PR 74 answers and the PR 75 evidence correction.

## Why
Plan M3a: the stderr warning must exist before any login route merges; the other items close the PR 74 and PR 75 carry-overs.

## Review rounds
- R1: Approved. No P0/P1/P2. Two P3 notes (below).

## Deferred conditions
- [P3] DECISIONS and the PR body say the localhost cookie test has not run on the CI Linux runner, but CI run 41206976831 ran it (38 e2e passed) → add a dated note to M3a point (8) in the next PR that touches `docs/DECISIONS.md` (M3b).
- [P3] Nothing forces `unmatched_ignore_imports_alerting` back to the default → M3e removes the option and adds a check that fails while `config/urls.py` imports `accounts.views` and the option is present.

## Decisions worth keeping
- Reviewer residual risk: Django `django.request` ERROR records (500 tracebacks) still go only to `mail_admins` and the debug-only console, so a 500 on a host leaves no line in the container log. Fix before the first login route: send `django.request` ERROR to stderr (M3b or M3e), or the owner decides otherwise.
- Optional: add the multi-name import form (`from accounts import views, session`) to the Semgrep rule; import-linter already catches it.
- The worker now checks the key at start-up (reverses M2c deviation (e)).
- The Semgrep rule allows `config/asgi.py -> accounts.source_key` (exists since M2c).
- The stderr line is proven in a subprocess, not under the real uvicorn entrypoint; the first `host_live` login test (M3e) should prove it end to end, and should include an accepted same-origin POST through Caddy.
- Size was about 420 lines of code against the plan's 230 (production about 37).

## Follow-ups
- M3b: add the CI-run note to DECISIONS (P3); consider `django.request` ERROR to stderr.
- M3e: reset `unmatched_ignore_imports_alerting`, add the check, add a `host_live` same-origin POST case and an end-to-end stderr check.
- Next: M3b (`feat/m3b-auth-crypto`): `cryptography` and `argon2-cffi`, the `login_blob_key` reader, `accounts.auth.blob`, `accounts.auth.passwords`, interim `SKIW_AUTH_*` config.

## Appendix — final review round
## Round 1 — 2026-10-31 · scope: slice (M3a, first PR of M3; plan `docs/plans/2026-10-31-m3-auth.md` §3 M3a)
- **Code review:** base (merge base) `192a5507104f6514d8d3bedd41c4ba289e041859` · head `5b3c6a9942b06dbadb46a4bd0b9ffc332c667187` · head re-checked at end: yes (GitHub)
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371` (unchanged by this PR)
- Review checkout: `.agent/worktrees/review-77-5b3c6a99` (detached worktree at the head SHA). Planted-regression checks ran on a separate copy in the reviewer's scratch folder, never in the checkout.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No — M3b (crypto) needs the deep tier.

### Findings

No P0, P1 or P2 findings. Each M3a item in the plan is built and tested:
- (a) `django.security` now reaches the real stderr with DEBUG off. This closes the PR 74 deferred P2.
- (c) The key version is bounded to six digits at both readers.
- (d) A fresh store reads the renewed row, sync and async.
- (j) `runworker` checks the key before the migration check. The worker gets the key in every context: host `secrets.py:45` (`WEB_WORKER`), `infra/host/compose.yml:36,43`, local `docker-compose.yml:52`.
- (k) Chromium keeps `__Host-csrftoken` on `http://localhost`.
- Q10 edge: one named ignore, with Semgrep rules and contract fixture tests.
- (e) The DECISIONS entry records the owner answers as I recorded them in `.agent/reviews/PR-76.md` Round 2.

### [P3] DECISIONS and the PR body say the localhost cookie test has not run on the CI Linux runner, but it has
- Category: defect (documentation)
- Rule: reviewer role §3 (evidence must match); UNI-13
- Evidence: the PR body, "Not proven here": "(k) has not run on the CI Linux runner". DECISIONS M3a point (8): "not yet run on the CI Linux runner". CI run 41206976831 on `5b3c6a99`, `checks` job, "End-to-end tests": "38 passed". No workflow sets `E2E_BASE_URL` (`grep` over `.github/workflows/`), so CI used the new default `http://localhost:8000`.
- Failure scenario: a later reader thinks the Linux result is unknown and repeats the spike, or adds the Caddy `tls internal` fallback for nothing.
- Required correction: in the next PR that touches `docs/DECISIONS.md` (M3b), add a dated note to M3a point (8): CI run 41206976831 (Linux, both Playwright projects) passed the cookie test. Do not re-push PR 77 for this.
- Owner: builder
- Verification: the note is in `docs/DECISIONS.md` on `main`.
- Status: open

### [P3] Nothing forces `unmatched_ignore_imports_alerting` back to the default
- Category: test gap
- Rule: UNI-04; owner Q10 (a)
- Evidence: `pyproject.toml`: `unmatched_ignore_imports_alerting = "warn"`. The comment there and DECISIONS M3a point (7) say the first login-route PR "sets the option back to the default (error)". No test checks it.
- Failure scenario: M3e mounts the first view and forgets the switch. Later the edge goes away (a refactor), and the stale ignore stays in the contract with only a warning. The contract still holds, so the harm is small, but the planned step is easy to miss.
- Required correction: in M3e, remove the option, and add a check (for example in `app/documents/tests/test_import_contracts.py`) that fails while `config/urls.py` imports `accounts.views` and the option is still present.
- Owner: builder
- Disposition: deferred to M3e
- Verification: the M3e review checks it.
- Status: open

### Notes (no severity)
- **The builder's ASK (owner).** I advise the owner to accept all three items.
  - **Size, about 420 lines.** Production code is about 37 lines. The rest is tests and Semgrep rules. It is under the 450 split line.
  - **The `config/asgi.py -> accounts.source_key` allowance.** That import has existed since M2c (DECISIONS M2c deviation (a)). Without the allowance, the rule would fail on `main`.
  - **`warn` on the unmatched ignore.** It hides no edge: an ignore that matches nothing removes nothing from the graph. The P3 above covers the switch back.
- **The Semgrep rule misses a multi-name import, but import-linter catches it.** In a scratch copy, the rule did not flag `from accounts import views, session` in `config/urls.py`. Import-linter did catch it: "BROKEN … `config.urls -> accounts.session` (l.12, l.13)". So there is no gap now. If Semgrep becomes the only guard for a path (string imports), keep this in mind.
- **What else now reaches stderr.** DECISIONS point (4) lists the CSRF refusal line (it holds the client's `Origin` or `Referer` value) and `DisallowedHost`. These carry client-sent header values, not secrets. Django escapes control characters in them.
- **No text in the PR body is addressed to an AI agent.**
- **Owner answers in DECISIONS.** They match my record in `.agent/reviews/PR-76.md` Round 2 ("all a", Q1–Q10).

### Self-check audit

Note: I read the PR body (with the self-check table) before I built this list, because the body and the metadata came in one call. I built the list from the diff, not from the table.

My applicability list:
- UNI-01, 03, 04, 05, 07, 08, 09, 13, 16 apply: new code, a bound on input, a new contract edge and Semgrep rules, log output, runbooks.
- UNI-17 and 18 apply through the e2e cookie check.
- UNI-02, 06, 10–12, 14, 15 and 19 are n-a: no value, dependency, audit, external service, lockfile, migration or route.
- AUTH-02 and AUTH-11 do not apply yet: no route and no middleware.
- TEN-10 applies (contract). Other TEN rules are n-a.
- FE-50 and FE-70 apply (e2e config and spec change).
- PROJECT §9: the key mounts (unchanged) apply.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy: 122 files, no issues | none |
| UNI-03 | yes (`KEY_LINE`) | pass | pass | `v1000000` refused at `require_key`, `config.asgi`, `runworker`, `bootstrap-secrets restore`; `v999999` round-trips | none |
| UNI-04 | yes | pass | pass | 10 contracts kept; contract fixture tests; Semgrep 5 of 6 planted cases flagged, the 6th caught by import-linter | none |
| UNI-05 | yes | pass | pass | the stale M2b comment in `pyproject.toml` is replaced | none |
| UNI-07, 08 | yes | pass | pass | keys made per test run; added-line scan clean | none |
| UNI-09 | yes (log output) | pass | pass | stderr test checks no key, MAC, blob or stored key; planted `level: ERROR` fails it | none |
| UNI-13 | yes | pass | pass | new tests in the existing `checks` and `host` jobs; CI 41206976831 green | none |
| UNI-16 | yes | pass | pass | `local-dev.md`, `host-rebuild.md` updated | none |
| UNI-17, 18 | yes | pass | pass | e2e cookie attributes asserted; CI e2e 38 passed | none |
| UNI-02, 06, 10–12, 14, 15, 19 | n-a | n/a or pass | n/a | no value, dependency, audit, service, lockfile, migration or route | none |
| AUTH rules | n-a (no route yet) | n/a | n/a | — | none |
| TEN-10 | yes | pass | pass | `accounts.models` now forbidden; one named edge (owner Q10 (a)) | none |
| Other TEN | n-a | n/a | n/a | no table or grant change | none |
| FE-50, FE-70 | yes | pass | pass | CI `checks` (web build, e2e 38 passed, console and CSP tests) | none (the PR 75 P3 is closed) |
| PROJECT §9 | yes | pass | pass | key mounts unchanged; the worker already had `tenant_source_key` | none |

### Verification performed
| Command / check | Result |
|---|---|
| `git diff --check 192a550...5b3c6a9` | clean |
| `make lint` | ruff pass; 10 contracts kept (TEN-10 "KEPT (1 warning)"); Semgrep 9 rules, 0 findings; `--test` 9/9 |
| `make typecheck` | mypy: no issues in 122 files; `tsc` pass |
| `make test` | 1142 passed; vitest 4 passed |
| `make host-test` | 819 passed |
| `make test-live` (Docker db) | 126 passed |
| Planted (scratch): `django.security` handler level `ERROR` | stderr test: 1 failed; control on the clean copy: 6 passed |
| Planted (scratch): 6 bad `accounts` imports in `app/config/` | Semgrep flagged 5; `from accounts import views, session` in `urls.py` was not flagged by Semgrep, and import-linter broke the contract on it |
| `make host-test-live`, `make e2e` | not run locally; CI run 41206976831 on `5b3c6a99`: host-test-live 33 passed, e2e 38 passed (Linux, `localhost` default). These match the PR body. |
| Added-line secret scan; PR body scan for agent-addressed text | clean; none |
| Clean-up: `docker compose down -v`, `rm .env`, `git clean -fdX` | done; no containers or volumes left |
| End: GitHub head re-read; checkout `git status --untracked-files=no` | unchanged; clean |

### Residual risks and test gaps
- **Server errors are still silent on hosts.** Django's `django.request` ERROR records (500 tracebacks) still go only to `mail_admins` (no `ADMINS` set) and to the debug-only console. With DEBUG off, a 500 leaves no line in the container log. This PR did not cause it and the plan did not cover it. It matters before the first login route. M3b or M3e should send `django.request` ERROR to stderr as well, or the owner should accept the gap.
- The stderr line is proven in a subprocess, not under the real uvicorn entrypoint or in a host container log. The first `host_live` login test (M3e) can prove it end to end.
- No accepted same-origin POST through Caddy yet (PR 75 residual). M3e should add one.
- `bootstrap-secrets restore --allow-new-key-version` on a `v999999` key would mint `v1000000`. This is recorded in DECISIONS and cannot happen in practice.

### Required before merge
- None.

### Deferred conditions
- P3 `warn` switch-back → M3e.
- P3 DECISIONS CI note → M3b.

### Optional improvements
- Send `django.request` ERROR to stderr (see residual risks), in M3b.
- Add the multi-name import form to the Semgrep rule for defence in depth.
