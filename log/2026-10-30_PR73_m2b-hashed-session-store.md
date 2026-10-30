# PR 73 — feat(accounts): hashed session store and fixed absolute deadline (M2b)

- **Merged:** 2026-10-30T15:28:25Z (GitHub) · **Merge commit:** 33effaa732f41b111a1a6a2ee46327a8403ca74c · **Branch:** feat/m2b-hashed-session-store
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-73.receipt` on agent-logs (receipt commit ffdbd2cdd94a9602f23f506fb32a3842467ab018); head 16dbc06c and review-file hash fe3028cc match the final round; written 2026-10-30T15:26:09Z, before the merge
- **Merge evidence:** `gh pr view 73` state MERGED, merge commit above, merged 2026-10-30T15:28:25Z; commit is an ancestor of the fetched `origin/main`; final head SHA 16dbc06c5d2fab0f7bbe942511eb709eefd5d722 equals the reviewed SHA
- **Drafted by:** Opus sub-agent (code), Claude Sonnet 5.5 (CI fix); reviewer Codex (GPT-5) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 · **Plan:** docs/plans/2026-10-27-m2-headers-sessions-csrf.md · **Milestone:** M2 (M2b)

## What changed
Adds the `accounts` app with its own session model on `django_session` (primary key = sha256 of the cookie), an exact-grant migration for `skiw_app`, `accounts.session.SessionStore` (hashed key on every database path, sync and async; absolute 12-hour deadline fixed at row creation, kept on key rotation, reset only by `start_new_lifetime()`), `SessionMiddleware` with the `__Host-skiw_session` cookie, the `SKIW_SESSION_ABSOLUTE_H` / `SKIW_SESSION_IDLE_MIN` settings wired into every settings-import context (`migrate` keeps `skiw_migrator`), import-linter and Semgrep store-only rules, and runbook updates. About 310 lines of code.

## Why
Spec v1.20 section 9 M2: "the stored session key is not the cookie value"; D6 absolute lifetime does not slide; UNI-18; TEN-10.

## Review rounds
- R1: Approved with two optional P3s (handoff showed the pre-CI-fix head; TEN-01 labelled n/a in the self-check although the migration creates a table). No P0/P1/P2.
- Before review, CI `security` failed: the Semgrep registry rule `reflected-data-httpresponse` flagged the test-only probe views. Fixed by commit 16dbc06c (empty bodies).

## Deferred conditions
none

## Decisions worth keeping
- Six Django methods are inherited, not overridden (`save`, `asave`, `create`, `acreate`, `clear_expired`, `aclear_expired`); `test_session_store_surface.py` pins every Django 5.2.17 method and why it is safe.
- `clear()` refuses a session whose row is not read yet.
- Run the CI registry Semgrep rulesets locally before pushing: `uvx semgrep==1.179.0 --config p/python --config p/django --config p/typescript --config p/react --metrics=off --error app infra/host web/src scripts`. `make lint` runs only the project's own rules.
- Local `.env` files need `SKIW_SESSION_ABSOLUTE_H=12` and `SKIW_SESSION_IDLE_MIN=30`.

## Follow-ups
- **M2c must merge before M3** (no HMAC on `session_data` yet).
- **ASK for M3:** plan wants `accounts.models` importable by other apps; import-linter forbids it through indirect imports (`models -> session_model -> session`). Options: `allow_indirect_imports` on that contract, or move the re-export.
- Optional P3: classify TEN-01 as pass (migration-role evidence) in later self-checks.
- Idle timeout is enforced in M3; no real-host proof until M1k.

## Appendix — final review round

## Round 1 — 2026-10-30 · scope: slice
- **Code review:** base (merge base) `2b24812ac82b7059d74efaf6e8e283d6ad51db9f` · head `16dbc06c5d2fab0f7bbe942511eb709eefd5d722` · head re-checked at end: yes
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371`

**Verdict:** Approved
**Model used:** Codex (GPT-5; not mapped in `PROJECT.md` §6) · **Switch model next step?** Yes — the project maps auth/security review to Claude Opus; use that named deep tier for the next auth slice.

### Findings

### [P3] The handoff still identifies the pre-CI-fix head
- Category: defect
- Rule: reviewer role §2 (handoff/repo drift)
- Evidence: `.agent/handoff.md:1` still describes the M2a checkout at `f4b9b6b`; `.agent/handoff.md:6` names PR 73's head as `16394cb82cceab4f8ac99bb3ced129982df30aa4`, while GitHub and the reviewed snapshot are at `16dbc06c5d2fab0f7bbe942511eb709eefd5d722`.
- Failure scenario: a later builder resumes from the handoff and assumes the first PR commit, omitting the test-probe correction that CI actually reviewed.
- Why it matters: the handoff is the in-flight resume source and should identify the exact active head.
- Required correction: on the next builder resume, replace the current target/header with PR 73 and head `16dbc06c5d2fab0f7bbe942511eb709eefd5d722`; move superseded state under old history.
- Owner: builder
- Verification: the active handoff target and GitHub PR head agree.
- Status: open

