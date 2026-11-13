# PR 153 — feat(config): M3g-1a-1 passkey relying-party settings and start-up check

- **Merged:** 2026-11-13 (04:57:38 UTC) · **Merge commit:** 03e7e2dbd5ba07325749e1a9cc3a8001f3dd3327 · **Branch:** feat/m3g-1a1-settings (final head 5a57fef50de6fc2b0e294bda0fda97e935d34b8b)
- **Gate breaches:** none. The review's final round (R1) head SHA equals the PR's final head; the receipt (2026-11-13T04:57:22Z, review-file hash 2a409e7c, log-branch commit 2620545) precedes the merge by 16 seconds. Close, but before.
- **Approval receipt:** `reviews/PR-153.receipt` on agent-logs (review at commit e648f4a).
- **Merge evidence:** `gh pr view 153` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-13T04:57:38Z, merge commit 03e7e2d; reachable from fetched origin/main.
- **Drafted by:** a deep-tier (Opus) sub-agent for the design and code, Sonnet 5.5 for the split, gates and PR body · **Reviewed by:** Claude Opus 5.5 (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** M3 §1 M3g row, amended 2026-11-13 · **Milestone:** M3, package M3g (first of the server PRs)

## What changed
`config.env.webauthn()` (RP ID must be a lowercase hostname; the origin is derived as `https://<RP ID>`, and only `localhost` may use `http` or a port), `SKIW_WEBAUTHN` setting, start-up check in `config/asgi.py`, wiring in `.env.example`, local and host Compose (`web` only; hosts set only `SKIW_WEBAUTHN_RP_ID` from `SKIW_HOSTNAME`), host env comments, runbooks, tests, plan amendment and DECISIONS "M3g-1". +233/-4 over 18 files. No library, route, table or behaviour change; nothing reads the setting yet.

## Why
Plan M3g, owner Q8 (a): the RP ID is the exact app hostname per environment. The deep-tier measurement found the server half is about 1 700 lines, so the owner agreed (2026-11-13) to four server PRs and to cutting 1a in two.

## Review rounds
- R1: Approved, no P0 to P2. Two P3s, below.

## Deferred conditions
none. P3 #1 (a test that the localhost origin exception needs RP ID `localhost`; mutant W3 survived) to be added with M3g-1a-2; P3 #2 (forward note: review and parallel checkouts that run the M3g-2 virtual-authenticator e2e on other ports need `SKIW_WEBAUTHN_ORIGIN=http://localhost:<port>`; the M3g-2 runbook line should say so).

## Decisions worth keeping
- The origin is derived, not a second free value, because UNI-19 keeps URLs out of the host Compose file. The host deploy check (`SKIW_HOSTNAME`) is stricter than the app's RP ID rule, so every deployable hostname passes; `localhost` can never reach a host.
- Changing the RP ID later invalidates every passkey (TOTP and recovery codes keep working).

## Follow-ups
- Owner ask: the G9 hostname for each environment is also the passkey RP ID; fix it before the first passkey is registered.
- M3g-1a-2 (dependency, single-use challenge, ceremony primitives; built locally, about 840 lines, over the 600 rule, so the owner is asked first), then 1b (credential lookup migration), 1c (add and remove a passkey), 1d (sign-in and step-up branches), M3g-2 (screens, e2e), M3 gate review.
- Carried: main checkout `.env` needs the two `SKIW_WEBAUTHN_*` lines; PR 152 conditions (dialog follow-ups, AUTH-13 browser probe, runbook line for e2e reruns); older P3s.

## Appendix — final review round
## Round 1 — 2026-11-13 · scope: slice (M3g-1a-1; `config.env.webauthn`, its start-up check, wiring in local and host Compose, host env comments, runbooks, plan and DECISIONS amendment; no library, route, table, migration or behaviour change)
- **Code review:** base (merge base) 9ba92a4f272ecfc477a22d6702bcc27679e98ccc (= `origin/main`, PR 152 merged) · head 5a57fef50de6fc2b0e294bda0fda97e935d34b8b · one commit · +233/−4 over 18 files · head re-checked at end: yes (PR open, main unmoved; detached checkout `git status --untracked-files=no` clean, removed without `--force`)
- **Spec:** v1.22 D7 (optional passkeys), owner Q8 (a) (the RP ID is the exact app hostname per environment). Plan M3 §1 M3g row as amended 2026-11-13. DECISIONS "2026-11-13 — M3g-1". The owner's answers of 2026-11-13 (four server PRs; 1a split in two) match the amendment.
- **CI:** green on this head: `checks`, `security`, `image`, `host` success; `publish`, `deploy-staging` skipped (PR event).
- **Size:** +233, well under the split point.

**Verdict:** Approved.
**Model used:** Claude Opus 5.5 (deep tier, as the PR asked) · **Switch model next step?** No. Keep the deep tier for M3g-1a-2: a new crypto dependency, the single-use challenge and the ceremony checks. It is about 840 lines, so the size question comes to the owner first.

### Applicability (reviewer's own list) and self-check audit
UNI-02 (a deployment value lives in env config, validated, fails closed: met), UNI-03 (validated at the boundary, which is start-up: met), UNI-05 (one validator, used once: met), UNI-07 (hard; no secret: met, gitleaks in CI green), UNI-09 (errors name the variable, never the value: met, and mutant W9 is killed), UNI-13 (met), UNI-16 (env var and auth config change with three runbooks: met), UNI-19 as the project tests it (no `http` in `infra/host/compose.yml`, `test_uni_19_no_unit_or_service_is_triggered_over_http`: met, and this is the real reason the origin is derived). AUTH, TEN, FE: no route, table or screen, so n/a. UNI-06 (dependency ladder) belongs to 1a-2. I agree with the self-check.

### What I checked
- **RP ID rule (`config/env.py`).** Labels follow DNS LDH rules, 1 to 63 characters, with no edge hyphen. The lookahead sits before the last label, cannot cross a dot, and so checks only that the last label holds a letter. That refuses every dotted-quad IP, and `[::1]` fails on the bracket. `fullmatch` refuses a trailing newline. Python's `[a-z]` is ASCII only on `str`, so `skiw.tést` is refused. The 253-character cap holds even when every label is valid (a 256-character name is tested).
- **Origin rule.** If the origin is unset it is `https://<RP ID>`; if set it must equal that exactly. The one exception is RP ID `localhost`, with `http` or `https`, an optional port 1 to 65535 and no leading zero. A set but empty value is refused, not defaulted (mutant W6 killed).
- **The host side is stricter than the app, which is the right order.** `infra/host/skiw_host/deploy.py:62` (`HOSTNAME`) requires at least one dot and a letters-only last label of 2 to 63 characters. So every `SKIW_HOSTNAME` a deploy accepts also passes `env.webauthn()`, and `localhost` can never reach a host. The host Compose passes only the RP ID, so the origin there is always `https://<SKIW_HOSTNAME>`. The `http` and port exception cannot reach staging or production.
- **Start-up.** `config/asgi.py` checks it after the three keys and before `require_migrated()`. The new test shows the check runs before the migration check. Both the image (`gunicorn config.asgi:application`) and local dev (`uvicorn config.asgi:application`) go through it. The worker and `migrate` never read it, and the Compose test pins `web` as the only holder.
- **Runbooks.** `host-rebuild.md` "The passkey relying party", `deploy.md` and `local-dev.md` say what is set where, that an old `.env` stops every `docker compose` command, and that changing the RP ID, or restoring onto another hostname, invalidates passkeys while TOTP and recovery codes keep working. These steps can be carried out as written.

### Builder's questions
- **Is the RP ID rule tight enough, and not too tight?** Yes on both. It cannot be looser than the deploy check in effect, and it is never the stricter of the two for a real host. An IDN hostname works if the owner writes it in its `xn--` form; both checks accept that. Uppercase is refused by both, so the owner must write it in lowercase. Nothing more is needed.
- **`http` and a port only for `localhost`: the right fence?** Yes. Browsers treat `http://localhost` as a secure context and accept `localhost` as an RP ID. An IP address can never be an RP ID, so refusing `127.0.0.1` is consistent with that. One test is missing for this fence; see P3 #1.

### Findings

### [P3] #1 The localhost exception is not proven to need RP ID `localhost`
- Category: test gap
- Evidence: mutant W3 removes `if rp_id == "localhost" else None`, so `http://localhost:<port>` is accepted for any RP ID. It **survived**, 84 of 84 passed. No test pairs a real hostname with a localhost origin.
- Failure scenario: RP ID `skiw.test` with origin `http://localhost:8000` would pass start-up. It cannot reach a host (host Compose never sets the origin), and a browser would refuse the ceremony anyway, so the impact is a confusing local setup rather than a hole.
- Required correction (here or in 1a-2): add `("skiw.test", "http://localhost:8000")` to `test_any_other_origin_is_refused`.
- Owner: builder · Verification: W3 is killed.

### [P3] #2 Forward notes (no change here)
- **Review and second checkouts on other ports.** `local-dev.md` says to open the app at exactly `http://localhost:8000`. Reviews and parallel checkouts run e2e on other ports (8050 to 8054 so far). Once M3g-2 runs a virtual-authenticator ceremony, those runs need `SKIW_WEBAUTHN_ORIGIN=http://localhost:<port>` in their `.env`, or the origin check will fail them. The M3g-2 runbook line should say so.
- **Owner ask (from the PR):** the G9 hostname for each environment is also the passkey RP ID, and should be fixed before the first passkey is registered. I agree; nothing in this PR names one.

### Verification performed
In a detached checkout at the head with its own DB (`review-153`, port 5459), `make install lint typecheck test test-live host-test`:
- ruff, contracts, Semgrep and eslint clean;
- mypy 243 files, and `tsc`;
- **1842 passed**; vitest 45 passed;
- test-live **923 passed**; host-test **855 passed**.

`git diff --check` clean, and a grep of the diff for secret-shaped assignments found nothing.

**Mutants** (scratch copy, bytecode off, caches cleared, on the three settings test files):
- killed: W1 (no last-label letter check), W2 (no length cap), W4 (no port cap), W5 (default origin `http`), W6 (empty origin taken as the default), W7 (`asgi` check dropped), W8 (local origin allows `127.0.0.1`), W9 (error echoes the value), W10 (RP ID lower-cased before matching);
- **survived:** W3 (P3 #1).

Not run: `e2e`, `host-test-live`, gitleaks locally (nothing reads the setting yet; CI `security` green).

### Residual risks
- The settings are checked but unused until M3g-1a-2. The real proof that the origin matches what browsers send comes with the ceremony tests and the M3g-2 virtual authenticator.
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