### [P3] TEN-01 is implemented but mislabeled as not applicable in the self-check
- Category: guardrail mismatch
- Rule: TEN-01
- Evidence: the PR-body self-check groups `TEN-01, 03 to 09, 12` as n/a because `django_session` is global, but this PR creates that table in `app/accounts/migrations/0001_session.py:13-37`; the migration documents and uses the `skiw_migrator` ownership path, and `infra/host/tests/test_compose_config.py:305-328` preserves the migrator role.
- Failure scenario: a later database PR copies this classification and stops checking object ownership merely because a table is global.
- Why it matters: global-table status makes tenant-table rules n/a, not the schema-owner/migration-role rule.
- Required correction: classify TEN-01 as pass and cite the migration-role/ownership evidence in the next self-check update.
- Owner: builder
- Verification: the PR self-check or its successor marks TEN-01 applicable with evidence.
- Status: open

### Self-check audit

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01–05 | applies: new Python/store and boundary tooling | pass | pass | ruff, mypy, import-linter; store/surface tests | none |
| UNI-06 | n-a: no dependency | pass | n-a/pass | lockfiles unchanged | wording only |
| UNI-07–09 | 07/08 apply to env/host wiring; 09 n-a, no logging | pass / n-a | pass / n-a | secret-pattern diff scan; placeholders only | none |
| UNI-10–12 | n-a to this slice | n-a | n-a | no audit mutation, external service, or out-of-project write | none |
| UNI-13–16 | 13, 15, 16 apply; 14 n-a | pass / n-a | pass / n-a | exact-head CI, additive reversible migration, two runbooks | none |
| UNI-17–19 | 17 regression and 18 cookie apply; 19 test-only routes | pass | pass | header suite in CI; cookie live test; URLs under tests only | none |
| AUTH-01–06, 08–10, 12 | n-a: no production login/action/provider path yet | n-a | n-a | M3/M2d scope | none |
| AUTH-07 | prerequisite only: row deletion exists; account-change hooks are M3 | pass | pass for this slice | `delete`/`adelete`, cycle and flush live tests | none |
| AUTH-11 | applies to session middleware's lazy DB behavior | pass | pass | malformed-cookie no-query test; middleware source/path review | none |
| AUTH-13 | n-a: sign-out is M3 | n-a | n-a | approved plan | none |
| TEN-01 | applies: migration creates a table | n-a | pass | migration and migrate-service role wiring | yes; P3 above |
| TEN-02 | applies: runtime grants/role | pass | pass | exact ACL live test; exact-head CI | none |
| TEN-03–09, 12 | n-a: mutable global session table; no bypass | n-a | n-a | spec §4.1 closed global-table list | none |
| TEN-10 | applies: session DB allow-list | pass | pass | import-linter contract and Semgrep fixture | none |
| TEN-11 | deferred by approved slice: key-bound MAC is M2c before M3 | n-a | n-a for M2b | plan lines 26–34, 71–88 | none |
| D6 / M2b / D26 | applies | pass | pass | hash, fixed deadline, cookie, async, env and live tests | none |
| PROJECT §9 | applies: module, DB and middleware boundaries | pass | pass | effective diff and CI | none |
| FE, money, finalized records, files, events, links, payments packs | n-a: no relevant behavior changed | n-a | n-a | effective diff | none |

### Verification performed

| Command / check | Result |
|---|---|
| GitHub PR metadata and effective three-dot diff | pinned base `2b24812a`, head `16dbc06c`; 40 files; mergeable; no head substitution |
| Exact-head snapshot inventory and fingerprint | archive file list matched `git ls-tree`; all 229 original files passed the end fingerprint check |
| `git diff --check 2b24812a..16dbc06c` | pass |
| `ruff check .` and `ruff format --check .` | pass; 155 files formatted |
| `lint-imports` | pass; 10 kept, 0 broken |
| `mypy app infra/host scripts/deploy-prod` | pass; 111 source files |
| Targeted pytest: surface, settings, env wiring, host Compose | 100 passed |
| Django 5.2.17 source inspection | inherited create/save/rotation/expiry and middleware call order match the store's overrides and tests |
| Secret-pattern and injection scan of effective diff | placeholders/names only; no agent-directed or gate-skipping text |
| GitHub Actions run `41077984711` at exact head | success: lint/typecheck, 1055 unit, 94 live DB, 36 e2e, 817 host, 30 live host; security/audits and both image scans green |
| Local Semgrep | not verified locally: installed binary failed before scanning because the sandbox exposed no CA trust anchors; exact-head CI ran the local 4-rule suite/fixtures and registry suite successfully |
| Full local pytest attempt | not usable as a gate: sandbox denied loopback socket binds used by unrelated ClamAV/TLS tests; exact-head CI completed the full suite |

### Residual risks and test gaps
- M2b intentionally has no session-data HMAC. M2c must merge before M3, exactly as the approved plan requires; no production login/session writer exists in this interim state.
- The 30-minute idle timeout is validated and wired here but intentionally enforced in M3.
- No real-host proof was performed; that remains M1k/G-S1 and is not part of this CI slice.
- Codex GPT-5 is not mapped to a project tier. The next auth/security slice should use the project's named deep model.

### Required before merge
- None.

### Deferred conditions
- None from this round. The approved M2 sequencing still requires M2c before M3.

### Optional improvements
- Reconcile the handoff head and correct the TEN-01 self-check classification (the two P3 findings above).
